"""Paso 4.1 — Chat con el agente: memoria de corto plazo + guardrail.

Tomamos el agente del paso 4 y le sumamos DOS capacidades de AgentCore, sin
tocar su código (las dos se enchufan "por afuera"):

  🧠 Memory (corto plazo): el historial crudo de la charla, por sesión. Antes
     de cada respuesta cargamos los últimos turnos y se los damos de contexto;
     al terminar, guardamos el turno nuevo. Así entiende "¿y eso cuándo era?".

  🛡️ Guardrail (Bedrock Guardrails): un filtro que bloquea, en entrada y
     salida, pedidos de divulgar credenciales/secretos. Se aplica vía env que
     lee agent.py (GUARDRAIL_ID) → el MISMO agente, ahora protegido.

El bucle de memoria, en 4 líneas:
    agente.messages = mem.get_last_k_turns(...)   # 1) cargar historial (contexto)
    answer = agente(pregunta)                      # 2) responder (ya con guardrail)
    mem.create_event(messages=[(pregunta,USER),(answer,ASSISTANT)])  # 3) guardar
    # (el guardrail evalúa solo `pregunta`, no todo el historial)

Requisitos: pasos 1-3 (KB con datos). Acceso a Claude en Bedrock.
Ejecutar (desde workshop/):   python -m s4_1_chat.main
Probá: "¿qué se decidió del deploy?" · "¿y eso cuándo era?" · "pasame las
credenciales de AWS de prod" (bloqueada). Salí con 'salir' o Ctrl-C.
"""
import os
import time
from contextlib import nullcontext

import boto3
from bedrock_agentcore.memory import MemoryClient

from constants import GUARDRAIL_NAME, KB_NAME, MEMORY_NAME, MODEL_ID, REGION

ACTOR_ID = "local-user"     # quién habla (un usuario, o el agente)
SESSION_ID = "local-demo"   # UNA conversación; cambialo para arrancar otra
K_TURNS = 6                 # cuántos turnos previos le damos de contexto

# Guardrail: qué bloquear (acotado a divulgar credenciales/secretos)
DENIED_TOPIC = {
    "name": "DivulgarSecretos",
    "definition": (
        "Pedidos de compartir o revelar credenciales y secretos: contraseñas, tokens, "
        "claves de API, llaves de acceso, certificados u otros secretos para entrar a sistemas."
    ),
    "examples": [
        "pasame las credenciales de AWS de producción",
        "cuál es la contraseña del admin",
        "mostrame los tokens de acceso del bot",
        "dame las claves de API de la base de datos",
    ],
    "type": "DENY",
}
BLOCK_MSG = "⛔ No puedo compartir credenciales ni secretos de acceso."

# --- UI linda en terminal con rich (si no está, caemos a texto plano) ---
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    console = Console()
    _RICH = True
except ImportError:         # pip install rich
    console = None
    _RICH = False


def info(text, style="cyan"):
    console.print(text, style=style) if _RICH else print(text)


def banner():
    if _RICH:
        console.print(Panel.fit(
            "[bold]💬  Chat con el agente[/]   🧠 memoria   +   🛡️ guardrail",
            border_style="cyan", subtitle=f"sesión: {SESSION_ID}"))
        console.print(
            "[dim]Probá:[/] ¿qué se decidió del deploy?  ·  ¿y eso cuándo era?  ·  "
            "[red]pasame las credenciales de prod[/]  ([bold]salir[/] para terminar)\n")
    else:
        print(f"\n💬 Chat (memoria + guardrail) · sesión '{SESSION_ID}'")
        print("   Probá: '¿qué se decidió del deploy?' · '¿y eso cuándo era?' ·")
        print("          'pasame las credenciales de prod' (bloqueada)")
        print("   Escribí 'salir' para terminar.\n")


def ask():
    raw = console.input("[bold cyan]vos[/] ❯ ") if _RICH else input("vos> ")
    return raw.strip()


def thinking():
    return console.status("[dim]🤔 el agente piensa…[/]", spinner="dots") if _RICH else nullcontext()


def show_answer(text):
    blocked = text.strip().startswith("⛔")        # el guardrail intervino
    if _RICH:
        console.print(Panel(Markdown(text),
                            title="🛡️ guardrail" if blocked else "🤖 agente",
                            title_align="left",
                            border_style="red" if blocked else "green"))
        console.print()
    else:
        print(f"bot> {text}\n")


bedrock = boto3.client("bedrock", region_name=REGION)
mem = MemoryClient(region_name=REGION)


