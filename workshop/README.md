# Workshop — Hablá con tu Slack

Construí, paso a paso, un agente de IA serverless en AWS que ingesta mensajes
de Slack a un Knowledge Base (S3 Vectors) y responde preguntas con citas.

Cada paso es una **carpeta autocontenida** con su `main.py` y su `requirements.txt`.
Se corren **en orden**, de a uno. Empezás limpiando (`s0`) y construís de `s1` a `s7`.

```
s0_delete_all       borra todo (empezar/terminar limpio)
s1_vector_bucket    base vectorial (S3 Vectors)
s2_knowledge_base   Knowledge Base + data source
s3_ingest_and_query ingestar y preguntar (RAG, el "aha")
s4_agent            el agente Strands (local)
s4_1_memory         chatear con memoria de corto plazo (AgentCore Memory)
s5_deploy_runtime   deploy a AgentCore Runtime
s6_slack_bridge     Lambda-puente + API Gateway (Slack)
s7_auto_ingest      ingesta automática cada 30 min
```

---

## 0 · Setup (una sola vez)

Usás una **cuenta de prueba** ya provista, con la consola de AWS abierta.
Asegurate de tener la región **us-east-1** seleccionada (arriba a la derecha).

### Opción A · CloudShell — todo en la consola (recomendado)

En la consola abrí **CloudShell** (ícono de terminal, arriba a la derecha).
Ya trae tus credenciales: no hay que configurar nada.

```bash
git clone https://github.com/gastonzarate/agent-core-habla-con-tu-slack.git && cd agent-core-habla-con-tu-slack/workshop
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Opción B · Local (con credenciales provistas)

En tu máquina:

```bash
git clone https://github.com/gastonzarate/agent-core-habla-con-tu-slack.git && cd agent-core-habla-con-tu-slack/workshop
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
aws configure     # pegá Access Key / Secret de la cuenta de prueba
# (o si te dan SSO: aws sso login --profile <perfil> && export AWS_PROFILE=<perfil>)
```

### Verificá el acceso (en cualquiera de las dos)

```bash
aws sts get-caller-identity       # debe mostrar la cuenta de prueba
```

**Modelos en Bedrock**: la cuenta de prueba ya viene con **Titan Text
Embeddings v2** y **Claude Sonnet 4.6** habilitados en `us-east-1`.

### Secretos de Slack (`.env`)

Los pasos que tocan Slack (**3** y **6**) leen los secretos de variables de
entorno. Para no exportarlos a mano, copiá el ejemplo, completalo **una vez** y
cargalo en la terminal:

```bash
cp .env.example .env            # editá .env con los datos de tu Slack App
set -a; source .env; set +a     # cargá las variables (antes de los pasos 3 y 6)
```

`.env` tiene `SLACK_SIGNING_SECRET`, `SLACK_BOT_TOKEN` y `SLACK_BOT_USER_ID`
(de dónde sacar cada uno está comentado en `.env.example`). Si **cambiás de
Slack App**, editás `.env` y volvés a correr `set -a; source .env; set +a`.
El `.env` está gitignored — no se sube.

> ⚠️ **Invitá el bot a los canales** que quieras indexar: en cada canal,
> `/invite @tu-bot`. Slack solo deja leer canales donde el bot es **miembro**
> — si no está en ninguno, la ingesta (pasos 3 y 7) trae **0 mensajes**.

> **Todos los pasos se corren desde `workshop/`** con `python -m <carpeta>.main`
> (así encuentran `constants.py`). No hace falta `cd` a cada carpeta.

---

## Paso 0 · Borrar todo (empezar limpio)

```bash
python -m s0_delete_all.main
```

## Paso 1 · Base vectorial (S3 Vectors)

```bash
python -m s1_vector_bucket.main
```
Crea el vector bucket y el índice (dim 1024, cosine).

## Paso 2 · Knowledge Base

```bash
python -m s2_knowledge_base.main
```
Crea el IAM role, el Knowledge Base sobre S3 Vectors y una data source CUSTOM.

## Paso 3 · Ingestar y preguntar (el "aha")

```bash
python -m s3_ingest_and_query.main
python -m s3_ingest_and_query.main "¿qué pasó con el deploy?"   # con tu pregunta
```
Con el `.env` cargado (con `SLACK_BOT_TOKEN`), ingesta el **último día real de
Slack** y pregunta. Sin token, usa mensajes de ejemplo. El retrieval encuentra
el correcto por significado, con su cita.

**Solo preguntar** (sin re-ingestar) — para probar varias preguntas en vivo:
```bash
python -m s3_1_query.main "¿qué cliente renovó contrato?"
python -m s3_1_query.main "¿cuándo es el deploy?"
```

## Paso 4 · El agente (local)

```bash
python -m s4_agent.main
```
El agente decide usar la tool `ask_kb` y Claude redacta la respuesta.

## Paso 4.1 · Chatear con memoria (corto plazo)

```bash
python -m s4_1_memory.main
```
Chat interactivo. Le suma **AgentCore Memory** (corto plazo): guarda cada turno
y se lo pasa como contexto al siguiente. Probá en orden:
```
vos> ¿qué se decidió del deploy?
vos> ¿y eso cuándo era?      # entiende que seguís hablando del deploy
```
La primera corrida crea el recurso de memoria (~1-2 min). Se borra con el paso 0.

## Paso 5 · Deploy a AgentCore Runtime

Instalá el CLI de deploy:
```bash
# CloudShell / Linux / Python < 3.14:
pip install bedrock-agentcore-starter-toolkit==0.3.9

# Local con Python 3.14 (el CLI crashea ahí): instalalo con 3.13
uv tool install --python 3.13 bedrock-agentcore-starter-toolkit==0.3.9
```
Luego:
```bash
python -m s5_deploy_runtime.main            # muestra los comandos
python -m s5_deploy_runtime.main --run      # crea el role y despliega (1-2 min)
```

## Paso 6 · Conectar Slack

Con el `.env` cargado (los 3 secretos de Slack — ver setup), corré:
```bash
python -m s6_slack_bridge.main
```
Imprime la **Request URL**. Pegala en la Slack App (Event Subscriptions +
Slash Commands) y reinstalá la app. (Ver `utils/manifest.yaml` para los scopes.)

## Paso 7 · Ingesta automática

```bash
python -m s7_auto_ingest.main
```
Crea la regla de EventBridge (cada 30 min) y dispara una ingesta de prueba.

---

## Probarlo en Slack

En un canal donde esté el bot:
```
@slack-rag ¿de qué se viene hablando en este canal?
```

## Empezar de nuevo

```bash
python -m s0_delete_all.main
```
Borra todo para volver a arrancar (útil porque el sandbox se resetea a diario).
