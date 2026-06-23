"""Paso 1 — Base vectorial serverless (Amazon S3 Vectors).

Creamos DÓNDE van a vivir los embeddings (las representaciones numéricas
de cada mensaje de Slack):

  • vector bucket → el almacén
  • índice        → la búsqueda por similitud (dimensión + métrica de distancia)

Es 100% serverless: se paga por uso, sin servidores que mantener.

Requisitos: credenciales AWS activas.
Ejecutar:   python main.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # para importar constants.py

import boto3

from constants import REGION, BUCKET, INDEX, EMBED_DIM

s3 = boto3.client("s3vectors", region_name=REGION)

# 1) El almacén de vectores
print(f"📦 Creando vector bucket: {BUCKET}")
s3.create_vector_bucket(vectorBucketName=BUCKET)

# 2) El índice donde se busca por similitud
print(f"🧭 Creando índice: {INDEX}  (dim={EMBED_DIM}, distancia=cosine)")
s3.create_index(
    vectorBucketName=BUCKET,
    indexName=INDEX,
    dataType="float32",
    dimension=EMBED_DIM,
    distanceMetric="cosine",
)

print("✅ Base vectorial lista.")
