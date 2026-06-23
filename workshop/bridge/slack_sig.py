# bridge/slack_sig.py
import hashlib
import hmac


def verify_slack_signature(signing_secret, timestamp, raw_body, signature):
    base = f"v0:{timestamp}:{raw_body}".encode()
    expected = "v0=" + hmac.new(signing_secret.encode(), base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")
