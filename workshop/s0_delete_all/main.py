"""Paso 0 — Borrar TODO lo creado por el workshop.

Deja la cuenta limpia para empezar de cero (o al final, para no dejar nada).
Borra en orden inverso a la creación e ignora lo que no exista.

Borra: regla EventBridge, API Gateway, Lambda, AgentCore Runtime,
Knowledge Base, índice y bucket de S3 Vectors, y los 3 IAM roles.

Ejecutar:  python main.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # para importar constants.py

import boto3
from botocore.exceptions import ClientError

from constants import REGION, BUCKET, INDEX, KB_NAME, FUNC, RULE, API_NAME, ROLES, AGENT_NAME


def step(msg, fn):
    """Ejecuta una limpieza e informa, sin frenar si el recurso no existe."""
    try:
        fn()
        print(f"🗑️  {msg}: borrado ✅")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("ResourceNotFoundException", "NotFoundException", "NoSuchEntity", "ValidationException"):
            print(f"   {msg}: no existía ⏭️")
        else:
            print(f"   {msg}: {code} ⚠️")
    except StopIteration:
        print(f"   {msg}: no existía ⏭️")


events = boto3.client("events", region_name=REGION)
lam = boto3.client("lambda", region_name=REGION)
api = boto3.client("apigatewayv2", region_name=REGION)
ac = boto3.client("bedrock-agentcore-control", region_name=REGION)
ba = boto3.client("bedrock-agent", region_name=REGION)
s3v = boto3.client("s3vectors", region_name=REGION)
iam = boto3.client("iam")

# 1) EventBridge (sacar targets antes de borrar la regla)
step("Regla EventBridge", lambda: (events.remove_targets(Rule=RULE, Ids=["1"]), events.delete_rule(Name=RULE)))

# 2) API Gateway
step("API Gateway", lambda: api.delete_api(
    ApiId=next(a["ApiId"] for a in api.get_apis()["Items"] if a["Name"] == API_NAME)))

# 3) Lambda
step("Lambda", lambda: lam.delete_function(FunctionName=FUNC))

# 4) AgentCore Runtime
step("AgentCore Runtime", lambda: ac.delete_agent_runtime(
    agentRuntimeId=next(r["agentRuntimeId"] for r in ac.list_agent_runtimes()["agentRuntimes"]
                        if r["agentRuntimeName"] == AGENT_NAME)))

# 5) Knowledge Base (borra también su data source)
step("Knowledge Base", lambda: ba.delete_knowledge_base(
    knowledgeBaseId=next(k["knowledgeBaseId"] for p in ba.get_paginator("list_knowledge_bases").paginate()
                         for k in p["knowledgeBaseSummaries"] if k["name"] == KB_NAME)))

# 6) S3 Vectors (índice antes que bucket)
step("Índice S3 Vectors", lambda: s3v.delete_index(vectorBucketName=BUCKET, indexName=INDEX))
step("Vector bucket", lambda: s3v.delete_vector_bucket(vectorBucketName=BUCKET))

# 7) IAM roles (borrar policies inline antes que el role)
for role in ROLES:
    def _del(role=role):
        for pol in iam.list_role_policies(RoleName=role)["PolicyNames"]:
            iam.delete_role_policy(RoleName=role, PolicyName=pol)
        iam.delete_role(RoleName=role)
    step(f"IAM role {role}", _del)

print("\n✅ Limpieza completa. Podés empezar de cero desde el paso 1.")
