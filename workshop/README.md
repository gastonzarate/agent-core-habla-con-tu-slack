# Workshop — Hablá con tu Slack

Agente de IA serverless en AWS que ingesta mensajes de Slack a un Knowledge Base
(S3 Vectors) y responde preguntas en lenguaje natural con citas.

## Estructura

```
workshop/
├── config.py          # config + estado compartido entre pasos (state.local.json)
├── steps/             # los pasos del hands-on (se corren en orden)
│   ├── step1_vectors.py   # base vectorial (S3 Vectors)
│   └── step2_kb.py        # Knowledge Base + data source
├── agent/             # AUTOCONTENIDO → se despliega a AgentCore Runtime
│   ├── agent.py           # agente Strands (tools: ask_kb, ingest_slack)
│   ├── normalize.py kb.py slack_reader.py
│   └── requirements.txt
├── bridge/            # AUTOCONTENIDO → se despliega como Lambda
│   ├── handler.py         # recibe Slack, valida firma, invoca el agente
│   ├── slack_sig.py blocks.py normalize.py kb.py
│   └── requirements.txt
└── tests/             # tests de la lógica pura (pytest)
```

> `agent/` y `bridge/` duplican `normalize.py` y `kb.py` a propósito: así cada
> uno se empaqueta zippeando su carpeta, sin dependencias externas.

## Requisitos

- Credenciales AWS activas (perfil con acceso al sandbox).
- Acceso en Bedrock a **Titan Text Embeddings v2** y **Claude**.
- Python 3.12+ y las dependencias de dev:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r workshop/requirements-dev.txt
```

## Variables de entorno (opcionales)

| Variable | Default | Para qué |
|----------|---------|----------|
| `AWS_REGION` | `us-east-1` | región de los recursos |
| `WORKSHOP_PREFIX` | `slackrag` | prefijo de nombres (cambialo para no chocar con otros) |
| `MODEL_ID` | `us.anthropic.claude-sonnet-4-6` | modelo de Claude |

## Pasos

```bash
python workshop/steps/step1_vectors.py   # 1 · base vectorial
python workshop/steps/step2_kb.py        # 2 · Knowledge Base
# (3-7 se agregan a medida que avanza el workshop)
```

Cada paso es **idempotente** (si el recurso existe, lo reusa) y guarda lo que
necesita el siguiente en `workshop/state.local.json`.

## Tests

```bash
cd workshop && python -m pytest -q
```
