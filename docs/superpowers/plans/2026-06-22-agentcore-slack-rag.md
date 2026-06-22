# Hablá con tu Slack — AgentCore RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir un agente serverless en AWS que ingesta mensajes de Slack a un Bedrock Knowledge Base (S3 Vectors) y responde preguntas en lenguaje natural con citas, disparado desde Slack vía una Lambda-puente fina.

**Architecture:** Strands Agent hosteado en AgentCore Runtime con dos tools — `ingest_slack` (lee historia vía Slack API con token de AgentCore Identity, normaliza y empuja al KB con ingestión directa) y `ask_kb` (recupera del KB y deja que Claude responda con citas). Una Lambda-puente recibe los slash commands de Slack (valida firma, ack <3s, invoca async). El vector store es S3 Vectors detrás de un Bedrock Knowledge Base con embeddings Titan v2.

**Tech Stack:** Python 3.12, `strands-agents`, `bedrock-agentcore`, `bedrock-agentcore-starter-toolkit`, `boto3`, `slack_sdk`, pytest. Servicios: AgentCore Runtime + Identity, Bedrock Knowledge Bases, S3 Vectors, Bedrock (Titan v2 + Claude), Lambda, API Gateway.

## Global Constraints

- **Región AWS:** `us-west-2` (vía env `AWS_REGION`; confirmar disponibilidad de AgentCore + S3 Vectors en la región del sandbox antes de empezar).
- **Python:** 3.12.
- **Modelo embeddings:** `amazon.titan-embed-text-v2:0`, dimensión **1024**, `distanceMetric = cosine`, `dataType = float32`.
- **Modelo LLM:** `us.anthropic.claude-sonnet-4-20250514-v1:0` (inference profile). Confirmar el ID exacto disponible en el catálogo de Bedrock de la región antes de pinear.
- **Prefijo de nombres de recursos:** `slackrag` (ej: `slackrag-vectors`, `slackrag-kb`, `slackrag-bridge`).
- **SigV4 signing name de AgentCore data plane:** `bedrock-agentcore`.
- **Límite de ingestión directa:** máx. 25 documentos por llamada a `ingest_knowledge_base_documents`.
- **Todo el código nuevo vive en el repo `poc_aws_slack/`** con la estructura de archivos de abajo.

---

## File Structure

```
poc_aws_slack/
├── agent/
│   ├── __init__.py
│   ├── agent.py            # Strands agent + AgentCore entrypoint (runtime)
│   ├── normalize.py        # Slack raw → documentos normalizados (lógica pura)
│   ├── kb.py               # build_kb_documents + retrieve + format_results
│   ├── slack_reader.py     # lee historia de Slack con token de Identity
│   └── requirements.txt
├── bridge/
│   ├── handler.py          # Lambda-puente: verify firma, challenge, ack, invoke async
│   ├── slack_sig.py        # verify_slack_signature (lógica pura)
│   ├── blocks.py           # build_slack_response (Block Kit, lógica pura)
│   └── requirements.txt
├── infra/
│   ├── config.py           # nombres, región, ARNs derivados (lógica pura)
│   ├── setup_vectors.py    # crea vector bucket + index (S3 Vectors)
│   ├── setup_kb.py         # crea KB + custom data source
│   └── setup_identity.py   # crea Slack OAuth2 credential provider
├── slack/
│   └── manifest.yaml       # manifest de la Slack App (slash commands + scopes)
├── scripts/
│   └── seed_demo.py        # pre-carga data de ejemplo al KB para el demo
├── tests/
│   ├── test_normalize.py
│   ├── test_kb.py
│   ├── test_slack_sig.py
│   ├── test_blocks.py
│   ├── test_config.py
│   └── test_bridge_handler.py
├── requirements-dev.txt    # pytest, boto3 (para tests + provisioning)
└── README.md
```

**Decisión de diseño (flag):** la lectura de Slack usa AgentCore Identity (`@requires_access_token`) + `slack_sdk` directo, NO Gateway/MCP. Gateway queda como extensión avanzada fuera de este plan.

---

### Task 1: Scaffolding + config module

**Files:**
- Create: `requirements-dev.txt`, `agent/__init__.py`, `infra/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `infra/config.py` con `Config` (dataclass) y `load_config() -> Config`. Campos: `region: str`, `prefix: str`, `vector_bucket: str`, `vector_index: str`, `kb_name: str`, `embedding_model_arn: str`, `embedding_dim: int`. Y helper `embedding_model_arn(region: str) -> str`.

- [ ] **Step 1: Crear `requirements-dev.txt`**

```
boto3>=1.40
pytest>=8.0
slack_sdk>=3.27
```

- [ ] **Step 2: Crear venv e instalar dev deps**

Run: `cd /Users/gastonzarate/Documents/Code/poc_aws_slack && python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt`
Expected: instala sin error.

- [ ] **Step 3: Escribir el test que falla** (`tests/test_config.py`)

```python
from infra.config import load_config, embedding_model_arn


def test_embedding_model_arn_uses_region():
    arn = embedding_model_arn("us-west-2")
    assert arn == "arn:aws:bedrock:us-west-2::foundation-model/amazon.titan-embed-text-v2:0"


def test_load_config_defaults():
    cfg = load_config(region="us-west-2", prefix="slackrag")
    assert cfg.region == "us-west-2"
    assert cfg.vector_bucket == "slackrag-vectors"
    assert cfg.vector_index == "slackrag-index"
    assert cfg.kb_name == "slackrag-kb"
    assert cfg.embedding_dim == 1024
    assert cfg.embedding_model_arn.endswith("amazon.titan-embed-text-v2:0")
```

- [ ] **Step 4: Correr el test y verificar que falla**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'infra'`.

- [ ] **Step 5: Crear `agent/__init__.py` vacío e implementar `infra/config.py`**

