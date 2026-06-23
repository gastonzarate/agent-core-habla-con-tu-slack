"""Configuración compartida del workshop.

Cada paso importa de acá los nombres/región y un pequeño 'estado' que se
guarda en disco (state.local.json) para pasar IDs de un paso al siguiente.

Variables de entorno (con defaults):
  AWS_REGION        región AWS               (default us-east-1)
  WORKSHOP_PREFIX   prefijo de los recursos  (default slackrag)
  MODEL_ID          modelo de Claude         (default us.anthropic.claude-sonnet-4-6)
"""
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

REGION = os.environ.get("AWS_REGION", "us-east-1")
PREFIX = os.environ.get("WORKSHOP_PREFIX", "slackrag")
MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-6")


def embedding_model_arn(region: str) -> str:
    return f"arn:aws:bedrock:{region}::foundation-model/amazon.titan-embed-text-v2:0"


@dataclass(frozen=True)
class Config:
    region: str
    prefix: str
    vector_bucket: str
    vector_index: str
    kb_name: str
    embedding_model_arn: str
    embedding_dim: int = 1024


def load_config(region: str = REGION, prefix: str = PREFIX) -> Config:
    return Config(
        region=region,
        prefix=prefix,
        vector_bucket=f"{prefix}-vectors",
        vector_index=f"{prefix}-index",
        kb_name=f"{prefix}-kb",
        embedding_model_arn=embedding_model_arn(region),
    )


CFG = load_config()  # .vector_bucket, .vector_index, .kb_name, .embedding_dim, .embedding_model_arn

_STATE = Path(__file__).resolve().parent / "state.local.json"


def save_state(**kwargs):
    """Guarda/actualiza valores (ARNs, IDs) para los pasos siguientes."""
    data = all_state()
    data.update(kwargs)
    _STATE.write_text(json.dumps(data, indent=2))


def all_state():
    return json.loads(_STATE.read_text()) if _STATE.exists() else {}


def get_state(key, default=None):
    """Lee un valor guardado por un paso anterior; corta con mensaje claro si falta."""
    val = all_state().get(key, default)
    if val is None and default is None:
        sys.exit(f"❌ Falta '{key}' en el estado. ¿Corriste el paso anterior?")
    return val
