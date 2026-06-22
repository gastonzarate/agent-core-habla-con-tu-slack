# infra/setup_kb.py
import os
import boto3
from infra.config import load_config


def provision_kb(cfg, vector_bucket_arn, index_arn, role_arn):
    ba = boto3.client("bedrock-agent", region_name=cfg.region)
    kb = ba.create_knowledge_base(
        name=cfg.kb_name,
        roleArn=role_arn,
        knowledgeBaseConfiguration={
            "type": "VECTOR",
            "vectorKnowledgeBaseConfiguration": {
                "embeddingModelArn": cfg.embedding_model_arn,
                "embeddingModelConfiguration": {
                    "bedrockEmbeddingModelConfiguration": {
                        "dimensions": cfg.embedding_dim,
                        "embeddingDataType": "FLOAT32",
                    }
                },
            },
        },
        storageConfiguration={
            "type": "S3_VECTORS",
            "s3VectorsConfiguration": {
                "vectorBucketArn": vector_bucket_arn,
                "indexArn": index_arn,
            },
        },
    )
    kb_id = kb["knowledgeBase"]["knowledgeBaseId"]
    ds = ba.create_data_source(
        knowledgeBaseId=kb_id,
        name=f"{cfg.prefix}-direct",
        dataSourceConfiguration={"type": "CUSTOM"},
    )
    return {
        "knowledgeBaseId": kb_id,
        "dataSourceId": ds["dataSource"]["dataSourceId"],
    }


if __name__ == "__main__":
    cfg = load_config(region=os.environ.get("AWS_REGION", "us-east-1"))
    out = provision_kb(
        cfg,
        vector_bucket_arn=os.environ["VECTOR_BUCKET_ARN"],
        index_arn=os.environ["INDEX_ARN"],
        role_arn=os.environ["KB_ROLE_ARN"],
    )
    print("knowledgeBaseId:", out["knowledgeBaseId"])
    print("dataSourceId:", out["dataSourceId"])
