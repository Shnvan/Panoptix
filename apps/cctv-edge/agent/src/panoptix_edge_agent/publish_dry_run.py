from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Protocol

from panoptix_edge_agent.commands import (
    CommandVerificationError,
    GatewayCommand,
    canonical_command_json,
    verify_gateway_command,
)
from panoptix_edge_agent.executor import CommandExecutor
from panoptix_edge_agent.livekit_publisher import (
    LiveKitMediaController,
    LiveKitPublishRequest,
    LiveKitPublisherClient,
    LiveKitPublisherResult,
)
from panoptix_edge_agent.mediamtx_process import MediamtxStartResult, MediamtxStopResult


class DryRunMediamtxLifecycle(Protocol):
    def start(self) -> MediamtxStartResult: ...

    def stop(self) -> MediamtxStopResult: ...


@dataclass(frozen=True)
class SyntheticPublishDryRunConfig:
    gateway_id: str = "gateway-dry-run"
    signing_key: str = "dry-run-signing-key"
    camera_id: str = "camera-1"
    room: str = "camera_ab12cd34"
    livekit_url: str = "wss://livekit.example.test"
    gateway_publish_token: str = "dry-run-gateway-publish-token"
    source_url: str = "rtsp://127.0.0.1:8554/synthetic-camera-1"
    command_ttl_seconds: int = 60
    duplicate_start: bool = False


@dataclass(frozen=True)
class DryRunPublisherCall:
    camera_id: str
    room: str
    livekit_url: str
    source_url: str
    token_present: bool


@dataclass(frozen=True)
class SyntheticPublishDryRunResult:
    ok: bool
    accepted_commands: int
    rejected_commands: int
    errors: tuple[str, ...]
    publisher_start_calls: tuple[DryRunPublisherCall, ...]
    publisher_stop_calls: tuple[dict[str, str], ...]
    source_url: str
    mediamtx_started: bool = False
    mediamtx_stopped: bool = False


class FakeDryRunLiveKitPublisherClient:
    def __init__(
        self,
        start_result: LiveKitPublisherResult | None = None,
        stop_result: LiveKitPublisherResult | None = None,
    ) -> None:
        self.start_result = LiveKitPublisherResult(ok=True) if start_result is None else start_result
        self.stop_result = LiveKitPublisherResult(ok=True) if stop_result is None else stop_result
        self.start_calls: list[DryRunPublisherCall] = []
        self.stop_calls: list[dict[str, str]] = []

    async def start_publish(self, request: LiveKitPublishRequest) -> LiveKitPublisherResult:
        self.start_calls.append(
            DryRunPublisherCall(
                camera_id=request.camera_id,
                room=request.room,
                livekit_url=request.livekit_url,
                source_url=request.source_url,
                token_present=bool(request.token.strip()),
            )
        )
        return self.start_result

    async def stop_publish(self, *, camera_id: str, room: str) -> LiveKitPublisherResult:
        self.stop_calls.append({"camera_id": camera_id, "room": room})
        return self.stop_result


