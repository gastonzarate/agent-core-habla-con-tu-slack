import boto3


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
