"""PASO 2 — Knowledge Base de Amazon Bedrock (RAG gestionado).

El Knowledge Base es el "cerebro" que:
  • toma documentos,
  • los corta en chunks y genera embeddings (con Titan v2),
  • los guarda en nuestra base vectorial (S3 Vectors del paso 1),
  • y después permite buscarlos por similitud.

Acá creamos:
  1. un IAM role que el KB usa para hablar con Titan y S3 Vectors,
  2. el Knowledge Base apuntando a nuestra base vectorial,
  3. una "data source" CUSTOM → nos deja inyectar documentos directo por API.

Todo es find-or-create: si ya existe, lo reusa.

Ejecutar:  python workshop/steps/step2_kb.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # permite importar config.py

import json
import time

import boto3
from botocore.exceptions import ClientError

from config import CFG, REGION, PREFIX, get_state, save_state


def ensure_kb_role():
    """Crea (o reusa) el IAM role que asume el Knowledge Base."""
    iam = boto3.client("iam")
    name = f"{PREFIX}-kb-role"
    acct = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
    trust = {"Version": "2012-10-17", "Statement": [{
        "Effect": "Allow", "Principal": {"Service": "bedrock.amazonaws.com"},
        "Action": "sts:AssumeRole", "Condition": {"StringEquals": {"aws:SourceAccount": acct}}}]}
    perms = {"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Action": ["bedrock:InvokeModel"],
         "Resource": [CFG.embedding_model_arn]},
        {"Effect": "Allow", "Action": ["s3vectors:*"],
         "Resource": [f"arn:aws:s3vectors:{REGION}:{acct}:bucket/{CFG.vector_bucket}",
                      f"arn:aws:s3vectors:{REGION}:{acct}:bucket/{CFG.vector_bucket}/*"]}]}
    try:
        arn = iam.create_role(RoleName=name,
                              AssumeRolePolicyDocument=json.dumps(trust))["Role"]["Arn"]
        print(f"🔑 IAM role '{name}' creado ✅")
    except iam.exceptions.EntityAlreadyExistsException:
        arn = iam.get_role(RoleName=name)["Role"]["Arn"]
        print(f"🔑 IAM role '{name}' ya existía ♻️")
    iam.put_role_policy(RoleName=name, PolicyName=f"{PREFIX}-kb-perms",
                        PolicyDocument=json.dumps(perms))
    return arn


def find_kb(ba, name):
    for page in ba.get_paginator("list_knowledge_bases").paginate():
        for kb in page["knowledgeBaseSummaries"]:
            if kb["name"] == name:
                return kb["knowledgeBaseId"]
    return None


def find_ds(ba, kb_id, name):
    for ds in ba.list_data_sources(knowledgeBaseId=kb_id).get("dataSourceSummaries", []):
        if ds["name"] == name:
            return ds["dataSourceId"]
    return None


def main():
    bucket_arn = get_state("vector_bucket_arn")  # viene del paso 1
    index_arn = get_state("index_arn")
    ba = boto3.client("bedrock-agent", region_name=REGION)

    role_arn = ensure_kb_role()

    print(f"🧠 Knowledge Base '{CFG.kb_name}' ...")
    kb_id = find_kb(ba, CFG.kb_name)
    if kb_id:
        print("   ya existía, lo reuso ♻️")
    else:
        for attempt in range(6):  # el role recién creado tarda en propagar
            try:
                kb_id = ba.create_knowledge_base(
                    name=CFG.kb_name,
                    roleArn=role_arn,
                    knowledgeBaseConfiguration={
                        "type": "VECTOR",
                        "vectorKnowledgeBaseConfiguration": {
                            "embeddingModelArn": CFG.embedding_model_arn,
                            "embeddingModelConfiguration": {"bedrockEmbeddingModelConfiguration": {
                                "dimensions": CFG.embedding_dim, "embeddingDataType": "FLOAT32"}},
                        }},
                    storageConfiguration={
                        "type": "S3_VECTORS",
                        "s3VectorsConfiguration": {"vectorBucketArn": bucket_arn, "indexArn": index_arn}},
                )["knowledgeBase"]["knowledgeBaseId"]
                print("   creado ✅")
                break
            except ClientError as e:
                if "assume" in str(e).lower() and attempt < 5:
                    print("   esperando que propague el IAM role...")
                    time.sleep(8)
                else:
                    raise

    print(f"📥 Data source CUSTOM (ingestión directa) ...")
    ds_name = f"{PREFIX}-direct"
    ds_id = find_ds(ba, kb_id, ds_name)
    if ds_id:
        print("   ya existía, lo reuso ♻️")
    else:
        ds_id = ba.create_data_source(
            knowledgeBaseId=kb_id, name=ds_name,
            dataSourceConfiguration={"type": "CUSTOM"})["dataSource"]["dataSourceId"]
        print("   creada ✅")

    save_state(kb_id=kb_id, data_source_id=ds_id, kb_role_arn=role_arn)
    print("\n✅ Knowledge Base listo:")
    print("   knowledgeBaseId:", kb_id)
    print("   dataSourceId:   ", ds_id)
    print("\n👉 Siguiente: python workshop/steps/step3_query.py")


if __name__ == "__main__":
    main()
