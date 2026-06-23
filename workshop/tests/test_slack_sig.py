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
