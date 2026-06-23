"""Constantes compartidas del workshop.

Un solo lugar para los nombres de recursos. Cambiá NAME para usar un prefijo
propio (ej. si compartís la cuenta y no querés chocar con otros).

Los `main.py` de cada paso importan de acá. El código que se DESPLIEGA
(s4_agent/agent.py, s6_slack_bridge/handler.py) NO usa este archivo: lee su
config de variables de entorno, así sigue siendo autocontenido al empaquetarse.
"""

NAME = "slackrag"           # prefijo de todos los recursos
REGION = "us-east-1"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"
EMBED_DIM = 1024            # Titan Text Embeddings v2
INGEST_DAYS = 7             # ventana de ingesta: últimos N días de cada canal

# Recursos (derivados de NAME)
BUCKET = f"{NAME}-vectors"
INDEX = f"{NAME}-index"
KB_NAME = f"{NAME}-kb"
DATA_SOURCE_NAME = f"{NAME}-direct"
AGENT_NAME = NAME
FUNC = f"{NAME}-bridge"
RULE = f"{NAME}-ingest-30min"
API_NAME = f"{NAME}-api"

# IAM roles
KB_ROLE = f"{NAME}-kb-role"
RUNTIME_ROLE = f"{NAME}-runtime-role"
BRIDGE_ROLE = f"{NAME}-bridge-role"
ROLES = [BRIDGE_ROLE, RUNTIME_ROLE, KB_ROLE]


def titan_arn(region=REGION):
    """ARN del modelo de embeddings Titan v2."""
    return f"arn:aws:bedrock:{region}::foundation-model/amazon.titan-embed-text-v2:0"
