"""Paso 5 — Desplegar el agente a Amazon Bedrock AgentCore Runtime.

Llevamos el agente del paso 4 a producción: hosting serverless, sesión
aislada y observabilidad, sin manejar contenedores.

Creamos el IAM role de ejecución del runtime y mostramos (o ejecutamos, con
--run) los dos comandos del CLI agentcore:
  • configure → genera la config (.bedrock_agentcore.yaml)
  • deploy    → empaqueta y publica (direct_code_deploy, sin Docker local)

Requisitos: pasos 1-4. CLI instalado (con Python 3.13):
  uv tool install --python 3.13 bedrock-agentcore-starter-toolkit==0.3.9
Ejecutar (desde workshop/):   python -m s5_deploy_runtime.main          (muestra los comandos)
                              python -m s5_deploy_runtime.main --run    (crea el role y despliega)
"""

import os
import sys
from pathlib import Path


import json
import subprocess

import boto3
from bedrock_agentcore.memory import MemoryClient
from constants import AGENT_NAME, GUARDRAIL_NAME, KB_NAME, MEMORY_NAME, MODEL_ID, REGION, RUNTIME_ROLE

# El CLI agentcore exige que el entrypoint esté DENTRO del cwd → corremos desde s4_agent/
AGENT_DIR = str(Path(__file__).resolve().parent.parent / "s4_agent")

acct = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
ba = boto3.client("bedrock-agent", region_name=REGION)
kb_id = next(
    k["knowledgeBaseId"]
    for p in ba.get_paginator("list_knowledge_bases").paginate()
    for k in p["knowledgeBaseSummaries"]
    if k["name"] == KB_NAME
)
ds_id = ba.list_data_sources(knowledgeBaseId=kb_id)["dataSourceSummaries"][0]["dataSourceId"]
role_arn = f"arn:aws:iam::{acct}:role/{RUNTIME_ROLE}"

# Si el paso 4.1 creó el guardrail, lo attacheamos al Runtime (el agente lo
# lee de GUARDRAIL_ID). Si no existe, deployamos sin filtro.
guardrail_id = next(
    (g["id"] for g in boto3.client("bedrock", region_name=REGION).list_guardrails()["guardrails"]
     if g["name"] == GUARDRAIL_NAME),
    None,
)

# Memory: el agente desplegado recuerda por sesión (corto plazo). Buscamos el
# recurso; si no existe, se crea recién en --run (crear tarda ~1-2 min).
_mem = MemoryClient(region_name=REGION)


def find_memory():
    for m in _mem.list_memories():
        if m.get("id", "").startswith(MEMORY_NAME) or m.get("name") == MEMORY_NAME:
            return m["id"]
    return None


def ensure_memory():
    mid = find_memory()
    if mid:
        return mid
    print("🧠 Creando recurso Memory (corto plazo, ~1-2 min)...")
    created = _mem.create_memory_and_wait(name=MEMORY_NAME, strategies=[])
    return created.get("id") or created.get("memoryId")


memory_id = find_memory()


def ensure_runtime_role():
    iam = boto3.client("iam")
    try:
        iam.create_role(
            RoleName=RUNTIME_ROLE,
            AssumeRolePolicyDocument=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                            "Action": "sts:AssumeRole",
                            "Condition": {"StringEquals": {"aws:SourceAccount": acct}},
                        }
                    ],
                }
            ),
        )
    except iam.exceptions.EntityAlreadyExistsException:
        pass
    iam.put_role_policy(
        RoleName=RUNTIME_ROLE,
        PolicyName="perms",
        PolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "bedrock:InvokeModel",
                            "bedrock:InvokeModelWithResponseStream",
                            "bedrock:ApplyGuardrail",
                            "bedrock:Retrieve",
                            "bedrock:IngestKnowledgeBaseDocuments",
                            "bedrock:StartIngestionJob",
                            "bedrock-agentcore:CreateEvent",
                            "bedrock-agentcore:ListEvents",
                            "bedrock-agentcore:ListSessions",
                            "bedrock-agentcore:GetEvent",
                        ],
                        "Resource": "*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                            "xray:PutTraceSegments",
                            "xray:PutTelemetryRecords",
                            "cloudwatch:PutMetricData",
                            "ecr:GetAuthorizationToken",
                            "ecr:BatchGetImage",
                            "ecr:GetDownloadUrlForLayer",
                        ],
                        "Resource": "*",
                    },
                ],
            }
        ),
    )


