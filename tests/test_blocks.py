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
