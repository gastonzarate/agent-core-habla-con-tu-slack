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
from pathlib import Path

# Permite importar los módulos ya probados del repo (infra/, agent/).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from infra.config import load_config  # noqa: E402

REGION = os.environ.get("AWS_REGION", "us-east-1")
PREFIX = os.environ.get("WORKSHOP_PREFIX", "slackrag")
MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-6")

CFG = load_config(region=REGION, prefix=PREFIX)  # .vector_bucket, .vector_index, .kb_name, .embedding_dim, .embedding_model_arn

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
