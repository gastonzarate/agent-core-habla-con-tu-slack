# Diseño — Workshop AWS GenAI: RAG sobre Slack con Bedrock AgentCore

**Fecha:** 2026-06-02
**Autor:** Gastón Zárate (SleakOps)
**Objetivo de negocio:** Dar dos charlas/workshops de GenAI sobre AWS para captar clientes, mostrando una implementación serverless real con lo más nuevo de AWS 2026 (Bedrock AgentCore + S3 Vectors).

## Eventos reservados

| Fecha | Formato | Audiencia |
|-------|---------|-----------|
| 24 de junio, 2pm | "1 to few" — workshop hands-on | 18 personas |
| 25 de junio, 2pm | "1 to many" — sesión presentación | 40 personas |

## Caso de uso

Una implementación simple que **chupa la data de un workspace de Slack, la organiza en una base vectorial y permite preguntar sobre esa data en lenguaje natural**. Todo serverless, todo AWS, apoyándose al máximo en Bedrock AgentCore para minimizar la infraestructura propia.

## Decisiones de diseño tomadas

- **Vector store / RAG:** Bedrock Knowledge Base + S3 Vectors (RAG "de manual", fácil de explicar y defender en vivo, escala a corpus grande). [Opción 2 del brainstorming.]
- **Embeddings:** Amazon Titan Text Embeddings v2 (vía Bedrock).
- **LLM:** Anthropic Claude (Sonnet o Haiku) en Bedrock.
- **Agente:** Strands Agents SDK, hosteado en AgentCore Runtime.
- **Ingesta:** la realiza **el propio agente de AgentCore**, disparado por Slack — NO una Lambda de ingesta dedicada.
- **Front-door Slack → AgentCore:** **Lambda-puente fina** (API Gateway HTTP → Lambda). La Lambda valida la firma de Slack, responde el `challenge` y el ack en <3s, e invoca al agente async; al terminar, el agente (o la Lambda) responde por `response_url`. NO es una "Lambda de ingesta" — es un shim de ~15-20 líneas; toda la lógica del caso de uso vive en AgentCore.
  - *Decisión revisada (2026-06-22):* originalmente se eligió "API Gateway directo sin Lambda", pero la investigación verificada lo descartó (ver restricción abajo).

## Restricción técnica conocida (junio 2026) — verificada

- AgentCore Runtime no se dispara nativamente desde EventBridge/S3/SQS; solo vía la API `InvokeAgentRuntime` (SigV4, signing name `bedrock-agentcore`).
- El front-door **sin Lambda no es viable** y se rompe en 3 puntos verificados:
  1. **Timeout de 3s de Slack:** `InvokeAgentRuntime` + retrieve + Claude tarda más; el slash command da timeout sin un ack inmediato + respuesta diferida por `response_url`.
  2. **Firma HMAC de Slack:** API Gateway no puede validar `X-Slack-Signature` sobre el body crudo.
  3. **Streaming / respuestas grandes:** API Gateway REST buffer-ea y corta a ~29s / 10 MB.
- Todas las arquitecturas oficiales de AWS para Slack + AgentCore usan al menos una Lambda. Por eso se adopta la **Lambda-puente fina**.

## Arquitectura

```
Slack (slash commands /ingest, /ask)
        │
        ▼
API Gateway HTTP ──► Lambda-puente (valida firma, ack <3s,    ──►  InvokeAgentRuntime
                     invoca async; ~15-20 líneas)                   │
                                                                    ▼
                                                        AgentCore Runtime
                                                         (Strands Agent)
                                                                 │
        ┌────────────────────────────────────────────────────────┤
        ▼ (tools vía AgentCore Gateway = MCP)                      ▼
  leer Slack history (conector Slack)        ingestar a Knowledge Base
                                             (KB direct ingestion API — sin S3 intermedio)
                                                                 │
                                                                 ▼
                                          Bedrock Knowledge Base + S3 Vectors + Titan v2
        ┌────────────────────────────────────────────────────────┘
        ▼ (al preguntar)
  tool: KB retrieve (top-K + citas) ──► Claude ──► respuesta + citas a mensajes originales

  Transversal (todo AgentCore gestionado):
   · Identity   → OAuth contra Slack (gratis con Runtime/Gateway)
   · Memory     → memoria de conversación multi-turn
   · Policy     → guardrails determinísticos (Cedar / lenguaje natural)
   · Observability → trazas paso a paso (CloudWatch / OTEL)
```

## Componentes: propio vs gestionado

| Pieza | Provee | Mantenimiento propio |
|-------|--------|----------------------|
| API Gateway HTTP + Lambda-puente | Nosotros (shim ~15-20 líneas) + AWS | ✏️ Glue mínimo (valida firma + ack + invoca) |
| AgentCore Runtime + Strands Agent | Nosotros (poca definición) + AgentCore | Definición del agente y sus tools |
| AgentCore Gateway (conector Slack + tools KB) | AWS gestionado | Configuración |
| Bedrock Knowledge Base + S3 Vectors | AWS gestionado | Configuración |
| Embeddings Titan v2 / Claude | Bedrock | Cero |
| Identity / Memory / Policy / Observability | AgentCore gestionado | Cero |

**Lo único "propio" es la definición del agente Strands (pocas líneas) y la configuración.** No hay Lambdas que mantener.

## Flujo de datos

1. **Ingesta:** usuario ejecuta `/ingest` en Slack → API Gateway → AgentCore. El agente usa el conector Slack (Gateway) para leer `conversations.history`, normaliza (resuelve user IDs a nombres, arma contexto de hilo) y empuja los documentos al Knowledge Base vía direct ingestion API. KB hace chunking + embeddings (Titan v2) + indexa en S3 Vectors.
2. **Consulta:** usuario ejecuta `/ask <pregunta>` → API Gateway → AgentCore. El agente llama la tool `KB retrieve` (top-K chunks + citas), pasa el contexto a Claude, devuelve la respuesta con enlaces a los mensajes de Slack originales. Memory mantiene el hilo de conversación.

## Argumentos comerciales (por qué vende)

- **Costo ≈ 0 en reposo:** todo consumo puro, sin mínimos. (Runtime ~$0.0895/vCPU-h; Memory $0.75/1000 registros-mes; Gateway $0.005/1000 invocaciones.)
- **Sin servidores ni Lambdas que mantener:** exactamente lo que vende SleakOps.
- **Lo más nuevo de AWS 2026:** AgentCore + S3 Vectors → posicionamiento early-adopter.

## Momentos "wow" para el demo en vivo

- **Observability:** mostrar la traza paso a paso del agente mientras razona y llama tools.
- **Policy:** demostrar un guardrail bloqueando una acción en tiempo real.
- **Citas del KB:** cada respuesta enlaza al mensaje de Slack original = confianza.
- **Costo en pantalla:** evidenciar que en reposo no se paga nada.

## Pendiente (próximo paso del brainstorming)

- Definir **título** de las charlas.
- Definir **lineup / agenda** de cada una (workshop hands-on de 18 vs sesión de 40).

## Fuentes

- [AgentCore Overview](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)
- [AgentCore Pricing](https://aws.amazon.com/bedrock/agentcore/pricing/)
- [InvokeAgentRuntime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-invoke-agent.html)
- [Cuándo usar AgentCore vs Lambda](https://www.virtuability.com/blog/2026-03-27-when-to-use-agentcore/)
