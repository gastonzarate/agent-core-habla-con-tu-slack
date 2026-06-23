"""PASO 7 — Ingesta automática cada 30 minutos (EventBridge).

Hasta acá la ingesta era manual. Ahora la hacemos sola: una regla de
EventBridge invoca la Lambda-puente cada 30 minutos con un evento especial
({"__scheduled_ingest__": true}). La Lambda lee los canales donde está el
bot, normaliza los mensajes y los ingesta al Knowledge Base.

La ingesta es IDEMPOTENTE: el id de cada documento es "canal-ts", así que
re-ingestar el mismo mensaje lo sobrescribe (no duplica). Por eso el batch
puede releer los últimos mensajes sin llevar estado.

Este script crea/actualiza la regla y dispara una ingesta de prueba.

Ejecutar:  python workshop/steps/step7_schedule.py
"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # config.py

import boto3
from botocore.exceptions import ClientError

from config import REGION, PREFIX, get_state

FUNC = f"{PREFIX}-bridge"
RULE = f"{PREFIX}-ingest-30min"


def main():
    acct = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
    func_arn = f"arn:aws:lambda:{REGION}:{acct}:function:{FUNC}"
    events = boto3.client("events", region_name=REGION)
    lam = boto3.client("lambda", region_name=REGION)

    print(f"⏰ Regla EventBridge '{RULE}' (rate: 30 min) ...")
    rule_arn = events.put_rule(Name=RULE, ScheduleExpression="rate(30 minutes)",
                               State="ENABLED")["RuleArn"]
    print("   lista ✅")

    print("🔗 Permiso + target hacia la Lambda ...")
    try:
        lam.add_permission(FunctionName=FUNC, StatementId="eventbridge-sched",
                           Action="lambda:InvokeFunction", Principal="events.amazonaws.com",
                           SourceArn=rule_arn)
    except ClientError:
        pass  # el permiso ya existía
    events.put_targets(Rule=RULE, Targets=[{
        "Id": "1", "Arn": func_arn,
        "Input": json.dumps({"__scheduled_ingest__": True}),
    }])
    print("   conectado ✅")

    print("\n▶️  Disparando una ingesta de prueba ahora ...")
    resp = lam.invoke(FunctionName=FUNC,
                      Payload=json.dumps({"__scheduled_ingest__": True}).encode())
    out = json.loads(resp["Payload"].read())
    if "ingested" in out:
        print(f"   ✅ Ingestados {out['ingested']} mensajes de los canales del bot.")
    else:
        print(f"   respuesta: {out}")

    print("\n✅ Ingesta automática activada: corre sola cada 30 minutos.")
    print("🎉 Workshop completo. Probá en Slack:  @slack-rag ¿de qué se viene hablando?")


if __name__ == "__main__":
    main()
