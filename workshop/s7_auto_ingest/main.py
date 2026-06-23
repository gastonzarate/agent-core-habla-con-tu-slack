"""Paso 7 — Ingesta automática cada 30 minutos (EventBridge).

Una regla de EventBridge invoca la Lambda-puente cada 30 minutos con un
evento especial ({"__scheduled_ingest__": true}). La Lambda lee los canales
donde está el bot y los ingesta al Knowledge Base.

Es IDEMPOTENTE: el id de cada documento es "canal-ts", así que re-ingestar
sobrescribe (no duplica). Por eso puede releer sin llevar estado.

Requisitos: haber corrido el paso 6 (la Lambda debe existir).
Ejecutar (desde workshop/):   python -m s7_auto_ingest.main
"""


import json

import boto3

from constants import REGION, FUNC, RULE

acct = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
func_arn = f"arn:aws:lambda:{REGION}:{acct}:function:{FUNC}"
events = boto3.client("events", region_name=REGION)
lam = boto3.client("lambda", region_name=REGION)

# 1) la regla: cada 30 minutos
print(f"⏰ Creando regla EventBridge: {RULE} (rate: 30 min)")
rule_arn = events.put_rule(Name=RULE, ScheduleExpression="rate(30 minutes)", State="ENABLED")["RuleArn"]

# 2) permiso para que EventBridge invoque la Lambda
try:
    lam.add_permission(FunctionName=FUNC, StatementId="eventbridge-sched",
                       Action="lambda:InvokeFunction", Principal="events.amazonaws.com", SourceArn=rule_arn)
except lam.exceptions.ResourceConflictException:
    pass

# 3) conectar la regla a la Lambda con el evento de ingesta
events.put_targets(Rule=RULE, Targets=[{
    "Id": "1", "Arn": func_arn, "Input": json.dumps({"__scheduled_ingest__": True})}])
print("🔗 Regla conectada a la Lambda.")

# 4) disparamos una ingesta de prueba ahora (async, como lo hace EventBridge:
#    no esperamos a que termine — ingestar todos los canales puede tardar)
print("\n▶️  Disparando una ingesta de prueba (async)...")
lam.invoke(FunctionName=FUNC, InvocationType="Event",
           Payload=json.dumps({"__scheduled_ingest__": True}).encode())
print("   disparada ✅ (corre en segundo plano)")
print("\n✅ Ingesta automática activada: corre sola cada 30 minutos.")
