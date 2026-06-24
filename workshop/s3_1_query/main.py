"""Paso 3.1 — Solo preguntar (sin ingestar).

Para repreguntar las veces que quieras sobre lo que YA está en el Knowledge
Base, sin volver a ingestar. Útil en vivo para probar varias preguntas.

Requisitos: haber ingestado antes (paso 3).
Ejecutar (desde workshop/):   python -m s3_1_query.main "¿qué pasó con el deploy?"
"""
import sys

import boto3

from constants import KB_NAME, REGION

PREGUNTA = sys.argv[1] if len(sys.argv) > 1 else "¿qué se decidió hoy?"

ba = boto3.client("bedrock-agent", region_name=REGION)
rt = boto3.client("bedrock-agent-runtime", region_name=REGION)
kb_id = next(
    k["knowledgeBaseId"]
    for p in ba.get_paginator("list_knowledge_bases").paginate()
    for k in p["knowledgeBaseSummaries"]
    if k["name"] == KB_NAME
)

print(f'❓ Pregunta: "{PREGUNTA}"\n🔎 Buscando por similitud...\n')
res = rt.retrieve(
    knowledgeBaseId=kb_id,
    retrievalQuery={"text": PREGUNTA},
    retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 5}},
)
hits = res["retrievalResults"]
if not hits:
    print("   (sin resultados — ¿ingestaste con el paso 3?)")
for h in hits:
    print(f"   • [{h['score']:.2f}]  {h['content']['text'][:140]}")
