# agent/agent.py
import base64
import datetime
import json
import os
import urllib.request
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel

try:  # paquete (local: python -m s4_agent.main)
    from s4_agent.normalize import normalize_messages
    from s4_agent.kb import build_kb_documents, format_retrieval_results, ingest_documents, retrieve
    from s4_agent.slack_reader import read_channel_history
except ModuleNotFoundError:  # plano (runtime: /var/task con módulos hermanos)
    from normalize import normalize_messages
    from kb import build_kb_documents, format_retrieval_results, ingest_documents, retrieve
    from slack_reader import read_channel_history

REGION = os.environ.get("AWS_REGION", "us-east-1")
KB_ID = os.environ["KB_ID"]
DATA_SOURCE_ID = os.environ["DATA_SOURCE_ID"]
MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-6")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
# Guardrail OPCIONAL (paso 4.1): si está seteado, Bedrock filtra entrada/salida.
GUARDRAIL_ID = os.environ.get("GUARDRAIL_ID", "")
GUARDRAIL_VERSION = os.environ.get("GUARDRAIL_VERSION", "DRAFT")
# Memory OPCIONAL (paso 4.1/5.1): si está seteado, el agente recuerda la
# conversación por sesión (corto plazo). En el Runtime desplegado, el chat
# server-side carga/guarda el historial acá adentro.
MEMORY_ID = os.environ.get("MEMORY_ID", "")
MEMORY_ACTOR = "slack-user"
# Jira OPCIONAL: si está configurado, el agente gana las tools buscar_jira / crear_jira.
JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "")
JIRA_PROJECT = os.environ.get("JIRA_PROJECT", "")

app = BedrockAgentCoreApp()
_model_kwargs = dict(model_id=MODEL_ID, region_name=REGION, temperature=0.2)
if GUARDRAIL_ID:
    # guardrail_latest_message: el filtro evalúa SOLO el último mensaje del
    # usuario (no toda la conversación), así no se diluye con el historial.
    _model_kwargs.update(guardrail_id=GUARDRAIL_ID, guardrail_version=GUARDRAIL_VERSION,
                         guardrail_trace="enabled", guardrail_latest_message=True)
_model = BedrockModel(**_model_kwargs)

# Cliente de memoria (solo si MEMORY_ID está seteado)
_mem = None
if MEMORY_ID:
    from bedrock_agentcore.memory import MemoryClient
    _mem = MemoryClient(region_name=REGION)


def _load_history(session_id, k=6):
    """Últimos k turnos de la sesión como mensajes de conversación de Strands."""
    turns = _mem.get_last_k_turns(memory_id=MEMORY_ID, actor_id=MEMORY_ACTOR,
                                  session_id=session_id, k=k)
    msgs = []
    for turn in turns:
        for m in turn:
            text = (m.get("content") or {}).get("text", "").strip()
            if not text:
                continue
            role = "user" if (m.get("role") or "").upper() == "USER" else "assistant"
            msgs.append({"role": role, "content": [{"text": text}]})
    return msgs


def _save_turn(session_id, pregunta, answer):
    _mem.create_event(memory_id=MEMORY_ID, actor_id=MEMORY_ACTOR, session_id=session_id,
                      messages=[(pregunta, "USER"), (answer, "ASSISTANT")])


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


def _jira(method, path, body=None):
    """Llamada a la REST API de Jira Cloud (Basic auth: email + API token)."""
    auth = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        JIRA_BASE_URL.rstrip("/") + path, data=data, method=method,
        headers={"Authorization": "Basic " + auth, "Accept": "application/json",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode() or "{}")


