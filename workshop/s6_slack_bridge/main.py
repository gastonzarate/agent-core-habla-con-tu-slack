"""Paso 6 — Conectar Slack con una Lambda-puente + API Gateway.

AgentCore no se llama directo desde Slack: Slack manda un webhook firmado y
exige responder en < 3s. Una Lambda fina en el medio:
  • valida la firma, ackea al instante, invoca al agente async,
  • y postea la respuesta en el hilo.

Este script empaqueta esta carpeta (handler.py + módulos), crea el IAM role,
la función Lambda y una API HTTP que la expone.

Requisitos: pasos 1-5 (el agente desplegado). Secretos de Slack por entorno:
  export SLACK_SIGNING_SECRET=...   SLACK_BOT_TOKEN=xoxb-...   SLACK_BOT_USER_ID=U...
Ejecutar:   python main.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # para importar constants.py

import io
import json
import os
import zipfile

import boto3

from constants import REGION, FUNC, BRIDGE_ROLE, KB_NAME, AGENT_NAME, API_NAME

HERE = Path(__file__).resolve().parent

acct = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
iam = boto3.client("iam")
lam = boto3.client("lambda", region_name=REGION)
api = boto3.client("apigatewayv2", region_name=REGION)
ba = boto3.client("bedrock-agent", region_name=REGION)
ac = boto3.client("bedrock-agentcore-control", region_name=REGION)

# datos que necesita la Lambda
kb_id = next(k["knowledgeBaseId"] for p in ba.get_paginator("list_knowledge_bases").paginate()
             for k in p["knowledgeBaseSummaries"] if k["name"] == KB_NAME)
ds_id = ba.list_data_sources(knowledgeBaseId=kb_id)["dataSourceSummaries"][0]["dataSourceId"]
runtime_arn = next(r["agentRuntimeArn"] for r in ac.list_agent_runtimes()["agentRuntimes"]
                   if r["agentRuntimeName"] == AGENT_NAME)

# 1) IAM role de la Lambda
print(f"🔑 IAM role {BRIDGE_ROLE}")
try:
    role_arn = iam.create_role(RoleName=BRIDGE_ROLE, AssumeRolePolicyDocument=json.dumps({
        "Version": "2012-10-17", "Statement": [{"Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]}))["Role"]["Arn"]
except iam.exceptions.EntityAlreadyExistsException:
    role_arn = iam.get_role(RoleName=BRIDGE_ROLE)["Role"]["Arn"]
iam.put_role_policy(RoleName=BRIDGE_ROLE, PolicyName="perms", PolicyDocument=json.dumps({
    "Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"], "Resource": "*"},
        {"Effect": "Allow", "Action": "bedrock-agentcore:InvokeAgentRuntime", "Resource": "*"},
        {"Effect": "Allow", "Action": ["bedrock:IngestKnowledgeBaseDocuments", "bedrock:StartIngestionJob"], "Resource": "*"},
        {"Effect": "Allow", "Action": "lambda:InvokeFunction", "Resource": f"arn:aws:lambda:{REGION}:{acct}:function:{FUNC}"}]}))

# 2) empaquetar la carpeta (todo menos main.py)
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
    for py in HERE.glob("*.py"):
        if py.name != "main.py":
            z.write(py, py.name)
code = buf.getvalue()

env = {"AGENT_RUNTIME_ARN": runtime_arn, "KB_ID": kb_id, "DATA_SOURCE_ID": ds_id,
       "SLACK_SIGNING_SECRET": os.environ.get("SLACK_SIGNING_SECRET", ""),
       "SLACK_BOT_TOKEN": os.environ.get("SLACK_BOT_TOKEN", ""),
       "SLACK_BOT_USER_ID": os.environ.get("SLACK_BOT_USER_ID", "")}

# 3) función Lambda
print(f"λ  Función {FUNC}")
lam.create_function(FunctionName=FUNC, Runtime="python3.12", Handler="handler.lambda_handler",
                    Role=role_arn, Timeout=120, Code={"ZipFile": code}, Environment={"Variables": env})

# 4) API HTTP que la expone
print("🌐 API Gateway")
created = api.create_api(Name=API_NAME, ProtocolType="HTTP",
                         Target=f"arn:aws:lambda:{REGION}:{acct}:function:{FUNC}")
lam.add_permission(FunctionName=FUNC, StatementId="apigw", Action="lambda:InvokeFunction",
                   Principal="apigateway.amazonaws.com",
                   SourceArn=f"arn:aws:execute-api:{REGION}:{acct}:{created['ApiId']}/*")

print(f"\n✅ Bridge listo. Request URL para Slack:\n   {created['ApiEndpoint']}")
print("   → pegala en la Slack App (Event Subscriptions + Slash Commands) y reinstalá.")
