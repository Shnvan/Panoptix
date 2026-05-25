from __future__ import annotations

import hashlib
import hmac
import uuid

CSRF_COOKIE_NAME = "panoptix_csrf"
CSRF_HEADER_NAME = "x-panoptix-csrf-token"


class CsrfTokenError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def create_csrf_token(session_id: uuid.UUID, signing_key: str) -> str:
    _validate_signing_key(signing_key)
    session_str = str(session_id)
    signature = _sign(session_str, signing_key)
    return f"{session_str}.{signature}"


def verify_csrf_token(token: str, *, session_id: uuid.UUID, signing_key: str) -> None:
    _validate_signing_key(signing_key)
    if not token or "." not in token:
        raise CsrfTokenError("csrf-token-invalid")
    token_session, signature = token.rsplit(".", 1)
    if token_session != str(session_id):
        raise CsrfTokenError("csrf-token-invalid")
    expected = _sign(token_session, signing_key)
    if not hmac.compare_digest(signature, expected):
        raise CsrfTokenError("csrf-token-invalid")


def _sign(data: str, signing_key: str) -> str:
    return hmac.new(signing_key.strip().encode("utf-8"), data.encode("utf-8"), hashlib.sha256).hexdigest()


def _validate_signing_key(signing_key: str) -> None:
    if not signing_key.strip() or signing_key.strip() == "replace-me":
        raise CsrfTokenError("csrf-signing-key-invalid")
