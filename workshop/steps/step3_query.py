"""PASO 3 — Ingestar y preguntar (RAG en acción, sin agente todavía).

Acá se ve la magia del RAG en su forma más simple:

  1. INGESTA  → metemos unos mensajes de ejemplo al Knowledge Base.
                El KB genera los embeddings (Titan v2) y los indexa.
  2. RETRIEVE → hacemos una pregunta y el KB nos devuelve los chunks
                más parecidos por similitud, con su CITA (de qué mensaje salió).

Todavía NO hay LLM ni agente: es retrieval puro. El "aha" es ver que
una pregunta en lenguaje natural encuentra el mensaje correcto.

Ejecutar:  python workshop/steps/step3_query.py
"""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # permite importar config.py y agent/

import boto3

from config import REGION, get_state
from agent.normalize import normalize_messages
from agent.kb import build_kb_documents, ingest_documents, retrieve, format_retrieval_results

# Mensajes de ejemplo (simulan un canal de Slack).
DEMO_MESSAGES = [
    {"type": "message", "user": "U1", "ts": "1.0", "text": "El deploy de prod quedó para el viernes 18hs."},
    {"type": "message", "user": "U2", "ts": "2.0", "text": "Confirmado, freeze de código el jueves."},
    {"type": "message", "user": "U1", "ts": "3.0", "text": "El bug de login se arregló en el PR #482."},
    {"type": "message", "user": "U3", "ts": "4.0", "text": "Decidimos migrar la base de datos a Aurora Serverless v2."},
    {"type": "message", "user": "U2", "ts": "5.0", "text": "El cliente Acme pidió SSO con Okta."},
]
USER_MAP = {"U1": "ana", "U2": "beto", "U3": "caro"}

PREGUNTA = "¿cuándo es el deploy de producción?"


def main():
    kb_id = get_state("kb_id")              # del paso 2
    ds_id = get_state("data_source_id")     # del paso 2

    # 1) INGESTA -------------------------------------------------------------
    print("📨 Ingestando mensajes de ejemplo al Knowledge Base ...")
    docs = normalize_messages(DEMO_MESSAGES, USER_MAP, channel="C-DEMO")
    n = ingest_documents(REGION, kb_id, ds_id, build_kb_documents(docs))
    print(f"   {n} mensajes enviados. El KB los está embebiendo e indexando...")

    # 2) RETRIEVE ------------------------------------------------------------
    print(f"\n❓ Pregunta: \"{PREGUNTA}\"")
    print("🔎 Buscando por similitud (puede tardar unos segundos en indexar)...\n")
    for intento in range(1, 13):
        # filtramos por el canal de demo para aislar el resultado de otros datos del KB
        ctx, citas = format_retrieval_results(retrieve(REGION, kb_id, PREGUNTA, k=3, channel="C-DEMO"))
        if ctx:
            break
        time.sleep(10)
    else:
        sys.exit("   Todavía no hay resultados; reintentá en unos segundos.")

    for c in citas:
        print(f"   • [{c['score']:.2f}]  cita {c['id']}")
    print("\n📄 Chunk más relevante:")
    print("   ", ctx.split('\n\n')[0])
    print("\n✅ Retrieval funcionando: la pregunta encontró el mensaje correcto, con su cita.")
    print("\n👉 Siguiente: python workshop/steps/step4_agent.py")


if __name__ == "__main__":
    main()