```python
# infra/config.py
from dataclasses import dataclass


def embedding_model_arn(region: str) -> str:
    return f"arn:aws:bedrock:{region}::foundation-model/amazon.titan-embed-text-v2:0"


@dataclass(frozen=True)
class Config:
    region: str
    prefix: str
    vector_bucket: str
    vector_index: str
    kb_name: str
    embedding_model_arn: str
    embedding_dim: int = 1024


def load_config(region: str = "us-west-2", prefix: str = "slackrag") -> Config:
    return Config(
        region=region,
        prefix=prefix,
        vector_bucket=f"{prefix}-vectors",
        vector_index=f"{prefix}-index",
        kb_name=f"{prefix}-kb",
        embedding_model_arn=embedding_model_arn(region),
    )
```

Crear también `infra/__init__.py` y `tests/__init__.py` vacíos, y un `conftest.py` en la raíz o usar `pythonpath`. Agregar `pyproject.toml` o `pytest.ini` con:

```ini
# pytest.ini
[pytest]
pythonpath = .
```

- [ ] **Step 6: Correr el test y verificar que pasa**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: PASS (2 passed).

- [ ] **Step 7: Commit**

```bash
git init && git add -A && git commit -m "feat: scaffolding + config module"
```

---

### Task 2: Normalización de mensajes de Slack (lógica pura, TDD)

**Files:**
- Create: `agent/normalize.py`
- Test: `tests/test_normalize.py`

**Interfaces:**
- Produces: `normalize_messages(messages: list[dict], user_map: dict[str, str], channel: str) -> list[dict]`. Cada doc de salida: `{"id": str, "text": str, "channel": str, "ts": str, "author": str}`. Resuelve `user` ID → nombre vía `user_map`, antepone `"<autor>: "` al texto, descarta mensajes sin `text` o de tipo no `message`, y genera `id` determinístico `f"{channel}-{ts}"`.

- [ ] **Step 1: Escribir el test que falla** (`tests/test_normalize.py`)

```python
from agent.normalize import normalize_messages

USER_MAP = {"U1": "ana", "U2": "beto"}


def test_resolves_author_and_builds_id():
    msgs = [{"type": "message", "user": "U1", "text": "deployé a prod", "ts": "1700000000.0001"}]
    out = normalize_messages(msgs, USER_MAP, channel="C9")
    assert out == [{
        "id": "C9-1700000000.0001",
        "text": "ana: deployé a prod",
        "channel": "C9",
        "ts": "1700000000.0001",
        "author": "ana",
    }]


def test_skips_non_messages_and_empty_text():
    msgs = [
        {"type": "channel_join", "user": "U1", "ts": "1.0"},
        {"type": "message", "user": "U2", "text": "", "ts": "2.0"},
        {"type": "message", "user": "U2", "text": "hola", "ts": "3.0"},
    ]
    out = normalize_messages(msgs, USER_MAP, channel="C9")
    assert len(out) == 1
    assert out[0]["text"] == "beto: hola"


def test_unknown_user_falls_back_to_id():
    msgs = [{"type": "message", "user": "U999", "text": "hey", "ts": "4.0"}]
    out = normalize_messages(msgs, USER_MAP, channel="C9")
    assert out[0]["author"] == "U999"
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `.venv/bin/python -m pytest tests/test_normalize.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'agent.normalize'`.

- [ ] **Step 3: Implementar `agent/normalize.py`**

```python
# agent/normalize.py
def normalize_messages(messages, user_map, channel):
    docs = []
    for m in messages:
        if m.get("type") != "message":
            continue
        text = (m.get("text") or "").strip()
        if not text:
            continue
        uid = m.get("user", "")
        author = user_map.get(uid, uid)
        ts = m["ts"]
        docs.append({
            "id": f"{channel}-{ts}",
            "text": f"{author}: {text}",
            "channel": channel,
            "ts": ts,
            "author": author,
        })
    return docs
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `.venv/bin/python -m pytest tests/test_normalize.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add agent/normalize.py tests/test_normalize.py && git commit -m "feat: Slack message normalization"
```

---

### Task 3: Builder de documentos KB + parser de resultados (lógica pura, TDD)

**Files:**
- Create: `agent/kb.py` (solo las funciones puras en esta task; los clientes boto3 se agregan en Task 7-bis si hace falta)
- Test: `tests/test_kb.py`

**Interfaces:**
- Consumes: docs normalizados de `normalize_messages` (Task 2).
- Produces:
  - `build_kb_documents(docs: list[dict]) -> list[dict]` — arma el payload `documents` para `ingest_knowledge_base_documents` (sourceType `IN_LINE`, type `TEXT`, con metadata inline `channel`, `ts`, `author`).
  - `format_retrieval_results(resp: dict) -> tuple[str, list[dict]]` — del response de `retrieve`, devuelve `(context_text, citations)`. `context_text` = chunks unidos por `"\n\n"`. `citations` = lista de `{"id": str, "score": float}` desde `location.customDocumentLocation.id`.

- [ ] **Step 1: Escribir el test que falla** (`tests/test_kb.py`)

