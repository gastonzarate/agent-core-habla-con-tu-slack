"""Paso 2 — Knowledge Base de Amazon Bedrock (RAG gestionado).

El Knowledge Base es el "cerebro": toma documentos, los corta en chunks,
genera embeddings con Titan v2 y los indexa en la base vectorial del paso 1.

Creamos:
  1. un IAM role que el KB usa para hablar con Titan y S3 Vectors,
  2. el Knowledge Base apuntando a la base vectorial,
  3. una data source CUSTOM → para inyectar documentos directo por API.

Requisitos: haber corrido el paso 1.
Ejecutar:   python main.py
"""
import json
import time

import boto3

REGION = "us-east-1"
BUCKET = "slackrag-vectors"
INDEX = "slackrag-index"
KB_NAME = "slackrag-kb"
ROLE = "slackrag-kb-role"

acct = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
bucket_arn = f"arn:aws:s3vectors:{REGION}:{acct}:bucket/{BUCKET}"
index_arn = f"{bucket_arn}/index/{INDEX}"
titan_arn = f"arn:aws:bedrock:{REGION}::foundation-model/amazon.titan-embed-text-v2:0"

# 1) IAM role que asume el Knowledge Base
iam = boto3.client("iam")
print(f"🔑 Creando IAM role: {ROLE}")
role_arn = iam.create_role(
    RoleName=ROLE,
    AssumeRolePolicyDocument=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Principal": {"Service": "bedrock.amazonaws.com"},
                       "Action": "sts:AssumeRole", "Condition": {"StringEquals": {"aws:SourceAccount": acct}}}],
    }),
)["Role"]["Arn"]
iam.put_role_policy(RoleName=ROLE, PolicyName="perms", PolicyDocument=json.dumps({
    "Version": "2012-10-17",
    "Statement": [
        {"Effect": "Allow", "Action": "bedrock:InvokeModel", "Resource": titan_arn},
        {"Effect": "Allow", "Action": "s3vectors:*", "Resource": [bucket_arn, f"{bucket_arn}/*"]},
    ],
}))

# 2) Knowledge Base (con reintento mientras el role recién creado propaga)
ba = boto3.client("bedrock-agent", region_name=REGION)
print(f"🧠 Creando Knowledge Base: {KB_NAME}")
for intento in range(6):
    try:
        kb_id = ba.create_knowledge_base(
            name=KB_NAME,
            roleArn=role_arn,
            knowledgeBaseConfiguration={
                "type": "VECTOR",
                "vectorKnowledgeBaseConfiguration": {"embeddingModelArn": titan_arn},
            },
            storageConfiguration={
                "type": "S3_VECTORS",
                "s3VectorsConfiguration": {"vectorBucketArn": bucket_arn, "indexArn": index_arn},
            },
        )["knowledgeBase"]["knowledgeBaseId"]
        break
    except ba.exceptions.ValidationException:
        print("   esperando que el IAM role propague...")
        time.sleep(8)

# 3) Data source CUSTOM (ingestión directa, sin bucket intermedio)
ds_id = ba.create_data_source(
    knowledgeBaseId=kb_id, name="slackrag-direct",
    dataSourceConfiguration={"type": "CUSTOM"},
)["dataSource"]["dataSourceId"]

print(f"\n✅ Knowledge Base creado:")
print(f"   knowledgeBaseId: {kb_id}")
print(f"   dataSourceId:    {ds_id}")
