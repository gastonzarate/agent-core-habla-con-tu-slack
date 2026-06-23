"""Paso 3 — Ingestar y preguntar (RAG en acción, sin agente todavía).

La magia del RAG en su forma más simple:
  1. INGESTA  → metemos unos mensajes de ejemplo al Knowledge Base.
  2. RETRIEVE → preguntamos y devuelve los chunks más parecidos, con su CITA.

Todavía NO hay LLM ni agente: es retrieval puro. El "aha" es ver que una
pregunta en lenguaje natural encuentra el mensaje correcto por significado.

Como venís del paso 0 (todo limpio), el KB solo tiene estos mensajes,
así que el resultado es directo.

Requisitos: haber corrido los pasos 1 y 2.
Ejecutar:   python main.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # para importar constants.py

import time

import boto3

from constants import REGION, KB_NAME

MENSAJES = [
    "ana: El deploy de prod quedó para el viernes 18hs.",
    "beto: Confirmado, freeze de código el jueves.",
    "ana: El bug de login se arregló en el PR #482.",
    "caro: Decidimos migrar la base de datos a Aurora Serverless v2.",
    "beto: El cliente Acme pidió SSO con Okta.",
]
PREGUNTA = "¿cuándo es el deploy de producción?"

ba = boto3.client("bedrock-agent", region_name=REGION)
rt = boto3.client("bedrock-agent-runtime", region_name=REGION)

# buscamos el KB y su data source por nombre (creados en el paso 2)
kb_id = next(k["knowledgeBaseId"] for p in ba.get_paginator("list_knowledge_bases").paginate()
             for k in p["knowledgeBaseSummaries"] if k["name"] == KB_NAME)
ds_id = ba.list_data_sources(knowledgeBaseId=kb_id)["dataSourceSummaries"][0]["dataSourceId"]

# 1) INGESTA — empujamos los mensajes como documentos
print(f"📨 Ingestando {len(MENSAJES)} mensajes al Knowledge Base...")
ba.ingest_knowledge_base_documents(
    knowledgeBaseId=kb_id, dataSourceId=ds_id,
    documents=[{
        "content": {"dataSourceType": "CUSTOM", "custom": {
            "customDocumentIdentifier": {"id": f"demo-{i}"},
            "sourceType": "IN_LINE",
            "inlineContent": {"type": "TEXT", "textContent": {"data": texto}}}},
    } for i, texto in enumerate(MENSAJES)],
)

# 2) RETRIEVE — preguntamos (esperamos unos segundos a que indexe)
print(f'\n❓ Pregunta: "{PREGUNTA}"\n🔎 Buscando por similitud...\n')
for _ in range(12):
    res = rt.retrieve(knowledgeBaseId=kb_id, retrievalQuery={"text": PREGUNTA},
                      retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 3}})
    hits = res["retrievalResults"]
    if hits:
        break
    time.sleep(10)

for h in hits:
    print(f"   • [{h['score']:.2f}]  {h['content']['text']}")
print("\n✅ La pregunta encontró el mensaje correcto por significado (no por palabras).")
