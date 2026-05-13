from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from panoptix_edge_agent.config import AgentConfig

GatewayStatus = Literal["online", "degraded", "offline"]
CameraHealthStatus = Literal["online", "offline", "degraded"]


class AgentClientError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, body: str | None = None) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(message)


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: str


class JsonTransport(Protocol):
    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> HttpResponse:
        raise NotImplementedError


class UrlLibJsonTransport:
    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> HttpResponse:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected
                body = response.read().decode("utf-8")
                return HttpResponse(status_code=response.status, body=body)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return HttpResponse(status_code=exc.code, body=body)
        except URLError as exc:
            raise AgentClientError(f"gateway request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise AgentClientError("gateway request timed out") from exc


@dataclass(frozen=True)
class CameraStatusReport:
    camera_id: str
    status: CameraHealthStatus
    last_seen_at: datetime | None = None
    detail: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"camera_id": self.camera_id, "status": self.status}
        if self.last_seen_at is not None:
            payload["last_seen_at"] = _format_datetime(self.last_seen_at)
        if self.detail is not None:
            payload["detail"] = self.detail
        return payload


class GatewayApiClient:
    def __init__(self, config: AgentConfig, transport: JsonTransport | None = None) -> None:
        self.config = config
        self.transport = UrlLibJsonTransport() if transport is None else transport

    def send_heartbeat(
        self,
        *,
        status: GatewayStatus = "online",
        cameras: tuple[CameraStatusReport, ...] = (),
    ) -> dict[str, Any]:
        url = f"{self.config.normalized_api_base_url}/api/v1/gateways/{self.config.gateway_id}/heartbeat"
        payload: dict[str, Any] = {
            "status": status,
            "agent_version": self.config.agent_version,
            "cameras": [camera.to_payload() for camera in cameras],
        }
        return self._post(url, payload)

    def send_camera_status(
        self,
        *,
        camera_id: str,
        status: CameraHealthStatus,
        detail: str | None = None,
        observed_at: datetime | None = None,
    ) -> dict[str, Any]:
        url = (
            f"{self.config.normalized_api_base_url}/api/v1/gateways/"
            f"{self.config.gateway_id}/cameras/{camera_id}/status"
        )
        payload: dict[str, Any] = {"status": status}
        if detail is not None:
            payload["detail"] = detail
        if observed_at is not None:
            payload["observed_at"] = _format_datetime(observed_at)
        return self._post(url, payload)

    def _post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.transport.post_json(
            url,
            payload,
            self._headers(),
            self.config.request_timeout_seconds,
        )
        if response.status_code >= 400:
            raise AgentClientError(
                f"gateway request failed with status {response.status_code}",
                status_code=response.status_code,
                body=response.body,
            )
        if not response.body:
            return {}
        try:
            decoded = json.loads(response.body)
        except json.JSONDecodeError as exc:
            raise AgentClientError("gateway response was not valid JSON", body=response.body) from exc
        if not isinstance(decoded, dict):
            raise AgentClientError("gateway response JSON must be an object", body=response.body)
        return decoded

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.config.dev_identity_enabled:
            headers["x-panoptix-dev-gateway-id"] = self.config.gateway_id
        return headers


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
