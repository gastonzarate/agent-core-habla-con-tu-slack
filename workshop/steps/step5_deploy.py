"""PASO 5 — Desplegar el agente a Amazon Bedrock AgentCore Runtime.

Hasta ahora el agente corría en nuestra máquina. Ahora lo llevamos a
AgentCore Runtime: hosting serverless, con sesión aislada y observabilidad,
sin que tengamos que manejar contenedores ni servidores.

Usamos el CLI 'agentcore' (starter toolkit), que tiene dos pasos:
  • configure → genera la config del runtime (entrypoint, runtime python, role)
  • deploy    → empaqueta el código y lo publica (modo direct_code_deploy,
                NO requiere Docker local)

Este script arma los comandos con los valores correctos y los muestra.
Por seguridad NO ejecuta el deploy solo: copiás y pegás (o pasás --run).

Ejecutar:  python workshop/steps/step5_deploy.py          (muestra los comandos)
           python workshop/steps/step5_deploy.py --run    (los ejecuta)
"""
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # config.py

from config import REGION, MODEL_ID, PREFIX, get_state

AGENT_DIR = Path(__file__).resolve().parent.parent / "agent"
ENTRYPOINT = AGENT_DIR / "agent.py"
REQS = AGENT_DIR / "requirements.txt"


def main():
    kb_id = get_state("kb_id")               # del paso 2
    ds_id = get_state("data_source_id")      # del paso 2
    role_arn = get_state(                     # execution role del runtime (pre-creado en el sandbox)
        "runtime_role_arn",
        f"arn:aws:iam::<ACCOUNT_ID>:role/{PREFIX}-runtime-role",
    )

    configure = [
        "agentcore", "configure",
        "-e", str(ENTRYPOINT),
        "-n", PREFIX,
        "-rf", str(REQS),
        "-er", role_arn,
        "--disable-memory",
    ]
    deploy = [
        "agentcore", "deploy",
        "--env", f"KB_ID={kb_id}",
        "--env", f"DATA_SOURCE_ID={ds_id}",
        "--env", f"MODEL_ID={MODEL_ID}",
        "--env", f"AWS_REGION={REGION}",
        "-auc",  # auto-update si ya existe
    ]

    print("🚀 Deploy del agente a AgentCore Runtime (direct_code_deploy, sin Docker)\n")
    print("1) Configurar el runtime:\n   " + " ".join(configure) + "\n")
    print("2) Desplegar con sus variables de entorno:\n   " + " ".join(deploy) + "\n")

    if "--run" not in sys.argv:
        print("ℹ️  Mostrando comandos. Para ejecutarlos: agregá --run")
        print("\n👉 Siguiente: python workshop/steps/step6_slack.py")
        return

    print("▶️  Ejecutando configure ...")
    subprocess.run(configure, check=True)
    print("▶️  Ejecutando deploy ... (tarda 1-2 min: empaqueta deps y publica)")
    subprocess.run(deploy, check=True)
    print("\n✅ Agente desplegado. Probalo:  agentcore invoke '{\"prompt\": \"hola\"}'")
    print("\n👉 Siguiente: python workshop/steps/step6_slack.py")


if __name__ == "__main__":
    main()
