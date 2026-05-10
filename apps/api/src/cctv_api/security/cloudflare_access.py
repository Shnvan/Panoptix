from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request, WebSocket
from jwt import InvalidTokenError, PyJWKClient, PyJWKClientError, decode
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cctv_api.core.config import Settings
from cctv_api.models.enums import GatewayStatus
from cctv_api.models.tables import EdgeGateway
from cctv_api.security.identity import Principal, PrincipalKind
from cctv_api.security.service_tokens import verify_service_token


class AccessVerificationError(Exception):
    def __init__(self, detail: str, *, status: int = 401) -> None:
        self.detail = detail
        self.status = status
        super().__init__(detail)


class CloudflareAccessVerifier:
    _jwks_clients: dict[str, PyJWKClient] = {}

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def verify_browser_request(self, request: Request) -> Principal:
        dev_principal = self._dev_user_principal(request)
        if dev_principal is not None:
            return dev_principal

        token = request.headers.get("cf-access-jwt-assertion")
        if not token:
            raise AccessVerificationError("cf-access-token-required")

        claims = self._decode_browser_token(token)
        return self._principal_from_browser_claims(claims)

    def verify_gateway_request(self, request: Request, db: DbSession) -> Principal:
        dev_principal = self._dev_gateway_principal(request)
        if dev_principal is not None:
            return dev_principal

        gateway_id = request.headers.get("x-panoptix-gateway-id")
        token = self._bearer_token(request)
        if not gateway_id or token is None:
            raise AccessVerificationError("gateway-identity-required")

        try:
            gateway_uuid = uuid.UUID(gateway_id)
        except ValueError as exc:
            raise AccessVerificationError("gateway-identity-invalid") from exc

        gateway = db.execute(select(EdgeGateway).where(EdgeGateway.id == str(gateway_uuid))).scalar_one_or_none()
        if gateway is None:
            raise AccessVerificationError("gateway-identity-invalid")
        if gateway.status != GatewayStatus.enabled or gateway.disabled_at is not None:
            raise AccessVerificationError("gateway-disabled", status=403)
        if gateway.service_token_hash is None:
            raise AccessVerificationError("gateway-credential-not-configured")
        if not verify_service_token(token, gateway.service_token_hash):
            raise AccessVerificationError("gateway-credential-invalid")

        return Principal(
            kind=PrincipalKind.GATEWAY,
            subject=f"gateway:{gateway_uuid}",
            gateway_id=str(gateway_uuid),
            roles=frozenset({"gateway"}),
            is_dev=False,
        )

    def verify_gateway_websocket(self, websocket: WebSocket) -> Principal:
        gateway_id = websocket.headers.get("x-panoptix-dev-gateway-id")
        if gateway_id is not None:
            self._assert_dev_auth_allowed()
            return Principal(
                kind=PrincipalKind.GATEWAY,
                subject=f"gateway:{gateway_id}",
                gateway_id=gateway_id,
                roles=frozenset({"gateway"}),
                is_dev=True,
            )

        raise AccessVerificationError("gateway-identity-required")

    def _dev_user_principal(self, request: Request) -> Principal | None:
        if request.headers.get("x-panoptix-dev-auth") != "1":
            return None
        self._assert_dev_auth_allowed()

        roles = self._split_header(request.headers.get("x-panoptix-dev-roles", "viewer"))
        permissions = self._split_header(request.headers.get("x-panoptix-dev-permissions", ""))

        return Principal(
            kind=PrincipalKind.USER,
            subject=request.headers.get("x-panoptix-dev-subject", "dev-user"),
            email=request.headers.get("x-panoptix-dev-email", "dev@example.test"),
            roles=frozenset(roles),
            permissions=frozenset(permissions),
            is_dev=True,
        )

    def _dev_gateway_principal(self, request: Request) -> Principal | None:
        gateway_id = request.headers.get("x-panoptix-dev-gateway-id")
        if gateway_id is None:
            return None
        self._assert_dev_auth_allowed()

        return Principal(
            kind=PrincipalKind.GATEWAY,
            subject=f"gateway:{gateway_id}",
            gateway_id=gateway_id,
            roles=frozenset({"gateway"}),
            is_dev=True,
        )

    def _assert_dev_auth_allowed(self) -> None:
        if self.settings.APP_ENV != "development":
            raise AccessVerificationError("dev-auth-forbidden-outside-development")
        if not self.settings.ALLOW_DEV_AUTH:
            raise AccessVerificationError("dev-auth-disabled")

    def _decode_browser_token(self, token: str) -> dict[str, Any]:
        try:
            signing_key = self._get_signing_key(token)
            claims = decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.settings.cf_access_browser_audiences,
                issuer=self.settings.CF_ACCESS_ISSUER,
                leeway=self.settings.CLOCK_SKEW_SECONDS,
                options={
                    "require": ["exp", "iat", "nbf", "iss", "aud", "sub"],
                },
            )
        except (InvalidTokenError, PyJWKClientError) as exc:
            raise AccessVerificationError("cf-access-token-invalid") from exc

        return claims

    def _get_signing_key(self, token: str) -> Any:
        return self._get_jwks_client().get_signing_key_from_jwt(token)

    def _get_jwks_client(self) -> PyJWKClient:
        client = self._jwks_clients.get(self.settings.CF_ACCESS_JWKS_URL)
        if client is None:
            client = PyJWKClient(self.settings.CF_ACCESS_JWKS_URL)
            self._jwks_clients[self.settings.CF_ACCESS_JWKS_URL] = client
        return client

    def _principal_from_browser_claims(self, claims: dict[str, Any]) -> Principal:
        roles = claims.get("roles", [])
        permissions = claims.get("permissions", [])

        return Principal(
            kind=PrincipalKind.USER,
            subject=str(claims["sub"]),
            email=self._optional_claim(claims, "email"),
            roles=frozenset(self._claim_values(roles)),
            permissions=frozenset(self._claim_values(permissions)),
            is_dev=False,
        )

    @staticmethod
    def _claim_values(value: object) -> set[str]:
        if isinstance(value, str):
            return {item.strip() for item in value.split(",") if item.strip()}
        if isinstance(value, list):
            return {str(item).strip() for item in value if str(item).strip()}
        return set()

    @staticmethod
    def _optional_claim(claims: dict[str, Any], name: str) -> str | None:
        value = claims.get(name)
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _split_header(value: str) -> set[str]:
        return {item.strip() for item in value.split(",") if item.strip()}

    @staticmethod
    def _bearer_token(request: Request) -> str | None:
        authorization = request.headers.get("authorization")
        if authorization is None:
            return None
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None
        return token