```python
from agent.kb import build_kb_documents, format_retrieval_results


def test_build_kb_documents_inline_text_with_metadata():
    docs = [{"id": "C9-1.0", "text": "ana: hola", "channel": "C9", "ts": "1.0", "author": "ana"}]
    out = build_kb_documents(docs)
    assert out == [{
        "content": {
            "dataSourceType": "CUSTOM",
            "custom": {
                "customDocumentIdentifier": {"id": "C9-1.0"},
                "sourceType": "IN_LINE",
                "inlineContent": {
                    "type": "TEXT",
                    "textContent": {"data": "ana: hola"},
                },
            },
        },
        "metadata": {
            "type": "IN_LINE_ATTRIBUTE",
            "inlineAttributes": [
                {"key": "channel", "value": {"type": "STRING", "stringValue": "C9"}},
                {"key": "ts", "value": {"type": "STRING", "stringValue": "1.0"}},
                {"key": "author", "value": {"type": "STRING", "stringValue": "ana"}},
            ],
        },
    }]


def test_format_retrieval_results():
    resp = {
        "retrievalResults": [
            {"content": {"type": "TEXT", "text": "ana: deployé a prod"},
             "location": {"type": "CUSTOM", "customDocumentLocation": {"id": "C9-1.0"}},
             "score": 0.91},
            {"content": {"type": "TEXT", "text": "beto: ok"},
             "location": {"type": "CUSTOM", "customDocumentLocation": {"id": "C9-2.0"}},
             "score": 0.80},
        ]
    }
    context, citations = format_retrieval_results(resp)
    assert context == "ana: deployé a prod\n\nbeto: ok"
    assert citations == [{"id": "C9-1.0", "score": 0.91}, {"id": "C9-2.0", "score": 0.80}]
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `.venv/bin/python -m pytest tests/test_kb.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'agent.kb'`.

- [ ] **Step 3: Implementar las funciones puras en `agent/kb.py`**

```python
# agent/kb.py
def build_kb_documents(docs):
    out = []
    for d in docs:
        out.append({
            "content": {
                "dataSourceType": "CUSTOM",
                "custom": {
                    "customDocumentIdentifier": {"id": d["id"]},
                    "sourceType": "IN_LINE",
                    "inlineContent": {
                        "type": "TEXT",
                        "textContent": {"data": d["text"]},
                    },
                },
            },
            "metadata": {
                "type": "IN_LINE_ATTRIBUTE",
                "inlineAttributes": [
                    {"key": "channel", "value": {"type": "STRING", "stringValue": d["channel"]}},
                    {"key": "ts", "value": {"type": "STRING", "stringValue": d["ts"]}},
                    {"key": "author", "value": {"type": "STRING", "stringValue": d["author"]}},
                ],
            },
        })
    return out


def format_retrieval_results(resp):
    results = resp.get("retrievalResults", [])
    context = "\n\n".join(r["content"]["text"] for r in results)
    citations = [
        {"id": r["location"]["customDocumentLocation"]["id"], "score": r["score"]}
        for r in results
    ]
    return context, citations
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `.venv/bin/python -m pytest tests/test_kb.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add agent/kb.py tests/test_kb.py && git commit -m "feat: KB document builder + retrieval parser"
```

---

### Task 4: Verificación de firma de Slack (lógica pura, TDD)

**Files:**
- Create: `bridge/slack_sig.py`, `bridge/__init__.py`
- Test: `tests/test_slack_sig.py`

**Interfaces:**
- Produces: `verify_slack_signature(signing_secret: str, timestamp: str, raw_body: str, signature: str) -> bool`. Implementa el esquema oficial de Slack: `v0:{timestamp}:{raw_body}`, HMAC-SHA256 con `signing_secret`, comparado con `signature` (`v0=...`) vía `hmac.compare_digest`.

- [ ] **Step 1: Escribir el test que falla** (`tests/test_slack_sig.py`)

```python
import hashlib
import hmac
from bridge.slack_sig import verify_slack_signature

SECRET = "8f742231b10e8888abcd99yyyzzz85a5"


def _sign(ts, body):
    base = f"v0:{ts}:{body}".encode()
    digest = hmac.new(SECRET.encode(), base, hashlib.sha256).hexdigest()
    return f"v0={digest}"


def test_valid_signature_passes():
    ts, body = "1531420618", "token=xyz&command=%2Fask"
    assert verify_slack_signature(SECRET, ts, body, _sign(ts, body)) is True


def test_tampered_body_fails():
    ts, body = "1531420618", "token=xyz&command=%2Fask"
    sig = _sign(ts, body)
    assert verify_slack_signature(SECRET, ts, "token=HACKED", sig) is False


def test_wrong_secret_fails():
    ts, body = "1531420618", "x=1"
    assert verify_slack_signature("otro-secret", ts, body, _sign(ts, body)) is False
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `.venv/bin/python -m pytest tests/test_slack_sig.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'bridge.slack_sig'`.

- [ ] **Step 3: Implementar `bridge/slack_sig.py`** (crear `bridge/__init__.py` vacío)

```python
# bridge/slack_sig.py
import hashlib
import hmac


