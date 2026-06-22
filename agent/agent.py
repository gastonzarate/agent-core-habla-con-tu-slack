# agent/agent.py
import os
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel

from agent.normalize import normalize_messages
from agent.kb import build_kb_documents, format_retrieval_results, ingest_documents, retrieve
from agent.slack_reader import read_channel_history

REGION = os.environ.get("AWS_REGION", "us-east-1")
KB_ID = os.environ["KB_ID"]
DATA_SOURCE_ID = os.environ["DATA_SOURCE_ID"]
MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-6")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")

app = BedrockAgentCoreApp()
_model = BedrockModel(model_id=MODEL_ID, region_name=REGION, temperature=0.2)


@tool
def ask_kb(question: str) -> str:
    """Responde una pregunta usando el conocimiento indexado de Slack, con citas."""
    context, citations = format_retrieval_results(retrieve(REGION, KB_ID, question))
    if not context:
        return "No encontré nada relevante en la historia de Slack."
    refs = ", ".join(c["id"] for c in citations)
    return f"Contexto recuperado:\n{context}\n\n[Fuentes: {refs}]"


@tool
def ingest_slack(channel: str) -> str:
    """Indexa la historia de un canal de Slack en el Knowledge Base. channel = ID del canal (ej C0123)."""
    if not SLACK_BOT_TOKEN:
        return "No hay SLACK_BOT_TOKEN configurado para leer Slack."
    messages, user_map = read_channel_history(SLACK_BOT_TOKEN, channel)
    docs = normalize_messages(messages, user_map, channel=channel)
    if not docs:
        return "No encontré mensajes para indexar."
    n = ingest_documents(REGION, KB_ID, DATA_SOURCE_ID, build_kb_documents(docs))
    return f"Indexé {n} mensajes del canal {channel}."


_agent = Agent(
    model=_model,
    tools=[ask_kb, ingest_slack],
    system_prompt=(
        "Sos un asistente que responde sobre la historia de Slack del equipo. "
        "Usá ask_kb para responder preguntas y SIEMPRE incluí las fuentes (los IDs de cita) al final. "
        "Usá ingest_slack solo si te piden indexar un canal. Respondé en español, breve y preciso."
    ),
)


def _extract_text(message):
    """Extrae el texto plano del AgentResult.message (dict role/content)."""
    try:
        parts = [c.get("text", "") for c in message.get("content", []) if "text" in c]
        return "\n".join(p for p in parts if p).strip() or str(message)
    except AttributeError:
        return str(message)


@app.entrypoint
def invoke(payload):
    result = _agent(payload.get("prompt", ""))
    return {"result": _extract_text(result.message)}


if __name__ == "__main__":
    app.run()
