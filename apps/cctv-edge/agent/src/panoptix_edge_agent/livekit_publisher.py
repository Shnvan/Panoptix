from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

from panoptix_edge_agent.media import PublishResult, StopResult


class LiveKitPublisherError(ValueError):
    pass


@dataclass(frozen=True)
class LiveKitPublishRequest:
    camera_id: str
    room: str
    livekit_url: str
    token: str
    source_url: str

    def validate(self) -> None:
        _validate_non_empty(self.camera_id, "camera_id")
        _validate_non_empty(self.room, "room")
        _validate_non_empty(self.token, "token")
        _validate_livekit_url(self.livekit_url)
        _validate_source_url(self.source_url)


@dataclass(frozen=True)
class LiveKitPublisherResult:
    ok: bool
    error: str | None = None


class LiveKitPublisherClient(Protocol):
    async def start_publish(self, request: LiveKitPublishRequest) -> LiveKitPublisherResult:
        raise NotImplementedError

    async def stop_publish(self, *, camera_id: str, room: str) -> LiveKitPublisherResult:
        raise NotImplementedError


class SdkUnavailableLiveKitPublisherClient:
    async def start_publish(self, request: LiveKitPublishRequest) -> LiveKitPublisherResult:
        return LiveKitPublisherResult(ok=False, error="livekit-sdk-unavailable")

    async def stop_publish(self, *, camera_id: str, room: str) -> LiveKitPublisherResult:
        return LiveKitPublisherResult(ok=False, error="livekit-sdk-unavailable")


class LiveKitMediaController:
    def __init__(
        self,
        publisher: LiveKitPublisherClient | None = None,
        source_url: str = "rtsp://127.0.0.1:8554/synthetic-camera-1",
    ) -> None:
        self.publisher = SdkUnavailableLiveKitPublisherClient() if publisher is None else publisher
        self.source_url = source_url
        self.active_sessions: dict[str, LiveKitPublishRequest] = {}

    async def start_publish(
        self,
        *,
        camera_id: str,
        room: str,
        livekit_url: str,
        token: str,
    ) -> PublishResult:
        request = LiveKitPublishRequest(
            camera_id=camera_id,
            room=room,
            livekit_url=livekit_url,
            token=token,
            source_url=self.source_url,
        )
        try:
            request.validate()
        except LiveKitPublisherError as exc:
            return PublishResult(ok=False, error=str(exc))

        active = self.active_sessions.get(camera_id)
        if active is not None:
            if active.room != room:
                return PublishResult(ok=False, error="livekit-publish-room-mismatch")
            return PublishResult(ok=True)

        result = await self.publisher.start_publish(request)
        if not result.ok:
            return PublishResult(ok=False, error=result.error or "livekit-publish-start-failed")
        self.active_sessions[camera_id] = request
        return PublishResult(ok=True)

    async def stop_publish(
        self,
        *,
        camera_id: str,
        room: str,
    ) -> StopResult:
        try:
            _validate_non_empty(camera_id, "camera_id")
            _validate_non_empty(room, "room")
        except LiveKitPublisherError as exc:
            return StopResult(ok=False, error=str(exc))

        active = self.active_sessions.get(camera_id)
        if active is None:
            return StopResult(ok=True)
        if active.room != room:
            return StopResult(ok=False, error="livekit-publish-room-mismatch")

        result = await self.publisher.stop_publish(camera_id=camera_id, room=room)
        if not result.ok:
            return StopResult(ok=False, error=result.error or "livekit-publish-stop-failed")
        self.active_sessions.pop(camera_id, None)
        return StopResult(ok=True)


def _validate_non_empty(raw: str, name: str) -> None:
    if not raw.strip():
        raise LiveKitPublisherError(f"{name} is required")


def _validate_livekit_url(raw: str) -> None:
    parsed = urlsplit(raw)
    if parsed.scheme not in {"ws", "wss"} or not parsed.netloc:
        raise LiveKitPublisherError("livekit_url must be a ws:// or wss:// URL")
    if parsed.username is not None or parsed.password is not None:
        raise LiveKitPublisherError("livekit_url must not include credentials")


def _validate_source_url(raw: str) -> None:
    parsed = urlsplit(raw)
    if parsed.scheme not in {"rtsp", "rtsps"} or not parsed.netloc:
        raise LiveKitPublisherError("source_url must be an rtsp:// or rtsps:// URL")
    if parsed.username is not None or parsed.password is not None:
        raise LiveKitPublisherError("source_url must not include credentials")