def verify_slack_signature(signing_secret, timestamp, raw_body, signature):
    base = f"v0:{timestamp}:{raw_body}".encode()
    expected = "v0=" + hmac.new(signing_secret.encode(), base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `.venv/bin/python -m pytest tests/test_slack_sig.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add bridge/slack_sig.py bridge/__init__.py tests/test_slack_sig.py && git commit -m "feat: Slack signature verification"
```

---

### Task 5: Block Kit de respuesta (lógica pura, TDD)

**Files:**
- Create: `bridge/blocks.py`
- Test: `tests/test_blocks.py`

**Interfaces:**
- Consumes: `answer: str`, `citations: list[dict]` (de `format_retrieval_results`, Task 3).
- Produces: `build_slack_response(answer: str, citations: list[dict]) -> dict` — payload para postear a `response_url`: `{"response_type": "in_channel", "blocks": [...]}` con un `section` para la respuesta y un `context` con las citas (los `id`).

- [ ] **Step 1: Escribir el test que falla** (`tests/test_blocks.py`)

```python
from bridge.blocks import build_slack_response


def test_response_has_answer_and_citations():
    resp = build_slack_response("Se deployó el viernes.", [{"id": "C9-1.0", "score": 0.9}])
    assert resp["response_type"] == "in_channel"
    blocks = resp["blocks"]
    assert blocks[0]["type"] == "section"
    assert "Se deployó el viernes." in blocks[0]["text"]["text"]
    # último bloque = contexto con la cita
    assert blocks[-1]["type"] == "context"
    assert "C9-1.0" in blocks[-1]["elements"][0]["text"]


def test_no_citations_omits_context_block():
    resp = build_slack_response("No encontré nada.", [])
    assert all(b["type"] != "context" for b in resp["blocks"])
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `.venv/bin/python -m pytest tests/test_blocks.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `bridge/blocks.py`**

```python
# bridge/blocks.py
def build_slack_response(answer, citations):
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": answer}}]
    if citations:
        refs = ", ".join(c["id"] for c in citations)
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"📎 Fuentes: {refs}"}],
        })
    return {"response_type": "in_channel", "blocks": blocks}
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `.venv/bin/python -m pytest tests/test_blocks.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add bridge/blocks.py tests/test_blocks.py && git commit -m "feat: Slack Block Kit response builder"
```

---

### Task 6: Provisionar S3 Vectors (script + verificación)

**Files:**
- Create: `infra/setup_vectors.py`

**Interfaces:**
- Consumes: `Config` (Task 1).
- Produces: `infra/setup_vectors.py` ejecutable que crea el vector bucket y el index, e imprime `vectorBucketArn` e `indexArn`. Función `provision_vectors(cfg) -> dict` con esas claves.

> Nota: este task NO es unit-test (toca AWS real). La verificación es ejecutarlo y confirmar los ARNs.

- [ ] **Step 1: Implementar `infra/setup_vectors.py`**

```python
# infra/setup_vectors.py
import boto3
from infra.config import load_config


def provision_vectors(cfg):
    s3v = boto3.client("s3vectors", region_name=cfg.region)
    bucket = s3v.create_vector_bucket(vectorBucketName=cfg.vector_bucket)
    index = s3v.create_index(
        vectorBucketName=cfg.vector_bucket,
        indexName=cfg.vector_index,
        dataType="float32",
        dimension=cfg.embedding_dim,
        distanceMetric="cosine",
    )
    return {
        "vectorBucketArn": bucket["vectorBucketArn"],
        "indexArn": index["indexArn"],
    }


if __name__ == "__main__":
    cfg = load_config()
    out = provision_vectors(cfg)
    print("vectorBucketArn:", out["vectorBucketArn"])
    print("indexArn:", out["indexArn"])
```

- [ ] **Step 2: Ejecutar y verificar**

Run: `.venv/bin/python -m infra.setup_vectors`
Expected: imprime `vectorBucketArn: arn:aws:s3vectors:...` e `indexArn: arn:aws:s3vectors:.../index/...`. Guardar ambos ARNs (se usan en Task 7).
Si falla por `s3vectors` no disponible en la región → confirmar región del sandbox (Global Constraints).

- [ ] **Step 3: Commit**

```bash
git add infra/setup_vectors.py && git commit -m "feat: provision S3 Vectors bucket + index"
```

---

### Task 7: Provisionar Knowledge Base + custom data source (script + verificación)

**Files:**
- Create: `infra/setup_kb.py`

**Interfaces:**
- Consumes: `Config` (Task 1), `vectorBucketArn` + `indexArn` (Task 6), un IAM role ARN para el KB (pre-creado en el sandbox; pasar por env `KB_ROLE_ARN`).
- Produces: `provision_kb(cfg, vector_bucket_arn, index_arn, role_arn) -> dict` con `knowledgeBaseId` y `dataSourceId`. Imprime ambos.

> El IAM role del KB debe permitir `bedrock:InvokeModel` sobre Titan v2 y acceso a S3 Vectors. En el workshop el role lo provee el sandbox de Craftech. Pasar su ARN por `KB_ROLE_ARN`.

- [ ] **Step 1: Implementar `infra/setup_kb.py`**

```python
# infra/setup_kb.py
import os
import boto3
from infra.config import load_config


def provision_kb(cfg, vector_bucket_arn, index_arn, role_arn):
    ba = boto3.client("bedrock-agent", region_name=cfg.region)
    kb = ba.create_knowledge_base(
        name=cfg.kb_name,
        roleArn=role_arn,
        knowledgeBaseConfiguration={
            "type": "VECTOR",
            "vectorKnowledgeBaseConfiguration": {
                "embeddingModelArn": cfg.embedding_model_arn,
                "embeddingModelConfiguration": {
                    "bedrockEmbeddingModelConfiguration": {
                        "dimensions": cfg.embedding_dim,
                        "embeddingDataType": "FLOAT32",
                    }
                },
            },
        },
        storageConfiguration={
            "type": "S3_VECTORS",
            "s3VectorsConfiguration": {
                "vectorBucketArn": vector_bucket_arn,
                "indexArn": index_arn,
            },
        },
    )
    kb_id = kb["knowledgeBase"]["knowledgeBaseId"]
    ds = ba.create_data_source(
        knowledgeBaseId=kb_id,
        name=f"{cfg.prefix}-direct",
        dataSourceConfiguration={"type": "CUSTOM"},
    )
    return {
        "knowledgeBaseId": kb_id,
        "dataSourceId": ds["dataSource"]["dataSourceId"],
    }


if __name__ == "__main__":
    cfg = load_config()
    out = provision_kb(
        cfg,
        vector_bucket_arn=os.environ["VECTOR_BUCKET_ARN"],
        index_arn=os.environ["INDEX_ARN"],
        role_arn=os.environ["KB_ROLE_ARN"],
    )
    print("knowledgeBaseId:", out["knowledgeBaseId"])
    print("dataSourceId:", out["dataSourceId"])
```

- [ ] **Step 2: Ejecutar y verificar**

Run:
```bash
VECTOR_BUCKET_ARN=<arn-task6> INDEX_ARN=<arn-task6> KB_ROLE_ARN=<arn-sandbox> \
  .venv/bin/python -m infra.setup_kb
```
Expected: imprime `knowledgeBaseId:` y `dataSourceId:`. Guardar ambos.
Verificar estado ACTIVE: `aws bedrock-agent get-knowledge-base --knowledge-base-id <id> --region us-west-2`.

- [ ] **Step 3: Commit**

```bash
git add infra/setup_kb.py && git commit -m "feat: provision Knowledge Base + custom data source"
```

---

### Task 8: Provisionar AgentCore Identity — Slack OAuth provider (script + verificación)

**Files:**
- Create: `infra/setup_identity.py`, `slack/manifest.yaml`

**Interfaces:**
- Consumes: `Config`, Slack `client_id` + `client_secret` (de la Slack App, por env).
- Produces: `provision_slack_identity(cfg, client_id, client_secret) -> dict` con `credentialProviderArn` y `callbackUrl`. Imprime ambos. El `callbackUrl` se registra como Redirect URL en la Slack App.

- [ ] **Step 1: Crear `slack/manifest.yaml`** (manifest de la Slack App)

```yaml
display_information:
  name: Hablá con tu Slack
features:
  bot_user:
    display_name: slack-rag
    always_online: true
  slash_commands:
    - command: /ask
      description: Preguntale a tu Slack
      usage_hint: "¿qué se decidió sobre el deploy?"
    - command: /ingest
      description: Indexar la historia del canal actual
oauth_config:
  scopes:
    bot:
      - channels:history
      - channels:read
      - users:read
      - chat:write
settings:
  org_deploy_enabled: false
  socket_mode_enabled: false
```

- [ ] **Step 2: Implementar `infra/setup_identity.py`**

```python
# infra/setup_identity.py
import os
import boto3
from infra.config import load_config


def provision_slack_identity(cfg, client_id, client_secret):
    c = boto3.client("bedrock-agentcore-control", region_name=cfg.region)
    resp = c.create_oauth2_credential_provider(
        name=f"{cfg.prefix}-slack",
        credentialProviderVendor="SlackOauth2",
        oauth2ProviderConfigInput={
            "slackOauth2ProviderConfig": {
                "clientId": client_id,
                "clientSecret": client_secret,
            }
        },
    )
    return {
        "credentialProviderArn": resp["credentialProviderArn"],
        "callbackUrl": resp.get("callbackUrl") or resp.get("oauth2CallbackUrl"),
    }


if __name__ == "__main__":
    cfg = load_config()
    out = provision_slack_identity(
        cfg,
        client_id=os.environ["SLACK_CLIENT_ID"],
        client_secret=os.environ["SLACK_CLIENT_SECRET"],
    )
    print("credentialProviderArn:", out["credentialProviderArn"])
    print("callbackUrl (registrar como Redirect URL en la Slack App):", out["callbackUrl"])
```

> **Flag (verificación pendiente):** el nombre exacto del campo del callback URL en el response (`callbackUrl` vs otra clave) no quedó 100% confirmado. El código lee ambos por las dudas; confirmar imprimiendo el response completo la primera vez.

- [ ] **Step 3: Ejecutar y verificar**

Run:
```bash
SLACK_CLIENT_ID=<...> SLACK_CLIENT_SECRET=<...> .venv/bin/python -m infra.setup_identity
```
Expected: imprime `credentialProviderArn:` y el `callbackUrl`. Registrar el callbackUrl como Redirect URL en api.slack.com → OAuth & Permissions.

- [ ] **Step 4: Commit**

```bash
git add infra/setup_identity.py slack/manifest.yaml && git commit -m "feat: provision Slack OAuth identity provider + Slack manifest"
```

---

### Task 9: El agente Strands + tools + entrypoint AgentCore

**Files:**
- Create: `agent/slack_reader.py`, `agent/agent.py`, `agent/requirements.txt`
- Modify: `agent/kb.py` (agregar clientes boto3 `ingest_documents` y `retrieve`)

**Interfaces:**
- Consumes: `normalize_messages` (Task 2), `build_kb_documents` + `format_retrieval_results` (Task 3), token de Identity, `KB_ID` + `DATA_SOURCE_ID` (env).
- Produces:
  - `agent/kb.py`: `ingest_documents(region, kb_id, ds_id, kb_docs) -> int` (cantidad ingestada, en batches de 25) y `retrieve(region, kb_id, query, k=5) -> dict`.
  - `agent/slack_reader.py`: `read_channel_history(token, channel, limit=200) -> tuple[list[dict], dict]` → `(messages, user_map)` usando `slack_sdk`.
  - `agent/agent.py`: agente Strands con tools `ingest_slack(channel)` y `ask_kb(question)`, envuelto en `BedrockAgentCoreApp`.

- [ ] **Step 1: Crear `agent/requirements.txt`**

```
bedrock-agentcore
strands-agents
boto3
slack_sdk
```

- [ ] **Step 2: Agregar clientes boto3 a `agent/kb.py`** (sin romper las funciones puras existentes)

```python
# agent/kb.py  (agregar al final)
import boto3


def ingest_documents(region, kb_id, ds_id, kb_docs):
    ba = boto3.client("bedrock-agent", region_name=region)
    total = 0
    for i in range(0, len(kb_docs), 25):  # límite: 25 docs por llamada
        batch = kb_docs[i:i + 25]
        ba.ingest_knowledge_base_documents(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id,
            documents=batch,
        )
        total += len(batch)
    return total


def retrieve(region, kb_id, query, k=5):
    rt = boto3.client("bedrock-agent-runtime", region_name=region)
    return rt.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={"text": query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {"numberOfResults": k, "overrideSearchType": "SEMANTIC"}
        },
    )
