# scripts/seed_demo.py
import os
from agent.normalize import normalize_messages
from agent.kb import build_kb_documents, ingest_documents

REGION = os.environ.get("AWS_REGION", "us-east-1")
KB_ID = os.environ["KB_ID"]
DS_ID = os.environ["DATA_SOURCE_ID"]

RAW = [
    {"type": "message", "user": "U1", "ts": "1.0", "text": "Deploy de prod programado para el viernes 18hs."},
    {"type": "message", "user": "U2", "ts": "2.0", "text": "Confirmado, freeze de código el jueves."},
    {"type": "message", "user": "U1", "ts": "3.0", "text": "El bug de login se arregló en el PR #482."},
    {"type": "message", "user": "U3", "ts": "4.0", "text": "Decidimos migrar la DB a Aurora Serverless v2."},
    {"type": "message", "user": "U2", "ts": "5.0", "text": "El cliente Acme pidió SSO con Okta."},
]
USER_MAP = {"U1": "ana", "U2": "beto", "U3": "caro"}

docs = normalize_messages(RAW, USER_MAP, channel="C-DEMO")
n = ingest_documents(REGION, KB_ID, DS_ID, build_kb_documents(docs))
print(f"Seed: {n} mensajes indexados.")
