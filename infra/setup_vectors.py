# infra/setup_vectors.py
import os
import boto3
from infra.config import load_config


def provision_vectors(cfg):
    s3v = boto3.client("s3vectors", region_name=cfg.region)
    bucket = s3v.create_vector_bucket(vectorBucketName=cfg.vector_bucket)
    index = s3v.create_index(
        vectorBucketName=cfg.vector_bucket,
        indexName=cfg.vector_index,
        dataType="float32",
        dimension=cfg.embedding_dim,
        distanceMetric="cosine",
    )
    return {
        "vectorBucketArn": bucket["vectorBucketArn"],
        "indexArn": index["indexArn"],
    }


if __name__ == "__main__":
    cfg = load_config(region=os.environ.get("AWS_REGION", "us-east-1"))
    out = provision_vectors(cfg)
    print("vectorBucketArn:", out["vectorBucketArn"])
    print("indexArn:", out["indexArn"])