class SyntheticPublishDryRun:
    def __init__(
        self,
        config: SyntheticPublishDryRunConfig | None = None,
        publisher: LiveKitPublisherClient | None = None,
        mediamtx_lifecycle: DryRunMediamtxLifecycle | None = None,
    ) -> None:
        self.config = SyntheticPublishDryRunConfig() if config is None else config
        self.publisher = FakeDryRunLiveKitPublisherClient() if publisher is None else publisher
        self.mediamtx_lifecycle = mediamtx_lifecycle
        self.controller = LiveKitMediaController(
            publisher=self.publisher,
            source_url=self.config.source_url,
        )
        self.executor = CommandExecutor(self.controller)

    def build_commands(self, *, now: datetime | None = None) -> tuple[GatewayCommand, ...]:
        current_time = datetime.now(timezone.utc) if now is None else _normalize_datetime(now)
        expires_at = current_time + timedelta(seconds=self.config.command_ttl_seconds)
        token_expires_at = _format_datetime(expires_at)
        start = _signed_command(
            GatewayCommand(
                command_id="dry-run-start-publish",
                kind="gateway.command.start_publish",
                gateway_id=self.config.gateway_id,
                issued_at=current_time,
                expires_at=expires_at,
                payload={
                    "camera_id": self.config.camera_id,
                    "room": self.config.room,
                    "livekit_url": self.config.livekit_url,
                    "gateway_publish_token": self.config.gateway_publish_token,
                    "token_expires_at": token_expires_at,
                },
            ),
            self.config.signing_key,
        )
        stop = _signed_command(
            GatewayCommand(
                command_id="dry-run-stop-publish",
                kind="gateway.command.stop_publish",
                gateway_id=self.config.gateway_id,
                issued_at=current_time,
                expires_at=expires_at,
                payload={"camera_id": self.config.camera_id, "room": self.config.room},
            ),
            self.config.signing_key,
        )
        if self.config.duplicate_start:
            duplicate = replace(start, command_id="dry-run-start-publish-duplicate")
            duplicate = _signed_command(replace(duplicate, signature=""), self.config.signing_key)
            return (start, duplicate, stop)
        return (start, stop)

    def run(
        self,
        *,
        commands: Sequence[GatewayCommand] | None = None,
        now: datetime | None = None,
    ) -> SyntheticPublishDryRunResult:
        errors: list[str] = []
        accepted_commands = 0
        rejected_commands = 0
        mediamtx_started = False
        mediamtx_stopped = False

        if self.mediamtx_lifecycle is not None:
            start_result = self.mediamtx_lifecycle.start()
            if not start_result.ok:
                errors.append(start_result.error or "mediamtx-start-failed")
                return self._result(
                    accepted_commands=0,
                    rejected_commands=1,
                    errors=tuple(errors),
                    mediamtx_started=False,
                    mediamtx_stopped=False,
                )
            mediamtx_started = True

        selected_commands = tuple(self.build_commands(now=now) if commands is None else commands)
        current_time = datetime.now(timezone.utc) if now is None else _normalize_datetime(now)
        try:
            for command in selected_commands:
                try:
                    verify_gateway_command(
                        command,
                        self.config.signing_key,
                        expected_gateway_id=self.config.gateway_id,
                        now=current_time,
                    )
                except CommandVerificationError as exc:
                    rejected_commands += 1
                    errors.append(str(exc))
                    continue
                result = asyncio.run(self.executor.execute(command))
                if result.accepted:
                    accepted_commands += 1
                else:
                    rejected_commands += 1
                    errors.append(result.error or "command-execution-failed")
        finally:
            if self.mediamtx_lifecycle is not None and mediamtx_started:
                stop_result = self.mediamtx_lifecycle.stop()
                if stop_result.ok:
                    mediamtx_stopped = True
                else:
                    errors.append(stop_result.error or "mediamtx-stop-failed")

        return self._result(
            accepted_commands=accepted_commands,
            rejected_commands=rejected_commands,
            errors=tuple(errors),
            mediamtx_started=mediamtx_started,
            mediamtx_stopped=mediamtx_stopped,
        )

    def _result(
        self,
        *,
        accepted_commands: int,
        rejected_commands: int,
        errors: tuple[str, ...],
        mediamtx_started: bool,
        mediamtx_stopped: bool,
    ) -> SyntheticPublishDryRunResult:
        publisher = self.publisher
        start_calls = tuple(getattr(publisher, "start_calls", ()))
        stop_calls = tuple(getattr(publisher, "stop_calls", ()))
        return SyntheticPublishDryRunResult(
            ok=rejected_commands == 0 and not errors,
            accepted_commands=accepted_commands,
            rejected_commands=rejected_commands,
            errors=errors,
            publisher_start_calls=start_calls,
            publisher_stop_calls=stop_calls,
            source_url=self.config.source_url,
            mediamtx_started=mediamtx_started,
            mediamtx_stopped=mediamtx_stopped,
        )


def run_synthetic_publish_dry_run(
    config: SyntheticPublishDryRunConfig | None = None,
) -> SyntheticPublishDryRunResult:
    return SyntheticPublishDryRun(config=config).run()


def _signed_command(command: GatewayCommand, signing_key: str) -> GatewayCommand:
    body = canonical_command_json(command).encode("utf-8")
    digest = hmac.new(signing_key.strip().encode("utf-8"), body, hashlib.sha256).digest()
    signature = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return replace(command, signature=signature)


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _format_datetime(value: datetime) -> str:
    return _normalize_datetime(value).isoformat(timespec="seconds").replace("+00:00", "Z")