```

- [ ] **Step 3: Implementar `agent/slack_reader.py`**

```python
# agent/slack_reader.py
from slack_sdk import WebClient


def read_channel_history(token, channel, limit=200):
    client = WebClient(token=token)
    history = client.conversations_history(channel=channel, limit=limit)
    messages = history.get("messages", [])
    user_map = {}
    for u in client.users_list().get("members", []):
        user_map[u["id"]] = u.get("profile", {}).get("display_name") or u.get("name") or u["id"]
    return messages, user_map
```

- [ ] **Step 4: Implementar `agent/agent.py`**

```python
# agent/agent.py
import os
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.identity.auth import requires_access_token
from strands import Agent, tool
from strands.models import BedrockModel

from agent.normalize import normalize_messages
from agent.kb import build_kb_documents, format_retrieval_results, ingest_documents, retrieve
from agent.slack_reader import read_channel_history

REGION = os.environ.get("AWS_REGION", "us-west-2")
KB_ID = os.environ["KB_ID"]
DATA_SOURCE_ID = os.environ["DATA_SOURCE_ID"]
SLACK_PROVIDER = os.environ.get("SLACK_PROVIDER", "slackrag-slack")
MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")

app = BedrockAgentCoreApp()
_model = BedrockModel(model_id=MODEL_ID, region_name=REGION, temperature=0.2)


