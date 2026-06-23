"""Paso 2 — Knowledge Base de Amazon Bedrock (RAG gestionado).

El Knowledge Base es el "cerebro": toma documentos, los corta en chunks,
genera embeddings con Titan v2 y los indexa en la base vectorial del paso 1.

Creamos:
  1. un IAM role que el KB usa para hablar con Titan y S3 Vectors,
  2. el Knowledge Base apuntando a la base vectorial,
  3. una data source CUSTOM → para inyectar documentos directo por API.

Requisitos: haber corrido el paso 1.
Ejecutar (desde workshop/):   python -m s2_knowledge_base.main
"""


import json
import time

import boto3

from constants import REGION, BUCKET, INDEX, KB_NAME, KB_ROLE, DATA_SOURCE_NAME, titan_arn

acct = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
bucket_arn = f"arn:aws:s3vectors:{REGION}:{acct}:bucket/{BUCKET}"
index_arn = f"{bucket_arn}/index/{INDEX}"
titan = titan_arn(REGION)

# 1) IAM role que asume el Knowledge Base (crear-o-reusar)
iam = boto3.client("iam")
print(f"🔑 IAM role: {KB_ROLE}")
try:
    role_arn = iam.create_role(
        RoleName=KB_ROLE,
        AssumeRolePolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{"Effect": "Allow", "Principal": {"Service": "bedrock.amazonaws.com"},
                           "Action": "sts:AssumeRole", "Condition": {"StringEquals": {"aws:SourceAccount": acct}}}],
        }),
    )["Role"]["Arn"]
except iam.exceptions.EntityAlreadyExistsException:
    role_arn = iam.get_role(RoleName=KB_ROLE)["Role"]["Arn"]
iam.put_role_policy(RoleName=KB_ROLE, PolicyName="perms", PolicyDocument=json.dumps({
    "Version": "2012-10-17",
    "Statement": [
        {"Effect": "Allow", "Action": "bedrock:InvokeModel", "Resource": titan},
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
                "vectorKnowledgeBaseConfiguration": {"embeddingModelArn": titan},
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
#    dataDeletionPolicy=RETAIN → al borrar el KB no intenta limpiar el vector
#    store (lo borramos aparte en el paso 0), así el borrado es siempre limpio.
ds_id = ba.create_data_source(
    knowledgeBaseId=kb_id, name=DATA_SOURCE_NAME,
    dataSourceConfiguration={"type": "CUSTOM"},
    dataDeletionPolicy="RETAIN",
)["dataSource"]["dataSourceId"]

print("\n✅ Knowledge Base creado:")
print(f"   knowledgeBaseId: {kb_id}")
print(f"   dataSourceId:    {ds_id}")
