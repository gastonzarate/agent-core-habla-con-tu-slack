"""Paso 1 — Base vectorial serverless (Amazon S3 Vectors).

Creamos DÓNDE van a vivir los embeddings (las representaciones numéricas
de cada mensaje de Slack):

  • vector bucket → el almacén
  • índice        → la búsqueda por similitud (dimensión + métrica de distancia)

Es 100% serverless: se paga por uso, sin servidores que mantener.

Requisitos: credenciales AWS activas.
Ejecutar:   python main.py
"""
import boto3

REGION = "us-east-1"
BUCKET = "slackrag-vectors"
INDEX = "slackrag-index"
DIM = 1024  # Titan Text Embeddings v2 produce vectores de 1024 números

s3 = boto3.client("s3vectors", region_name=REGION)

# 1) El almacén de vectores
print(f"📦 Creando vector bucket: {BUCKET}")
s3.create_vector_bucket(vectorBucketName=BUCKET)

# 2) El índice donde se busca por similitud
print(f"🧭 Creando índice: {INDEX}  (dim={DIM}, distancia=cosine)")
s3.create_index(
    vectorBucketName=BUCKET,
    indexName=INDEX,
    dataType="float32",
    dimension=DIM,
    distanceMetric="cosine",
)

print("✅ Base vectorial lista.")
