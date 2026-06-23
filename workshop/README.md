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

Usás una **cuenta de prueba** ya provista, con la consola de AWS abierta.
Asegurate de tener la región **us-east-1** seleccionada (arriba a la derecha).

### Opción A · CloudShell — todo en la consola (recomendado)

En la consola abrí **CloudShell** (ícono de terminal, arriba a la derecha).
Ya trae tus credenciales: no hay que configurar nada.

```bash
git clone <URL-del-repo> && cd poc_aws_slack/workshop
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Opción B · Local (con credenciales provistas)

En tu máquina:

```bash
git clone <URL-del-repo> && cd poc_aws_slack/workshop
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
```
Ingesta unos mensajes y pregunta: el retrieval encuentra el correcto, con cita.

## Paso 4 · El agente (local)

```bash
python -m s4_agent.main
```
El agente decide usar la tool `ask_kb` y Claude redacta la respuesta.

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

Necesitás los secretos de tu Slack App (Signing Secret y Bot Token):
```bash
export SLACK_SIGNING_SECRET=...        # Basic Information → App Credentials
export SLACK_BOT_TOKEN=xoxb-...        # OAuth & Permissions (tras instalar)
export SLACK_BOT_USER_ID=U...          # auth.test, o el user id del bot
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
