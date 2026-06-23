"""Paso 4 — El agente (Strands) que razona y usa herramientas, en LOCAL.

Hasta ahora hacíamos retrieve "a mano". Un AGENTE da un paso más:
recibe la pregunta, DECIDE usar la tool ask_kb, le pasa el contexto a Claude,
y Claude redacta la respuesta final con citas.

El agente está en agent.py (esta carpeta), con dos tools: ask_kb e ingest_slack.
Acá lo corremos LOCAL, sin desplegar nada.

Requisitos: pasos 1-3. Acceso a Claude en Bedrock.
Ejecutar:   python main.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # para importar constants.py

import os

import boto3

from constants import REGION, KB_NAME, MODEL_ID

PREGUNTA = "¿cuándo es el deploy de producción y qué hay que hacer antes?"

# el agente lee KB_ID / DATA_SOURCE_ID del entorno → los buscamos por nombre
ba = boto3.client("bedrock-agent", region_name=REGION)
kb_id = next(k["knowledgeBaseId"] for p in ba.get_paginator("list_knowledge_bases").paginate()
             for k in p["knowledgeBaseSummaries"] if k["name"] == KB_NAME)
ds_id = ba.list_data_sources(knowledgeBaseId=kb_id)["dataSourceSummaries"][0]["dataSourceId"]

os.environ["AWS_REGION"] = REGION
os.environ["KB_ID"] = kb_id
os.environ["DATA_SOURCE_ID"] = ds_id
os.environ["MODEL_ID"] = MODEL_ID

# importamos el agente DESPUÉS de setear el entorno
from agent import _agent, _extract_text

_agent.callback_handler = lambda **_: None  # silenciamos el stream automático

print(f'❓ Pregunta: "{PREGUNTA}"\n🤖 El agente decide qué tool usar y responde...\n')
result = _agent(PREGUNTA)
print(_extract_text(result.message))
print("\n✅ El agente usó ask_kb (retrieval) y Claude redactó la respuesta con citas.")
