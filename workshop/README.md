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
s5_deploy_runtime   deploy a AgentCore Runtime
s6_slack_bridge     Lambda-puente + API Gateway (Slack)
s7_auto_ingest      ingesta automática cada 30 min
```

---

## 0 · Setup (una sola vez)

**Python + entorno virtual:**
```bash
cd workshop
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install boto3
```

**Login a AWS (SSO):**
```bash
aws sso login --profile sandbox
export AWS_PROFILE=sandbox
aws sts get-caller-identity       # confirma que estás logueado
```

**Acceso a modelos en Bedrock** (consola → Bedrock → Model access): habilitá
**Titan Text Embeddings v2** y **Claude Sonnet 4.6** en `us-east-1`.

---

## Paso 0 · Borrar todo (empezar limpio)

```bash
cd s0_delete_all
python main.py
```

---

## Paso 1 · Base vectorial (S3 Vectors)

```bash
cd ../s1_vector_bucket
python main.py
```
Crea el vector bucket y el índice (dim 1024, cosine).

## Paso 2 · Knowledge Base

```bash
cd ../s2_knowledge_base
python main.py
```
Crea el IAM role, el Knowledge Base sobre S3 Vectors y una data source CUSTOM.

## Paso 3 · Ingestar y preguntar (el "aha")

```bash
cd ../s3_ingest_and_query
python main.py
```
Ingesta unos mensajes y pregunta: el retrieval encuentra el correcto, con cita.

## Paso 4 · El agente (local)

```bash
cd ../s4_agent
pip install -r requirements.txt        # strands, bedrock-agentcore, slack_sdk
python main.py
```
El agente decide usar la tool `ask_kb` y Claude redacta la respuesta.

## Paso 5 · Deploy a AgentCore Runtime

```bash
cd ../s5_deploy_runtime
pip install bedrock-agentcore-starter-toolkit
python main.py            # muestra los comandos
python main.py --run      # crea el role y despliega (1-2 min)
```

## Paso 6 · Conectar Slack

Necesitás los secretos de tu Slack App (Signing Secret y Bot Token):
```bash
cd ../s6_slack_bridge
export SLACK_SIGNING_SECRET=...        # Basic Information → App Credentials
export SLACK_BOT_TOKEN=xoxb-...        # OAuth & Permissions (tras instalar)
export SLACK_BOT_USER_ID=U...          # auth.test, o el user id del bot
python main.py
```
Imprime la **Request URL**. Pegala en la Slack App (Event Subscriptions +
Slash Commands) y reinstalá la app. (Ver `slack/manifest.yaml` para los scopes.)

## Paso 7 · Ingesta automática

```bash
cd ../s7_auto_ingest
python main.py
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
cd s0_delete_all && python main.py
```
Borra todo para volver a arrancar (útil porque el sandbox se resetea a diario).
