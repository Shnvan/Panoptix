from __future__ import annotations

from fastapi import Request

from cctv_api.core.config import Settings
from cctv_api.security.identity import Principal, PrincipalKind


class AccessVerificationError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class CloudflareAccessVerifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def verify_browser_request(self, request: Request) -> Principal:
        dev_principal = self._dev_user_principal(request)
        if dev_principal is not None:
            return dev_principal

        token = request.headers.get("cf-access-jwt-assertion")
        if not token:
            raise AccessVerificationError("cf-access-token-required")

        raise AccessVerificationError("cf-access-verifier-not-configured")

    def verify_gateway_request(self, request: Request) -> Principal:
        dev_principal = self._dev_gateway_principal(request)
        if dev_principal is not None:
            return dev_principal

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

    @staticmethod
    def _split_header(value: str) -> set[str]:
        return {item.strip() for item in value.split(",") if item.strip()}