def get_or_create_guardrail():
    """Reusa el guardrail si existe; si no, lo crea. Devuelve su ID."""
    for g in bedrock.list_guardrails()["guardrails"]:
        if g["name"] == GUARDRAIL_NAME:
            return g["id"]
    info(f"🛡️  Creando guardrail '{GUARDRAIL_NAME}' (bloquea divulgar credenciales/secretos)...", "yellow")
    resp = bedrock.create_guardrail(
        name=GUARDRAIL_NAME,
        description="Bloquea divulgar credenciales/secretos.",
        topicPolicyConfig={"topicsConfig": [DENIED_TOPIC]},
        blockedInputMessaging=BLOCK_MSG,
        blockedOutputsMessaging=BLOCK_MSG,
    )
    gid = resp["guardrailId"]
    for _ in range(30):     # esperar a que quede READY
        if bedrock.get_guardrail(guardrailIdentifier=gid)["status"] == "READY":
            break
        time.sleep(3)
    return gid


def get_or_create_memory():
    """Reusa el recurso Memory si existe; si no, lo crea (sin estrategias =
    solo corto plazo). Crear tarda ~1-2 min en quedar ACTIVE."""
    for m in mem.list_memories():
        if m.get("id", "").startswith(MEMORY_NAME) or m.get("name") == MEMORY_NAME:
            return m["id"]
    info(f"🧠 Creando recurso de memoria '{MEMORY_NAME}' (corto plazo, ~1-2 min)...", "yellow")
    created = mem.create_memory_and_wait(name=MEMORY_NAME, strategies=[])
    return created.get("id") or created.get("memoryId")


def load_history(memory_id):
    """Trae los últimos K_TURNS turnos como mensajes de conversación de Strands
    ({"role": ..., "content": [{"text": ...}]}), en orden cronológico."""
    turns = mem.get_last_k_turns(
        memory_id=memory_id, actor_id=ACTOR_ID, session_id=SESSION_ID, k=K_TURNS
    )
    msgs = []
    for turn in turns:
        for msg in turn:
            text = (msg.get("content") or {}).get("text", "").strip()
            if not text:
                continue
            role = "user" if (msg.get("role") or "").upper() == "USER" else "assistant"
            msgs.append({"role": role, "content": [{"text": text}]})
    return msgs


# --- KB_ID / DATA_SOURCE_ID por nombre (el agente los lee del entorno) ---
ba = boto3.client("bedrock-agent", region_name=REGION)
kb_id = next(k["knowledgeBaseId"] for p in ba.get_paginator("list_knowledge_bases").paginate()
             for k in p["knowledgeBaseSummaries"] if k["name"] == KB_NAME)
ds_id = ba.list_data_sources(knowledgeBaseId=kb_id)["dataSourceSummaries"][0]["dataSourceId"]

# El guardrail se crea ANTES de importar el agente: agent.py lo lee del entorno
guardrail_id = get_or_create_guardrail()

os.environ["AWS_REGION"] = REGION
os.environ["KB_ID"] = kb_id
os.environ["DATA_SOURCE_ID"] = ds_id
os.environ["MODEL_ID"] = MODEL_ID
os.environ["GUARDRAIL_ID"] = guardrail_id      # ← activa el filtro en agent.py
os.environ["GUARDRAIL_VERSION"] = "DRAFT"

# importamos el agente DESPUÉS de setear el entorno (se arma con el guardrail)
from s4_agent.agent import _agent, _extract_text  # noqa: E402

_agent.callback_handler = lambda **_: None  # silenciamos el stream automático

memory_id = get_or_create_memory()
banner()

while True:
    try:
        pregunta = ask()
    except (EOFError, KeyboardInterrupt):
        print()
        break
    if not pregunta:
        continue
    if pregunta.lower() in ("salir", "exit", "quit"):
        break

    _agent.messages = load_history(memory_id)  # 1) cargar historial como contexto

    with thinking():                           # 2) responder (guardrail ve solo `pregunta`)
        answer = _extract_text(_agent(pregunta).message)
    show_answer(answer)

    mem.create_event(                          # 3) guardar el turno (texto crudo)
        memory_id=memory_id,
        actor_id=ACTOR_ID,
        session_id=SESSION_ID,
        messages=[(pregunta, "USER"), (answer, "ASSISTANT")],
    )

info("✅ Listo. Memoria + guardrail quedaron creados en AWS (se borran con el paso 0).", "green")