@requires_access_token(
    provider_name=SLACK_PROVIDER,
    scopes=["channels:history", "channels:read", "users:read"],
    auth_flow="USER_FEDERATION",
    on_auth_url=lambda url: print("Autorizá Slack acá:\n" + url),
)
def _get_slack_token(*, access_token: str) -> str:
    return access_token


@tool
def ingest_slack(channel: str) -> str:
    """Indexa la historia de un canal de Slack en el Knowledge Base. channel = ID del canal (ej C0123)."""
    token = _get_slack_token()
    messages, user_map = read_channel_history(token, channel)
    docs = normalize_messages(messages, user_map, channel=channel)
    if not docs:
        return "No encontré mensajes para indexar."
    n = ingest_documents(REGION, KB_ID, DATA_SOURCE_ID, build_kb_documents(docs))
    return f"Indexé {n} mensajes del canal {channel}."


@tool
def ask_kb(question: str) -> str:
    """Responde una pregunta usando el conocimiento indexado de Slack, con citas."""
    context, citations = format_retrieval_results(retrieve(REGION, KB_ID, question))
    if not context:
        return "No encontré nada relevante en la historia de Slack."
    refs = ", ".join(c["id"] for c in citations)
    return f"Contexto recuperado:\n{context}\n\n[Fuentes: {refs}]"


_agent = Agent(
    model=_model,
    tools=[ingest_slack, ask_kb],
    system_prompt=(
        "Sos un asistente que responde sobre la historia de Slack del equipo. "
        "Usá ask_kb para responder preguntas y SIEMPRE incluí las fuentes (los IDs de cita). "
        "Usá ingest_slack solo si te piden indexar un canal. Respondé en español, breve y preciso."
    ),
)


@app.entrypoint
def invoke(payload):
    result = _agent(payload.get("prompt", ""))
    return {"result": result.message}


if __name__ == "__main__":
    app.run()
```

- [ ] **Step 5: Probar el agente localmente**

Run (en una terminal, con env seteado):
```bash
KB_ID=<id> DATA_SOURCE_ID=<id> .venv/bin/pip install -r agent/requirements.txt && \
KB_ID=<id> DATA_SOURCE_ID=<id> .venv/bin/python -m agent.agent
```
En otra terminal:
```bash
curl -X POST http://localhost:8080/invocations -H "Content-Type: application/json" \
  -d '{"prompt": "¿qué se dijo sobre el deploy?"}'
```
Expected: responde un JSON `{"result": ...}`. (La primera vez `ingest_slack` imprimirá una URL de autorización OAuth de Slack — autorizar una vez.)

- [ ] **Step 6: Commit**

```bash
git add agent/ && git commit -m "feat: Strands agent with ingest_slack + ask_kb tools"
```

---

### Task 10: Deploy del agente a AgentCore Runtime

**Files:**
- (genera) `Dockerfile`, `.dockerignore`, `.bedrock_agentcore.yaml` (los crea `agentcore configure`)

**Interfaces:**
- Consumes: `agent/agent.py` (Task 9).
- Produces: `agentRuntimeArn` del runtime desplegado (guardarlo para Task 11).

> **Flag:** verificar si el toolkit instalado usa `agentcore launch` (legacy) o `agentcore deploy` (CLI nuevo) corriendo `agentcore --help` primero.

- [ ] **Step 1: Instalar el starter toolkit**

Run: `.venv/bin/pip install bedrock-agentcore-starter-toolkit`

- [ ] **Step 2: Confirmar verbos del CLI**

Run: `.venv/bin/agentcore --help`
Expected: ver si aparece `launch` o `deploy`.

- [ ] **Step 3: Configurar**

Run: `.venv/bin/agentcore configure --entrypoint agent/agent.py`
Expected: genera `Dockerfile`, `.dockerignore`, `.bedrock_agentcore.yaml`. Pasar el execution role del sandbox con `-er <role-arn>` si lo pide.

- [ ] **Step 4: Desplegar**

Run: `.venv/bin/agentcore launch`  *(o `agentcore deploy` según Step 2)*
Expected: buildea imagen, push a ECR, crea el runtime. Anotar el `agentRuntimeArn` impreso.

> Las env vars (`KB_ID`, `DATA_SOURCE_ID`, `SLACK_PROVIDER`, `MODEL_ID`) deben configurarse en el runtime. Setearlas en `.bedrock_agentcore.yaml` (sección de environment) antes de `launch`, o vía consola tras desplegar.

- [ ] **Step 5: Invocar el runtime desplegado**

Run: `.venv/bin/agentcore invoke '{"prompt": "hola, ¿qué sabés?"}'`
Expected: respuesta del agente desde la nube.

- [ ] **Step 6: Commit**

```bash
git add Dockerfile .dockerignore .bedrock_agentcore.yaml && git commit -m "chore: deploy agent to AgentCore Runtime"
```

---

### Task 11: Lambda-puente + API Gateway

**Files:**
- Create: `bridge/handler.py`, `bridge/requirements.txt`
- Test: `tests/test_bridge_handler.py`

**Interfaces:**
- Consumes: `verify_slack_signature` (Task 4), `build_slack_response` (Task 5), `agentRuntimeArn` (Task 10), `SLACK_SIGNING_SECRET` (env).
- Produces: `lambda_handler(event, context) -> dict`. Maneja: (a) `url_verification` → devuelve el `challenge`; (b) slash command → valida firma, responde ack <3s, e invoca el runtime async (otra invocación Lambda / thread) que postea a `response_url`. Función pura testeable: `route_event(body_dict, headers, raw_body, signing_secret) -> dict` que decide la acción sin efectos.

- [ ] **Step 1: Escribir el test que falla** (`tests/test_bridge_handler.py`)

```python
import json
from bridge.handler import classify_request