configure = [
    "agentcore",
    "configure",
    "-e",
    "agent.py",
    "-n",
    AGENT_NAME,
    "-rf",
    "requirements.txt",
    "-er",
    role_arn,
    "--disable-memory",
]
deploy = [
    "agentcore",
    "deploy",
    "--env",
    f"KB_ID={kb_id}",
    "--env",
    f"DATA_SOURCE_ID={ds_id}",
    "--env",
    f"MODEL_ID={MODEL_ID}",
]
if guardrail_id:  # attacheamos el guardrail del paso 4.1 al Runtime
    deploy += ["--env", f"GUARDRAIL_ID={guardrail_id}", "--env", "GUARDRAIL_VERSION=DRAFT"]
    print(f"🛡️  Guardrail {guardrail_id} → se aplica también en el Runtime desplegado")
if memory_id:  # el agente desplegado recuerda por sesión
    deploy += ["--env", f"MEMORY_ID={memory_id}"]
    print(f"🧠 Memory {memory_id} → el agente recuerda por sesión")
# Jira (opcional): si están en el entorno (.env), el agente gana las tools de Jira
_jira_envs = ["JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_PROJECT"]
if os.environ.get("JIRA_BASE_URL") and os.environ.get("JIRA_API_TOKEN"):
    for k in _jira_envs:
        deploy += ["--env", f"{k}={os.environ.get(k, '')}"]
    print("🎫 Jira configurado → el agente puede buscar/crear tickets")
deploy += ["-auc"]

print("🚀 Deploy a AgentCore Runtime (direct_code_deploy, sin Docker)\n")
print("1) configurar:\n   " + " ".join(configure) + "\n")
print("2) desplegar:\n   " + " ".join(deploy) + "\n")

if "--run" not in sys.argv:
    print("ℹ️  Solo mostrando los comandos. Para ejecutarlos: python main.py --run")
    sys.exit()

print(f"🔑 Asegurando IAM role {RUNTIME_ROLE}...")
ensure_runtime_role()

# Memory: si no existía al armar el comando, la creamos ahora e inyectamos MEMORY_ID
memory_id = ensure_memory()
if not any(a.startswith("MEMORY_ID=") for a in deploy):
    deploy[deploy.index("-auc"):deploy.index("-auc")] = ["--env", f"MEMORY_ID={memory_id}"]
print(f"🧠 Memory lista: {memory_id}")

# configure conserva el agent_id de un deploy anterior; si ese runtime se borró
# en AWS, deploy intenta hacer UpdateAgentRuntime sobre un ID inexistente y falla
# con ResourceNotFoundException. Borramos la config previa para empezar limpio
# (deploy crea un runtime nuevo). El caché de build en .bedrock_agentcore/ no estorba.
stale_config = Path(AGENT_DIR) / ".bedrock_agentcore.yaml"
if stale_config.exists():
    print(f"🧹 Borrando config previa ({stale_config.name}) para crear runtime nuevo...")
    stale_config.unlink()

print("▶️  configure...")
# corremos desde s4_agent/ (el CLI exige entrypoint dentro del cwd); newlines = aceptar defaults
subprocess.run(configure, cwd=AGENT_DIR, input=b"\n" * 20, check=True)
print("▶️  deploy... (1-2 min)")
subprocess.run(deploy, cwd=AGENT_DIR, check=True)
print('\n✅ Agente desplegado. Probá:  agentcore invoke \'{"prompt": "hola"}\'')
