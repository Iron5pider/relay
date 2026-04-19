"""Signature verifiers for inbound webhooks.

Currently just ElevenLabs post_call (HMAC-SHA256 over `ts.body` with a 5-minute
replay window, per `API_DOCS/ElevenLabs_Twilio_integration.md` §6.2 and
`backend/CLAUDE.md` §1.3). Twilio's HMAC-SHA1 verifier will land when we
start receiving Twilio webhooks directly; for now ElevenLabs' native Twilio
integration handles call status internally.
"""

from __future__ import annotations

import hashlib
import hmac
import time


def verify_elevenlabs_signature(
    raw_body: bytes,
    header: str | None,
    secret: str,
    *,
    max_age_seconds: int = 300,
) -> bool:
    """Verify `ElevenLabs-Signature: t=<unix_ts>,v0=<sha256_hmac>` header.

    Returns False on any verification failure (missing header, stale timestamp,
    HMAC mismatch, malformed input). Never raises. Callers should treat False
    as 403.
    """
    if not header or not secret:
        return False
    try:
        parts = dict(p.split("=", 1) for p in header.split(","))
        ts_str = parts.get("t", "")
        sig = parts.get("v0", "")
        if not ts_str or not sig:
            return False
        ts = int(ts_str)
    except (KeyError, ValueError):
        return False

    if abs(time.time() - ts) > max_age_seconds:
        return False

    expected = hmac.new(
        secret.encode(),
        f"{ts}.".encode() + raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, sig)


__all__ = ["verify_elevenlabs_signature"]
