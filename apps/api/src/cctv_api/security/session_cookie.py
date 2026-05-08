from __future__ import annotations

import hashlib
import hmac
import uuid


def create_session_cookie(session_id: uuid.UUID, signing_key: str) -> str:
    session_str = str(session_id)
    signature = _sign(session_str, signing_key)
    return f"{session_str}.{signature}"


def read_session_cookie(cookie_value: str, signing_key: str) -> uuid.UUID | None:
    if not cookie_value or "." not in cookie_value:
        return None

    parts = cookie_value.rsplit(".", 1)
    if len(parts) != 2:
        return None

    session_str, signature = parts

    expected = _sign(session_str, signing_key)
    if not hmac.compare_digest(signature, expected):
        return None

    try:
        return uuid.UUID(session_str)
    except ValueError:
        return None


def _sign(data: str, key: str) -> str:
    return hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()
