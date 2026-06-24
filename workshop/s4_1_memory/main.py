"""Paso 4.1 — Chatear con el agente CON memoria de corto plazo.

El agente del paso 4 no recuerda nada: cada pregunta arranca de cero. Acá le
sumamos **AgentCore Memory (corto plazo)** = el historial crudo de la charla,
guardado por sesión. Antes de cada respuesta cargamos los últimos turnos y se
los pasamos como contexto; al terminar, guardamos el turno nuevo. Así podés
decir "¿y eso cuándo era?" y entiende de qué venís hablando.

Memory de corto plazo NO usa estrategias de largo plazo (no extrae nada en
background): es, literalmente, la conversación turno a turno.

Cómo funciona el bucle, en 4 líneas:
    turns  = mem.get_last_k_turns(...)        # 1) cargar historial
    prompt = historial + pregunta              # 2) armar contexto
    answer = agente(prompt)                    # 3) responder
    mem.create_event(messages=[(pregunta,USER),(answer,ASSISTANT)])  # 4) guardar

Requisitos: pasos 1-3 (KB con datos). Acceso a Claude en Bedrock.
Ejecutar (desde workshop/):   python -m s4_1_memory.main
Salí con Ctrl-C o escribiendo 'salir'.
"""
import os
from contextlib import nullcontext

import boto3
from bedrock_agentcore.memory import MemoryClient

from constants import KB_NAME, MEMORY_NAME, MODEL_ID, REGION

ACTOR_ID = "local-user"     # quién habla (un usuario, o el agente)
SESSION_ID = "local-demo"   # UNA conversación; cambialo para arrancar otra
K_TURNS = 6                 # cuántos turnos previos le damos de contexto

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


def banner(memory_id):
    if _RICH:
        console.print(Panel.fit(
            "[bold]💬  Chat con memoria[/]  ·  AgentCore Memory (corto plazo)",
            border_style="cyan", subtitle=f"sesión: {SESSION_ID}"))
        console.print(
            "[dim]Probá:[/] 1) ¿qué se decidió del deploy?   "
            "2) ¿y eso cuándo era?   ([bold]salir[/] para terminar)\n")
    else:
        print(f"\n💬 Chat con memoria · sesión '{SESSION_ID}' (memory_id={memory_id})")
        print("   Probá: 1) '¿qué se decidió del deploy?'  2) '¿y eso cuándo era?'")
        print("   Escribí 'salir' para terminar.\n")


def ask():
    raw = console.input("[bold cyan]vos[/] ❯ ") if _RICH else input("vos> ")
    return raw.strip()


def thinking():
    return console.status("[dim]🤔 el agente piensa…[/]", spinner="dots") if _RICH else nullcontext()


def show_answer(text):
    if _RICH:
        console.print(Panel(Markdown(text), title="🤖 agente",
                            title_align="left", border_style="green"))
        console.print()
    else:
        print(f"bot> {text}\n")


# --- KB_ID / DATA_SOURCE_ID por nombre (igual que el paso 4) ---
ba = boto3.client("bedrock-agent", region_name=REGION)
kb_id = next(k["knowledgeBaseId"] for p in ba.get_paginator("list_knowledge_bases").paginate()
             for k in p["knowledgeBaseSummaries"] if k["name"] == KB_NAME)
ds_id = ba.list_data_sources(knowledgeBaseId=kb_id)["dataSourceSummaries"][0]["dataSourceId"]

os.environ["AWS_REGION"] = REGION
os.environ["KB_ID"] = kb_id
os.environ["DATA_SOURCE_ID"] = ds_id
os.environ["MODEL_ID"] = MODEL_ID

# importamos el agente DESPUÉS de setear el entorno (lee su config de ahí)
from s4_agent.agent import _agent, _extract_text  # noqa: E402

_agent.callback_handler = lambda **_: None  # silenciamos el stream automático

mem = MemoryClient(region_name=REGION)


def get_or_create_memory():
    """Reusa el recurso Memory si ya existe; si no, lo crea (sin estrategias =
    solo corto plazo). Crear tarda ~1-2 min en quedar ACTIVE."""
    for m in mem.list_memories():
        if m.get("id", "").startswith(MEMORY_NAME) or m.get("name") == MEMORY_NAME:
            return m["id"]
    info(f"🧠 Creando recurso de memoria '{MEMORY_NAME}' (corto plazo, ~1-2 min)...", "yellow")
    created = mem.create_memory_and_wait(name=MEMORY_NAME, strategies=[])
    return created.get("id") or created.get("memoryId")


def load_history(memory_id):
    """Trae los últimos K_TURNS turnos y los arma como texto (orden cronológico)."""
    turns = mem.get_last_k_turns(
        memory_id=memory_id, actor_id=ACTOR_ID, session_id=SESSION_ID, k=K_TURNS
    )
    lines = []
    for turn in turns:
        for msg in turn:
            text = (msg.get("content") or {}).get("text", "").strip()
            if not text:
                continue
            quien = "Usuario" if (msg.get("role") or "").upper() == "USER" else "Asistente"
            lines.append(f"{quien}: {text}")
    return "\n".join(lines)


memory_id = get_or_create_memory()
banner(memory_id)

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

    historial = load_history(memory_id)        # 1) cargar historial
    if historial:                              # 2) armar prompt con contexto
        prompt = (
            "Conversación hasta ahora (por si el usuario hace referencia a algo previo):\n"
            f"{historial}\n\nNuevo mensaje del usuario: {pregunta}"
        )
    else:
        prompt = pregunta

    with thinking():                           # 3) responder (con spinner)
        answer = _extract_text(_agent(prompt).message)
    show_answer(answer)

    mem.create_event(                          # 4) guardar el turno (texto crudo)
        memory_id=memory_id,
        actor_id=ACTOR_ID,
        session_id=SESSION_ID,
        messages=[(pregunta, "USER"), (answer, "ASSISTANT")],
    )

info("✅ Listo. El historial quedó en AgentCore Memory (se borra con el paso 0).", "green")
