"""Paso 5 — Desplegar el agente a Amazon Bedrock AgentCore Runtime.

Llevamos el agente del paso 4 a producción: hosting serverless, sesión
aislada y observabilidad, sin manejar contenedores.

Creamos el IAM role de ejecución del runtime y mostramos (o ejecutamos, con
--run) los dos comandos del CLI agentcore:
  • configure → genera la config (.bedrock_agentcore.yaml)
  • deploy    → empaqueta y publica (direct_code_deploy, sin Docker local)

Requisitos: pasos 1-4. Tener instalado el CLI:  pip install bedrock-agentcore-starter-toolkit
Ejecutar:   python main.py          (muestra los comandos)
            python main.py --run    (crea el role y ejecuta el deploy)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # para importar constants.py

import json
import subprocess

import boto3

from constants import REGION, MODEL_ID, RUNTIME_ROLE, KB_NAME, AGENT_NAME

AGENT_PY = str(Path(__file__).resolve().parent.parent / "s4_agent" / "agent.py")
REQS = str(Path(__file__).resolve().parent.parent / "s4_agent" / "requirements.txt")

acct = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
ba = boto3.client("bedrock-agent", region_name=REGION)
kb_id = next(k["knowledgeBaseId"] for p in ba.get_paginator("list_knowledge_bases").paginate()
             for k in p["knowledgeBaseSummaries"] if k["name"] == KB_NAME)
ds_id = ba.list_data_sources(knowledgeBaseId=kb_id)["dataSourceSummaries"][0]["dataSourceId"]
role_arn = f"arn:aws:iam::{acct}:role/{RUNTIME_ROLE}"


def ensure_runtime_role():
    iam = boto3.client("iam")
    try:
        iam.create_role(RoleName=RUNTIME_ROLE, AssumeRolePolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{"Effect": "Allow", "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                           "Action": "sts:AssumeRole", "Condition": {"StringEquals": {"aws:SourceAccount": acct}}}]}))
    except iam.exceptions.EntityAlreadyExistsException:
        pass
    iam.put_role_policy(RoleName=RUNTIME_ROLE, PolicyName="perms", PolicyDocument=json.dumps({
        "Version": "2012-10-17", "Statement": [
            {"Effect": "Allow", "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream",
                "bedrock:Retrieve", "bedrock:IngestKnowledgeBaseDocuments", "bedrock:StartIngestionJob"], "Resource": "*"},
            {"Effect": "Allow", "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents",
                "xray:PutTraceSegments", "xray:PutTelemetryRecords", "cloudwatch:PutMetricData",
                "ecr:GetAuthorizationToken", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"], "Resource": "*"}]}))


configure = ["agentcore", "configure", "-e", AGENT_PY, "-n", AGENT_NAME, "-rf", REQS,
             "-er", role_arn, "--disable-memory"]
deploy = ["agentcore", "deploy", "--env", f"KB_ID={kb_id}", "--env", f"DATA_SOURCE_ID={ds_id}",
          "--env", f"MODEL_ID={MODEL_ID}", "-auc"]

print("🚀 Deploy a AgentCore Runtime (direct_code_deploy, sin Docker)\n")
print("1) configurar:\n   " + " ".join(configure) + "\n")
print("2) desplegar:\n   " + " ".join(deploy) + "\n")

if "--run" not in sys.argv:
    print("ℹ️  Solo mostrando los comandos. Para ejecutarlos: python main.py --run")
    sys.exit()

print(f"🔑 Asegurando IAM role {RUNTIME_ROLE}...")
ensure_runtime_role()
print("▶️  configure...")
subprocess.run(configure, check=True)
print("▶️  deploy... (1-2 min)")
subprocess.run(deploy, check=True)
print('\n✅ Agente desplegado. Probá:  agentcore invoke \'{"prompt": "hola"}\'')
