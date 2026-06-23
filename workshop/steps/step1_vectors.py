"""PASO 1 — Base vectorial serverless con Amazon S3 Vectors.

Acá creamos dónde van a vivir los "embeddings" (las representaciones numéricas
de cada mensaje de Slack):

  • un VECTOR BUCKET  → el almacén
  • un ÍNDICE         → la estructura de búsqueda (dimensión + métrica de distancia)

Es 100% serverless y se paga por uso. Sin servidores que mantener.

Ejecutar:  python workshop/steps/step1_vectors.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # permite importar config.py

import boto3
from botocore.exceptions import ClientError

from config import CFG, REGION, save_state


def _account_id():
    return boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]


def main():
    s3v = boto3.client("s3vectors", region_name=REGION)
    acct = _account_id()
    bucket_arn = f"arn:aws:s3vectors:{REGION}:{acct}:bucket/{CFG.vector_bucket}"
    index_arn = f"{bucket_arn}/index/{CFG.vector_index}"

    print(f"📦 Vector bucket: '{CFG.vector_bucket}'")
    try:
        s3v.create_vector_bucket(vectorBucketName=CFG.vector_bucket)
        print("   creado ✅")
    except ClientError as e:
        if "Conflict" in str(e) or "exist" in str(e).lower():
            print("   ya existía, lo reuso ♻️")
        else:
            raise

    print(f"🧭 Índice: '{CFG.vector_index}'  (dim={CFG.embedding_dim}, distancia=cosine)")
    try:
        s3v.create_index(
            vectorBucketName=CFG.vector_bucket,
            indexName=CFG.vector_index,
            dataType="float32",
            dimension=CFG.embedding_dim,   # 1024 = Titan Text Embeddings v2
            distanceMetric="cosine",
        )
        print("   creado ✅")
    except ClientError as e:
        if "Conflict" in str(e) or "exist" in str(e).lower():
            print("   ya existía, lo reuso ♻️")
        else:
            raise

    save_state(vector_bucket_arn=bucket_arn, index_arn=index_arn)
    print("\n✅ Base vectorial lista:")
    print("   bucket:", bucket_arn)
    print("   índice:", index_arn)
    print("\n👉 Siguiente: python workshop/steps/step2_kb.py")


if __name__ == "__main__":
    main()