SECRET = "test-secret"


def test_url_verification_returns_challenge():
    body = json.dumps({"type": "url_verification", "challenge": "abc123"})
    action = classify_request(body, content_type="application/json")
    assert action == {"kind": "challenge", "challenge": "abc123"}


def test_slash_command_is_classified():
    body = "command=%2Fask&text=hola&response_url=https%3A%2F%2Fhook&channel_id=C9"
    action = classify_request(body, content_type="application/x-www-form-urlencoded")
    assert action["kind"] == "slash"
    assert action["command"] == "/ask"
    assert action["text"] == "hola"
    assert action["response_url"] == "https://hook"
    assert action["channel_id"] == "C9"
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `.venv/bin/python -m pytest tests/test_bridge_handler.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'bridge.handler'`.

- [ ] **Step 3: Implementar `bridge/handler.py`**

```python
# bridge/handler.py
import json
import os
import threading
import urllib.parse
import urllib.request

import boto3

from bridge.slack_sig import verify_slack_signature
from bridge.blocks import build_slack_response

REGION = os.environ.get("AWS_REGION", "us-west-2")
RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")
SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")


def classify_request(raw_body, content_type):
    if "application/json" in content_type:
        data = json.loads(raw_body)
        if data.get("type") == "url_verification":
            return {"kind": "challenge", "challenge": data["challenge"]}
        return {"kind": "event", "data": data}
    form = {k: v[0] for k, v in urllib.parse.parse_qs(raw_body).items()}
    return {
        "kind": "slash",
        "command": form.get("command", ""),
        "text": form.get("text", ""),
        "response_url": form.get("response_url", ""),
        "channel_id": form.get("channel_id", ""),
    }


def _process_async(action):
    prompt = action["text"] or "Resumí lo último del canal."
    if action["command"] == "/ingest":
        prompt = f"Indexá el canal {action['channel_id']}."
    client = boto3.client("bedrock-agentcore", region_name=REGION)
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=RUNTIME_ARN,
        runtimeSessionId=action["channel_id"].ljust(33, "0"),  # min 33 chars
        payload=json.dumps({"prompt": prompt}).encode(),
        qualifier="DEFAULT",
    )
    answer = json.loads(resp["response"].read())["result"]
    body = build_slack_response(answer, [])
    req = urllib.request.Request(
        action["response_url"],
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=10)


def lambda_handler(event, context):
    raw_body = event.get("body", "") or ""
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    content_type = headers.get("content-type", "")
    action = classify_request(raw_body, content_type)

    if action["kind"] == "challenge":
        return {"statusCode": 200, "body": action["challenge"]}

    ts = headers.get("x-slack-request-timestamp", "")
    sig = headers.get("x-slack-signature", "")
    if not verify_slack_signature(SIGNING_SECRET, ts, raw_body, sig):
        return {"statusCode": 401, "body": "bad signature"}

    if action["kind"] == "slash":
        threading.Thread(target=_process_async, args=(action,), daemon=True).start()
        return {"statusCode": 200, "body": "🔎 Buscando en tu Slack..."}

    return {"statusCode": 200, "body": "ok"}
```

> **Nota de robustez:** el `threading.Thread` da el ack <3s y procesa después dentro de la misma invocación Lambda. Para producción conviene SQS + segunda Lambda (patrón oficial AWS), pero para el workshop el thread alcanza. Setear timeout de la Lambda en 60s.

- [ ] **Step 4: Correr y verificar que pasa**

Run: `.venv/bin/python -m pytest tests/test_bridge_handler.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Crear `bridge/requirements.txt` y empaquetar/deployar**

```
boto3
```

Deploy (sandbox; ajustar role y nombres):
```bash
cd bridge && zip -r ../bridge.zip handler.py slack_sig.py blocks.py __init__.py && cd ..
aws lambda create-function --function-name slackrag-bridge \
  --runtime python3.12 --handler handler.lambda_handler \
  --role <LAMBDA_ROLE_ARN> --timeout 60 --zip-file fileb://bridge.zip \
  --environment "Variables={AGENT_RUNTIME_ARN=<arn-task10>,SLACK_SIGNING_SECRET=<secret>,AWS_REGION=us-west-2}" \
  --region us-west-2
```
Crear API HTTP y conectarla:
```bash
aws apigatewayv2 create-api --name slackrag-api --protocol-type HTTP \
  --target arn:aws:lambda:us-west-2:<acct>:function:slackrag-bridge --region us-west-2
aws lambda add-permission --function-name slackrag-bridge \
  --statement-id apigw --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com --region us-west-2
```
Expected: obtenés la `ApiEndpoint`. Esa URL (+ `/`) es la Request URL para Slack.

- [ ] **Step 6: Commit**

```bash
git add bridge/ tests/test_bridge_handler.py && git commit -m "feat: Slack bridge Lambda + API Gateway"
```

---

### Task 12: Conectar la Slack App + seed de datos demo

**Files:**
- Create: `scripts/seed_demo.py`
- Modify: `README.md` (instrucciones de setup)

**Interfaces:**
- Consumes: `build_kb_documents` + `ingest_documents` (Tasks 3/9), `KB_ID`, `DATA_SOURCE_ID`.
- Produces: `scripts/seed_demo.py` que ingesta ~10-15 mensajes ficticios al KB para tener data garantizada en el demo (no depender del `/ingest` en vivo).

- [ ] **Step 1: Implementar `scripts/seed_demo.py`**

```python
# scripts/seed_demo.py
import os
from agent.normalize import normalize_messages
from agent.kb import build_kb_documents, ingest_documents

