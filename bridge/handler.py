# bridge/handler.py
import base64
import json
import os
import re
import urllib.parse
import urllib.request

import boto3

try:  # paquete (local / tests)
    from bridge.slack_sig import verify_slack_signature
    from bridge.blocks import build_slack_response
    from agent.normalize import normalize_messages
    from agent.kb import build_kb_documents, ingest_documents
except ModuleNotFoundError:  # plano (Lambda: módulos en la raíz del zip)
    from slack_sig import verify_slack_signature
    from blocks import build_slack_response
    from normalize import normalize_messages
    from kb import build_kb_documents, ingest_documents

REGION = os.environ.get("AWS_REGION", "us-east-1")
RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")
SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")
FUNCTION_NAME = os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "")
BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
BOT_USER_ID = os.environ.get("SLACK_BOT_USER_ID", "")
KB_ID = os.environ.get("KB_ID", "")
DATA_SOURCE_ID = os.environ.get("DATA_SOURCE_ID", "")


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


def _strip_mention(text):
    return re.sub(r"<@[^>]+>", "", text or "").strip()


def _ask_agent(prompt, session):
    client = boto3.client("bedrock-agentcore", region_name=REGION)
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=RUNTIME_ARN,
        runtimeSessionId=(session or "session").ljust(33, "0"),
        payload=json.dumps({"prompt": prompt}).encode(),
        qualifier="DEFAULT",
    )
    return json.loads(resp["response"].read())["result"]


def _slack_get(method, params):
    url = "https://slack.com/api/" + method + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + BOT_TOKEN})
    return json.loads(urllib.request.urlopen(req, timeout=15).read().decode())


def _user_map():
    members = _slack_get("users.list", {"limit": 500}).get("members", [])
    return {u["id"]: (u.get("profile", {}).get("display_name") or u.get("name") or u["id"]) for u in members}


def _scheduled_ingest():
    """Batch idempotente: relee los últimos mensajes de cada canal del bot y los ingesta."""
    channels = _slack_get("users.conversations",
                          {"types": "public_channel,private_channel", "exclude_archived": "true", "limit": 200}).get("channels", [])
    umap = _user_map()
    total = 0
    for ch in channels:
        cid = ch["id"]
        msgs = _slack_get("conversations.history", {"channel": cid, "limit": 200}).get("messages", [])
        docs = normalize_messages(msgs, umap, channel=cid)
        if docs and KB_ID and DATA_SOURCE_ID:
            total += ingest_documents(REGION, KB_ID, DATA_SOURCE_ID, build_kb_documents(docs))
    return total


def _post_message(channel, text, thread_ts=None):
    payload = {"channel": channel, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json; charset=utf-8",
                 "Authorization": "Bearer " + BOT_TOKEN},
    )
    urllib.request.urlopen(req, timeout=10)


def _process_async(action):
    kind = action["kind"]
    if kind == "ask":
        answer = _ask_agent(action.get("text") or "Resumí lo último del canal.", action.get("session", ""))
        if action.get("response_url"):
            req = urllib.request.Request(
                action["response_url"],
                data=json.dumps(build_slack_response(answer, [])).encode(),
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
        else:
            _post_message(action["channel"], answer, action.get("thread_ts"))
    elif kind == "ingest_one":
        msg = {"type": "message", "user": action["user"], "text": action["text"], "ts": action["ts"]}
        docs = normalize_messages([msg], {action["user"]: action["user"]}, channel=action["channel"])
        if docs and KB_ID and DATA_SOURCE_ID:
            ingest_documents(REGION, KB_ID, DATA_SOURCE_ID, build_kb_documents(docs))


def _self_invoke(action):
    boto3.client("lambda", region_name=REGION).invoke(
        FunctionName=FUNCTION_NAME,
        InvocationType="Event",
        Payload=json.dumps({"__async__": True, "action": action}).encode(),
    )


def lambda_handler(event, context):
    # 2da invocación (async): procesa el trabajo pesado
    if isinstance(event, dict) and event.get("__async__"):
        _process_async(event["action"])
        return {"statusCode": 200}

    # EventBridge scheduler: ingesta batch cada 30 min
    if isinstance(event, dict) and event.get("__scheduled_ingest__"):
        n = _scheduled_ingest()
        return {"statusCode": 200, "ingested": n}

    raw_body = event.get("body", "") or ""
    if event.get("isBase64Encoded"):
        raw_body = base64.b64decode(raw_body).decode()
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    content_type = headers.get("content-type", "")
    req = classify_request(raw_body, content_type)

    if req["kind"] == "challenge":
        return {"statusCode": 200, "body": req["challenge"]}

    ts = headers.get("x-slack-request-timestamp", "")
    sig = headers.get("x-slack-signature", "")
    if not verify_slack_signature(SIGNING_SECRET, ts, raw_body, sig):
        return {"statusCode": 401, "body": "bad signature"}

    if req["kind"] == "slash":
        prompt = req["text"] or "Resumí lo último del canal."
        if req["command"] == "/ingest":
            prompt = f"Indexá el canal {req['channel_id']}."
        _self_invoke({"kind": "ask", "text": prompt,
                      "response_url": req["response_url"], "session": req["channel_id"]})
        return {"statusCode": 200, "body": "🔎 Buscando en tu Slack..."}

    if req["kind"] == "event":
        ev = req["data"].get("event", {})
        et = ev.get("type")
        if et == "app_mention":
            _self_invoke({"kind": "ask", "text": _strip_mention(ev.get("text", "")),
                          "channel": ev["channel"], "thread_ts": ev.get("thread_ts") or ev.get("ts"),
                          "session": ev["channel"]})
        elif (et == "message" and not ev.get("subtype")
              and not ev.get("bot_id") and ev.get("user") != BOT_USER_ID and ev.get("text")):
            _self_invoke({"kind": "ingest_one", "user": ev.get("user", ""),
                          "text": ev["text"], "ts": ev["ts"], "channel": ev["channel"]})
        return {"statusCode": 200, "body": "ok"}

    return {"statusCode": 200, "body": "ok"}
