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
