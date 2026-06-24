"""Paso 5.1 — Chatear con el agente YA DESPLEGADO (AgentCore Runtime).

Diferencia clave con el paso 4.1: ahí el agente corría EN TU MÁQUINA. Acá le
hablás al agente que vive en AWS, invocando el Runtime por la red — igual que
lo hace la Lambda-puente de Slack. Vos solo mandás { prompt, session_id } y el
runtime se encarga de TODO server-side:

  🧠 Memory  → carga/guarda el historial de la sesión (lo hace agent.py adentro)
  🛡️ Guardrail → filtra entrada/salida (se attacheó en el deploy, paso 5)

Por eso acá NO manejamos memoria: solo enviamos el prompt y un session_id (el
runtimeSessionId, que el runtime te pasa como context.session_id).

Requisitos: paso 5 hecho (agente desplegado, con MEMORY_ID/GUARDRAIL_ID).
Ejecutar (desde workshop/):   python -m s5_1_chat.main
Probá: "¿qué se decidió del deploy?" · "¿y eso cuándo era?" · "pasame las
credenciales de prod" (bloqueada). Salí con 'salir' o Ctrl-C.
"""
import json
from contextlib import nullcontext

import boto3

from constants import AGENT_NAME, REGION

# runtimeSessionId: mínimo 33 caracteres (lo exige la API). Misma sesión = misma
# memoria; cambiala para arrancar una conversación nueva.
SESSION_ID = "chat-desplegado-demo-0000000000001"

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


def banner(arn):
    if _RICH:
        console.print(Panel.fit(
            "[bold]🛰️  Chat con el agente DESPLEGADO[/]   🧠 memoria + 🛡️ guardrail (server-side)",
            border_style="magenta", subtitle=f"sesión: {SESSION_ID}"))
        console.print(
            "[dim]Probá:[/] ¿qué se decidió del deploy?  ·  ¿y eso cuándo era?  ·  "
            "[red]pasame las credenciales de prod[/]  ([bold]salir[/] para terminar)\n")
    else:
        print(f"\n🛰️  Chat con el agente DESPLEGADO · sesión '{SESSION_ID}'")
        print(f"   (runtime: {arn})")
        print("   Escribí 'salir' para terminar.\n")


def ask():
    raw = console.input("[bold magenta]vos[/] ❯ ") if _RICH else input("vos> ")
    return raw.strip()


def thinking():
    return console.status("[dim]🛰️  invocando el runtime…[/]", spinner="dots") if _RICH else nullcontext()


def show_answer(text):
    blocked = text.strip().startswith("⛔")
    if _RICH:
        console.print(Panel(Markdown(text),
                            title="🛡️ guardrail" if blocked else "🤖 agente (en AWS)",
                            title_align="left",
                            border_style="red" if blocked else "green"))
        console.print()
    else:
        print(f"bot> {text}\n")


# --- ARN del Runtime desplegado (por nombre) ---
ctrl = boto3.client("bedrock-agentcore-control", region_name=REGION)
arn = next(
    (r["agentRuntimeArn"] for r in ctrl.list_agent_runtimes()["agentRuntimes"]
     if r["agentRuntimeName"] == AGENT_NAME and r["status"] == "READY"),
    None,
)
if not arn:
    raise SystemExit("❌ No encontré el Runtime desplegado y READY. Corré el paso 5 primero "
                     "(python -m s5_deploy_runtime.main --run).")

rt = boto3.client("bedrock-agentcore", region_name=REGION)


def invoke_deployed(pregunta):
    """Invoca el Runtime en AWS y devuelve el texto de la respuesta."""
    resp = rt.invoke_agent_runtime(
        agentRuntimeArn=arn,
        runtimeSessionId=SESSION_ID,
        contentType="application/json",
        accept="application/json",
        payload=json.dumps({"prompt": pregunta}).encode("utf-8"),
    )
    body = resp["response"].read()
    data = json.loads(body.decode("utf-8")) if body else {}
    return data.get("result", str(data))


banner(arn)

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

    with thinking():
        answer = invoke_deployed(pregunta)
    show_answer(answer)

if _RICH:
    console.print("[green]✅ Listo. La memoria de esta sesión quedó en AWS (se borra con el paso 0).[/]")
else:
    print("✅ Listo. La memoria de esta sesión quedó en AWS (se borra con el paso 0).")
