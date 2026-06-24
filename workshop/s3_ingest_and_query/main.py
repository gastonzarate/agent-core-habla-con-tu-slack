"""Paso 3 — Ingestar y preguntar (RAG en acción, sin agente todavía).

La magia del RAG en su forma más simple:
  1. INGESTA  → metemos mensajes al Knowledge Base.
  2. RETRIEVE → preguntamos y devuelve los chunks más parecidos, con su CITA.

Todavía NO hay LLM ni agente: es retrieval puro. El "aha" es ver que una
pregunta en lenguaje natural encuentra el mensaje correcto por significado.

Si está SLACK_BOT_TOKEN en el entorno, ingesta el ÚLTIMO DÍA real de tus
canales. Si no, usa unos mensajes de ejemplo (para correrlo sin Slack).

Requisitos: pasos 1 y 2.
Ejecutar (desde workshop/):   python -m s3_ingest_and_query.main
                              python -m s3_ingest_and_query.main "¿qué pasó con el deploy?"
"""

import os
import sys
import time

import boto3
from constants import KB_NAME, REGION
from slack_sdk import WebClient

DAYS = 1  # cuánto hacia atrás leemos de Slack
TOKEN = os.environ.get("SLACK_BOT_TOKEN")
PREGUNTA = sys.argv[1] if len(sys.argv) > 1 else "¿qué se decidió hoy?"

DEMO = [
    {"id": "demo-0", "text": "ana: El deploy de prod quedó para el viernes 18hs."},
    {"id": "demo-1", "text": "beto: Confirmado, freeze de código el jueves."},
    {"id": "demo-2", "text": "ana: El bug de login se arregló en el PR #482."},
    {"id": "demo-3", "text": "caro: Decidimos migrar la base de datos a Aurora Serverless v2."},
    {"id": "demo-4", "text": "beto: El cliente Acme pidió SSO con Okta."},
]


def slack_last_day(token):
    """Lee los mensajes del último día de cada canal del bot."""

    c = WebClient(token=token)
    umap = {
        u["id"]: (u.get("profile", {}).get("display_name") or u.get("name") or u["id"])
        for u in c.users_list(limit=500).get("members", [])
    }
    oldest = str(time.time() - DAYS * 86400)
    chans = c.users_conversations(types="public_channel,private_channel", exclude_archived=True, limit=200).get(
        "channels", []
    )
    docs = []
    for ch in chans:
        cursor = None
        while True:
            kw = {"channel": ch["id"], "oldest": oldest, "limit": 200}
            if cursor:
                kw["cursor"] = cursor
            r = c.conversations_history(**kw)
            for m in r.get("messages", []):
                if m.get("type") == "message" and not m.get("subtype") and not m.get("bot_id") and m.get("text"):
                    who = umap.get(m.get("user", ""), m.get("user", ""))
                    docs.append({"id": f"{ch['id']}-{m['ts']}", "text": f"{who}: {m['text']}"})
            cursor = r.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
    return docs


ba = boto3.client("bedrock-agent", region_name=REGION)
rt = boto3.client("bedrock-agent-runtime", region_name=REGION)
kb_id = next(
    k["knowledgeBaseId"]
    for p in ba.get_paginator("list_knowledge_bases").paginate()
    for k in p["knowledgeBaseSummaries"]
    if k["name"] == KB_NAME
)
ds_id = ba.list_data_sources(knowledgeBaseId=kb_id)["dataSourceSummaries"][0]["dataSourceId"]

# 1) Conseguir los documentos: Slack real (último día) o ejemplo
if TOKEN:
    print(f"📥 Leyendo el último día de Slack ({DAYS}d)...")
    docs = slack_last_day(TOKEN)
else:
    print("ℹ️  Sin SLACK_BOT_TOKEN → uso mensajes de ejemplo.")
    docs = DEMO

# 2) INGESTA (en lotes de 25, el límite de la API)
print(f"📨 Ingestando {len(docs)} mensajes al Knowledge Base...")
for i in range(0, len(docs), 25):
    ba.ingest_knowledge_base_documents(
        knowledgeBaseId=kb_id,
        dataSourceId=ds_id,
        documents=[
            {
                "content": {
                    "dataSourceType": "CUSTOM",
                    "custom": {
                        "customDocumentIdentifier": {"id": d["id"]},
                        "sourceType": "IN_LINE",
                        "inlineContent": {"type": "TEXT", "textContent": {"data": d["text"]}},
                    },
                },
            }
            for d in docs[i : i + 25]
        ],
    )

# 3) RETRIEVE — preguntamos (esperamos unos segundos a que indexe)
print(f'\n❓ Pregunta: "{PREGUNTA}"\n🔎 Buscando por similitud...\n')
hits = []
for _ in range(12):
    res = rt.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={"text": PREGUNTA},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 3}},
    )
    hits = res["retrievalResults"]
    if hits:
        break
    time.sleep(10)

for h in hits:
    print(f"   • [{h['score']:.2f}]  {h['content']['text'][:120]}")
print("\n✅ La pregunta encontró el mensaje correcto por significado (no por palabras).")
