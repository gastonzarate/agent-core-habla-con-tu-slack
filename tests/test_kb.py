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
