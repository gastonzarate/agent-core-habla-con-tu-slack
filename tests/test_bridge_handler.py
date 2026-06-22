import json
from bridge.handler import classify_request


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
