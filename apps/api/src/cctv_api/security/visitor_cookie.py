from __future__ import annotations

import hashlib
import hmac
import uuid


def create_visitor_cookie(visit_id: uuid.UUID, signing_key: str) -> str:
    visit_str = str(visit_id)
    return f"{visit_str}.{_sign(visit_str, signing_key)}"


def read_visitor_cookie(cookie_value: str, signing_key: str) -> uuid.UUID | None:
    if not cookie_value or "." not in cookie_value:
        return None

    visit_str, signature = cookie_value.rsplit(".", 1)
    expected = _sign(visit_str, signing_key)
    if not hmac.compare_digest(signature, expected):
        return None

    try:
        return uuid.UUID(visit_str)
    except ValueError:
        return None


def _sign(value: str, signing_key: str) -> str:
    return hmac.new(signing_key.encode(), value.encode(), hashlib.sha256).hexdigest()
