"""PASO 4 — El agente (Strands) que razona y usa herramientas.

Hasta ahora hacíamos retrieve "a mano". Un AGENTE da un paso más:
  • recibe la pregunta en lenguaje natural,
  • DECIDE qué herramienta usar (acá: ask_kb → busca en el Knowledge Base),
  • le pasa el contexto recuperado a Claude,
  • y Claude redacta la respuesta final, con las citas.

El agente está definido en workshop/agent/agent.py con dos tools:
  • ask_kb(pregunta)     → responde sobre lo indexado, con citas
  • ingest_slack(canal)  → indexa un canal (lo usamos más adelante)

Acá lo ejecutamos LOCAL (en proceso), sin desplegar nada todavía.

Ejecutar:  python workshop/steps/step4_agent.py
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # config.py y agent/

from config import REGION, MODEL_ID, get_state

# El agente lee KB_ID / DATA_SOURCE_ID del entorno → los tomamos del estado del paso 2.
os.environ.setdefault("AWS_REGION", REGION)
os.environ.setdefault("MODEL_ID", MODEL_ID)
os.environ["KB_ID"] = get_state("kb_id")
os.environ["DATA_SOURCE_ID"] = get_state("data_source_id")

from agent.agent import _agent, _extract_text  # noqa: E402  (importa después de setear el entorno)

# Silenciamos el "stream" automático del agente para mostrar solo nuestra salida formateada.
_agent.callback_handler = lambda **_: None

PREGUNTA = "¿cuándo es el deploy de producción y qué hay que hacer antes?"


def main():
    print(f"🧠 Modelo: {MODEL_ID}")
    print(f"❓ Pregunta: \"{PREGUNTA}\"\n")
    print("🤖 El agente decide qué herramienta usar y responde...\n")

    result = _agent(PREGUNTA)

    print(_extract_text(result.message))
    print("\n✅ El agente usó ask_kb (retrieval) y Claude redactó la respuesta con citas.")
    print("\n👉 Siguiente: python workshop/steps/step5_deploy.py")


if __name__ == "__main__":
    main()
