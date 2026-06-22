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