@tool
def buscar_jira(consulta: str) -> str:
    """Busca tickets en Jira por texto. Devuelve clave, título, estado y responsable."""
    jql = f'text ~ "{consulta}" ORDER BY updated DESC'
    try:
        res = _jira("POST", "/rest/api/3/search/jql",
                    {"jql": jql, "maxResults": 8, "fields": ["summary", "status", "assignee"]})
    except Exception as e:  # noqa: BLE001
        return f"No pude buscar en Jira: {e}"
    issues = res.get("issues", [])
    if not issues:
        return "No encontré tickets para esa búsqueda."
    lines = []
    for it in issues:
        f = it.get("fields", {})
        estado = (f.get("status") or {}).get("name", "?")
        asignado = (f.get("assignee") or {}).get("displayName", "sin asignar")
        lines.append(f"{it['key']}: {f.get('summary', '')} [{estado} · {asignado}]")
    return "\n".join(lines)


@tool
def crear_jira(resumen: str, descripcion: str = "") -> str:
    """Crea un ticket (tipo Task) en Jira. resumen = título; descripcion es opcional."""
    adf = {"type": "doc", "version": 1, "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": descripcion or resumen}]}]}
    body = {"fields": {"project": {"key": JIRA_PROJECT}, "summary": resumen,
                       "description": adf, "issuetype": {"name": "Task"}}}
    try:
        res = _jira("POST", "/rest/api/3/issue", body)
    except Exception as e:  # noqa: BLE001
        return f"No pude crear el ticket: {e}"
    key = res.get("key", "?")
    return f"Creé el ticket {key}: {resumen} ({JIRA_BASE_URL.rstrip('/')}/browse/{key})"


# Argentina (UTC-3) para que "hoy/ayer" tenga sentido local
AR_TZ = datetime.timezone(datetime.timedelta(hours=-3))
_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

BASE_SYSTEM = (
    "Sos un asistente que responde sobre la historia de Slack del equipo. "
    "Usá ask_kb para responder preguntas y SIEMPRE incluí las fuentes (los IDs de cita) al final. "
    "Cada mensaje recuperado viene con su fecha entre corchetes [AAAA-MM-DD HH:MM]: "
    "usala para resolver preguntas temporales como 'hoy', 'ayer' o 'esta semana'. "
    "Usá ingest_slack solo si te piden indexar un canal. Respondé en español, breve y preciso."
)
JIRA_SYSTEM = (
    " Tenés acceso a Jira: usá buscar_jira para consultar tickets y crear_jira para abrir uno. "
    "Antes de CREAR un ticket, confirmá con el usuario el título; nunca lo crees sin que lo pida."
)


def _today_context():
    now = datetime.datetime.now(AR_TZ)
    return f"\nFecha y hora actuales: {_DIAS[now.weekday()]} {now.strftime('%Y-%m-%d %H:%M')} (Argentina)."


_tools = [ask_kb, ingest_slack]
if JIRA_BASE_URL and JIRA_API_TOKEN:
    _tools += [buscar_jira, crear_jira]
    BASE_SYSTEM += JIRA_SYSTEM

_agent = Agent(model=_model, tools=_tools, system_prompt=BASE_SYSTEM)


def _extract_text(message):
    """Extrae el texto plano del AgentResult.message (dict role/content)."""
    try:
        parts = [c.get("text", "") for c in message.get("content", []) if "text" in c]
        return "\n".join(p for p in parts if p).strip() or str(message)
    except AttributeError:
        return str(message)


@app.entrypoint
def invoke(payload, context=None):
    prompt = payload.get("prompt", "")
    # sesión: del payload o del contexto del runtime (runtimeSessionId)
    session_id = payload.get("session_id") or getattr(context, "session_id", None)

    if _mem and session_id:                       # 1) cargar historial (memoria)
        _agent.messages = _load_history(session_id)

    _agent.system_prompt = BASE_SYSTEM + _today_context()  # contexto temporal fresco
    answer = _extract_text(_agent(prompt).message)  # 2) responder (con guardrail)

    if _mem and session_id:                       # 3) guardar el turno
        _save_turn(session_id, prompt, answer)
    return {"result": answer}


if __name__ == "__main__":
    app.run()
