# bridge/handler.py
import json
import os
import urllib.parse
import urllib.request

import boto3

try:  # paquete (local / tests)
    from bridge.slack_sig import verify_slack_signature
    from bridge.blocks import build_slack_response
except ModuleNotFoundError:  # plano (Lambda: handler.py en la raíz del zip)
    from slack_sig import verify_slack_signature
    from blocks import build_slack_response

REGION = os.environ.get("AWS_REGION", "us-east-1")
RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")
SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")
FUNCTION_NAME = os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "")


def classify_request(raw_body, content_type):
    if "application/json" in content_type:
        data = json.loads(raw_body)
        if data.get("type") == "url_verification":
            return {"kind": "challenge", "challenge": data["challenge"]}
        return {"kind": "event", "data": data}
    form = {k: v[0] for k, v in urllib.parse.parse_qs(raw_body).items()}
    return {
        "kind": "slash",
        "command": form.get("command", ""),
        "text": form.get("text", ""),
        "response_url": form.get("response_url", ""),
        "channel_id": form.get("channel_id", ""),
    }


def _process_async(action):
    prompt = action["text"] or "Resumí lo último del canal."
    if action["command"] == "/ingest":
        prompt = f"Indexá el canal {action['channel_id']}."
    client = boto3.client("bedrock-agentcore", region_name=REGION)
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=RUNTIME_ARN,
        runtimeSessionId=(action["channel_id"] or "session").ljust(33, "0"),  # min 33 chars
        payload=json.dumps({"prompt": prompt}).encode(),
        qualifier="DEFAULT",
    )
    answer = json.loads(resp["response"].read())["result"]
    body = build_slack_response(answer, [])
    req = urllib.request.Request(
        action["response_url"],
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=10)


def lambda_handler(event, context):
    # 2da invocación (async, modo Event): procesa y postea a response_url
    if isinstance(event, dict) and event.get("__async__"):
        _process_async(event["action"])
        return {"statusCode": 200}

    raw_body = event.get("body", "") or ""
    if event.get("isBase64Encoded"):
        import base64
        raw_body = base64.b64decode(raw_body).decode()
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    content_type = headers.get("content-type", "")
    action = classify_request(raw_body, content_type)

    if action["kind"] == "challenge":
        return {"statusCode": 200, "body": action["challenge"]}

    ts = headers.get("x-slack-request-timestamp", "")
    sig = headers.get("x-slack-signature", "")
    if not verify_slack_signature(SIGNING_SECRET, ts, raw_body, sig):
        return {"statusCode": 401, "body": "bad signature"}

    if action["kind"] == "slash":
        # ack <3s + auto-invocación async para el trabajo pesado (Lambda congela threads tras retornar)
        boto3.client("lambda", region_name=REGION).invoke(
            FunctionName=FUNCTION_NAME,
            InvocationType="Event",
            Payload=json.dumps({"__async__": True, "action": action}).encode(),
        )
        return {"statusCode": 200, "body": "🔎 Buscando en tu Slack..."}

    return {"statusCode": 200, "body": "ok"}
