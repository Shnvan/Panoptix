from __future__ import annotations

import hashlib
import hmac
import secrets


def generate_service_token() -> str:
    return secrets.token_urlsafe(32)


def hash_service_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_service_token(token: str, token_hash: str) -> bool:
    candidate = hash_service_token(token)
    return hmac.compare_digest(candidate, token_hash)