REGION = os.environ.get("AWS_REGION", "us-west-2")
KB_ID = os.environ["KB_ID"]
DS_ID = os.environ["DATA_SOURCE_ID"]

RAW = [
    {"type": "message", "user": "U1", "ts": "1.0", "text": "Deploy de prod programado para el viernes 18hs."},
    {"type": "message", "user": "U2", "ts": "2.0", "text": "Confirmado, freeze de código el jueves."},
    {"type": "message", "user": "U1", "ts": "3.0", "text": "El bug de login se arregló en el PR #482."},
    {"type": "message", "user": "U3", "ts": "4.0", "text": "Decidimos migrar la DB a Aurora Serverless v2."},
    {"type": "message", "user": "U2", "ts": "5.0", "text": "El cliente Acme pidió SSO con Okta."},
]
USER_MAP = {"U1": "ana", "U2": "beto", "U3": "caro"}

docs = normalize_messages(RAW, USER_MAP, channel="C-DEMO")
n = ingest_documents(REGION, KB_ID, DS_ID, build_kb_documents(docs))
print(f"Seed: {n} mensajes indexados.")
```

- [ ] **Step 2: Ejecutar el seed y verificar retrieval**

Run:
```bash
KB_ID=<id> DATA_SOURCE_ID=<id> .venv/bin/python -m scripts.seed_demo
```
Esperar ~30s a que indexe, luego probar:
```python
KB_ID=<id> .venv/bin/python -c "from agent.kb import retrieve, format_retrieval_results; import os; print(format_retrieval_results(retrieve(os.environ.get('AWS_REGION','us-west-2'), os.environ['KB_ID'], '¿cuándo es el deploy?')))"
```
Expected: recupera el chunk del deploy del viernes con su cita `C-DEMO-1.0`.

- [ ] **Step 3: Configurar la Slack App en api.slack.com**

- Crear app desde `slack/manifest.yaml` (Create App → From manifest).
- En **OAuth & Permissions**: registrar el `callbackUrl` de Task 8 como Redirect URL; instalar la app al workspace; agregar el bot a un canal.
- En **Slash Commands** (o vía manifest): Request URL = `ApiEndpoint` de Task 11.
- En **Basic Information**: copiar el **Signing Secret** → setearlo en la env `SLACK_SIGNING_SECRET` de la Lambda (Task 11).
- Copiar **Client ID / Client Secret** → ya usados en Task 8.

- [ ] **Step 4: Smoke test end-to-end en Slack**

En un canal del workspace con la app:
- `/ask ¿cuándo es el deploy?`
Expected: el bot ackea "🔎 Buscando..." y al toque postea la respuesta con la fuente `C-DEMO-1.0`.

- [ ] **Step 5: Escribir `README.md`** con el orden de setup (Tasks 6→7→8→9→10→11→12) y las env vars necesarias.

- [ ] **Step 6: Commit**

```bash
git add scripts/seed_demo.py README.md && git commit -m "feat: demo seed data + Slack app wiring + README"
```

---

## Self-Review

**Spec coverage:**
- Ingesta vía AgentCore (Identity + agente) → Tasks 8, 9 ✅
- KB + S3 Vectors + ingestión directa → Tasks 6, 7, 3, 9 ✅
- Consulta con citas → Tasks 3, 9, 5 ✅
- Lambda-puente (front-door revisado) → Tasks 4, 5, 11 ✅
- Slack como ejemplo, extensible a Teams → documentado; Teams = cambiar provider a `MicrosoftOauth2` + scopes Graph (fuera de alcance de este plan, 1 nota en README) ✅
- Momentos wow (Observability) → no requiere código; se muestra en consola de AgentCore en el demo ✅

**Placeholder scan:** sin TBD/TODO. Los valores que dependen del entorno (ARNs, IDs, secretos) se pasan por env y se documentan; no son placeholders de código.

**Type consistency:** `normalize_messages` → dicts con `id/text/channel/ts/author` consumidos por `build_kb_documents`; `retrieve` → `format_retrieval_results` → `citations` con `{id,score}` consumido por `build_slack_response`. Consistente entre tasks.

**Flags abiertos (verificar al ejecutar):**
1. Verbo del CLI: `agentcore launch` vs `deploy` (Task 10, Step 2).
2. Clave exacta del `callbackUrl` en el response de `create_oauth2_credential_provider` (Task 8).
3. ID exacto del modelo Claude disponible en la región (Global Constraints).
4. `auth_flow="USER_FEDERATION"` requiere autorización OAuth interactiva la primera vez; para el workshop conviene pre-autorizar antes del demo.

## Referencias (verificadas)

- AgentCore Runtime + Strands: https://strandsagents.com/docs/user-guide/deploy/deploy_to_bedrock_agentcore/python/
- invoke_agent_runtime (boto3): https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-agentcore/client/invoke_agent_runtime.html
- Identity Slack provider: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-idp-slack.html
- @requires_access_token: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-authentication.html
- create_knowledge_base (boto3): https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-agent/client/create_knowledge_base.html
- S3 Vectors create_index: https://docs.aws.amazon.com/boto3/latest/reference/services/s3vectors/client/create_index.html
- ingest_knowledge_base_documents: https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-agent/client/ingest_knowledge_base_documents.html
- retrieve (boto3): https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-agent-runtime/client/retrieve.html
- InvokeAgentRuntime API: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-invoke-agent.html
- Integrating AgentCore with Slack (blog + sample): https://aws.amazon.com/blogs/machine-learning/integrating-amazon-bedrock-agentcore-with-slack/
- Slack slash commands: https://docs.slack.dev/interactivity/implementing-slash-commands
