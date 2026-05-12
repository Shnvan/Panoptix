from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PublishResult:
    ok: bool
    error: str | None = None


@dataclass(frozen=True)
class StopResult:
    ok: bool
    error: str | None = None


class MediaController(Protocol):
    async def start_publish(
        self,
        *,
        camera_id: str,
        room: str,
        livekit_url: str,
        token: str,
        source_url: str | None = None,
        rtsp_username: str | None = None,
        rtsp_password: str | None = None,
        rtsp_transport: str | None = None,
    ) -> PublishResult:
        raise NotImplementedError

    async def stop_publish(
        self,
        *,
        camera_id: str,
        room: str,
    ) -> StopResult:
        raise NotImplementedError


class StubMediaController:
    def __init__(self) -> None:
        self.start_calls: list[dict[str, str]] = []
        self.stop_calls: list[dict[str, str]] = []

    async def start_publish(
        self,
        *,
        camera_id: str,
        room: str,
        livekit_url: str,
        token: str,
        source_url: str | None = None,
        rtsp_username: str | None = None,
        rtsp_password: str | None = None,
        rtsp_transport: str | None = None,
    ) -> PublishResult:
        call: dict[str, str] = {
            "camera_id": camera_id,
            "room": room,
            "livekit_url": livekit_url,
            "token": token,
        }
        if source_url is not None:
            call["source_url"] = source_url
        self.start_calls.append(call)
        return PublishResult(ok=True)

    async def stop_publish(
        self,
        *,
        camera_id: str,
        room: str,
    ) -> StopResult:
        self.stop_calls.append({"camera_id": camera_id, "room": room})
        return StopResult(ok=True)


class FailingMediaController:
    def __init__(self, error: str = "media-controller-error") -> None:
        self._error = error

    async def start_publish(
        self,
        *,
        camera_id: str,
        room: str,
        livekit_url: str,
        token: str,
        source_url: str | None = None,
        rtsp_username: str | None = None,
        rtsp_password: str | None = None,
        rtsp_transport: str | None = None,
    ) -> PublishResult:
        return PublishResult(ok=False, error=self._error)

    async def stop_publish(
        self,
        *,
        camera_id: str,
        room: str,
    ) -> StopResult:
        return StopResult(ok=False, error=self._error)
