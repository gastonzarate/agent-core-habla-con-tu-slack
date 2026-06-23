"""PASO 6 — Conectar Slack con una Lambda-puente + API Gateway.

AgentCore Runtime no se puede llamar directo desde Slack: Slack manda un
webhook (con firma) y exige responder en menos de 3 segundos. Por eso ponemos
una Lambda fina en el medio que:

  • valida la FIRMA del request (que viene de Slack de verdad),
  • responde el ACK al instante (< 3s),
  • invoca al agente en AgentCore de forma asíncrona,
  • y postea la respuesta en el hilo de Slack.

Este script empaqueta workshop/bridge/ (autocontenido) y crea/actualiza:
  • la función Lambda 'slackrag-bridge',
  • una API HTTP (API Gateway) que la expone.

Necesita en el estado (o por env) el ARN del runtime y los secretos de Slack:
  SLACK_SIGNING_SECRET, SLACK_BOT_TOKEN, SLACK_BOT_USER_ID

Ejecutar:  python workshop/steps/step6_slack.py
"""
import os
import sys
import zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # config.py

import boto3
from botocore.exceptions import ClientError

from config import REGION, PREFIX, get_state, save_state

BRIDGE_DIR = Path(__file__).resolve().parent.parent / "bridge"
FUNC = f"{PREFIX}-bridge"


def build_zip():
    """Empaqueta la carpeta bridge/ (autocontenida) en un .zip para Lambda."""
    out = BRIDGE_DIR.parent / "bridge.zip"
    names = [p.name for p in BRIDGE_DIR.glob("*.py") if p.name != "__init__.py"]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in names:
            z.write(BRIDGE_DIR / name, name)  # plano: handler.py, slack_sig.py, blocks.py, normalize.py, kb.py
    print(f"📦 Empaquetado: {out.name} ({', '.join(names)})")
    return out.read_bytes()


def main():
    runtime_arn = get_state("runtime_arn",
                            os.environ.get("AGENT_RUNTIME_ARN", "<ARN_DEL_RUNTIME>"))
    env = {
        # Nota: AWS_REGION es una key reservada de Lambda (la inyecta sola), no la seteamos.
        "AGENT_RUNTIME_ARN": runtime_arn,
        "KB_ID": get_state("kb_id"),
        "DATA_SOURCE_ID": get_state("data_source_id"),
        "SLACK_SIGNING_SECRET": os.environ.get("SLACK_SIGNING_SECRET", ""),
        "SLACK_BOT_TOKEN": os.environ.get("SLACK_BOT_TOKEN", ""),
        "SLACK_BOT_USER_ID": os.environ.get("SLACK_BOT_USER_ID", ""),
    }
    role_arn = get_state("bridge_role_arn",
                         f"arn:aws:iam::<ACCOUNT_ID>:role/{PREFIX}-bridge-role")

    code = build_zip()
    lam = boto3.client("lambda", region_name=REGION)

    print(f"λ  Función '{FUNC}' ...")
    try:
        lam.create_function(
            FunctionName=FUNC, Runtime="python3.12", Handler="handler.lambda_handler",
            Role=role_arn, Timeout=120, Code={"ZipFile": code},
            Environment={"Variables": env},
        )
        print("   creada ✅")
    except lam.exceptions.ResourceConflictException:
        lam.update_function_code(FunctionName=FUNC, ZipFile=code)
        lam.get_waiter("function_updated").wait(FunctionName=FUNC)
        lam.update_function_configuration(FunctionName=FUNC, Environment={"Variables": env})
        print("   ya existía → código + env actualizados ♻️")

    print(f"🌐 API HTTP (API Gateway) ...")
    api = boto3.client("apigatewayv2", region_name=REGION)
    existing = next((a for a in api.get_apis()["Items"] if a["Name"] == f"{PREFIX}-api"), None)
    if existing:
        endpoint = existing["ApiEndpoint"]
        print("   ya existía, la reuso ♻️")
    else:
        acct = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
        created = api.create_api(
            Name=f"{PREFIX}-api", ProtocolType="HTTP",
            Target=f"arn:aws:lambda:{REGION}:{acct}:function:{FUNC}")
        endpoint = created["ApiEndpoint"]
        try:
            lam.add_permission(FunctionName=FUNC, StatementId="apigw-invoke",
                               Action="lambda:InvokeFunction", Principal="apigateway.amazonaws.com",
                               SourceArn=f"arn:aws:execute-api:{REGION}:{acct}:{created['ApiId']}/*")
        except ClientError:
            pass
        print("   creada ✅")

    save_state(api_endpoint=endpoint)
    print(f"\n✅ Bridge listo. Request URL para Slack:\n   {endpoint}")
    print("   → pegala en la Slack App (Event Subscriptions + Slash Commands) y reinstalá.")
    print("\n👉 Siguiente: python workshop/steps/step7_schedule.py")


if __name__ == "__main__":
    main()
