from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Protocol, cast
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


class LiveKitSdkRoom(Protocol):
    async def connect(self, url: str, token: str, options: object) -> None:
        raise NotImplementedError

    async def disconnect(self) -> None:
        raise NotImplementedError


class LiveKitRtcModule(Protocol):
    def Room(self) -> LiveKitSdkRoom:
        raise NotImplementedError

    def RoomOptions(self, *, auto_subscribe: bool) -> object:
        raise NotImplementedError


class LiveKitRtcModuleResolver(Protocol):
    def __call__(self) -> LiveKitRtcModule:
        raise NotImplementedError


class LiveKitMediaSession(Protocol):
    async def start(self) -> None:
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError


class LiveKitMediaSessionFactory(Protocol):
    def __call__(
        self,
        *,
        request: LiveKitPublishRequest,
        room: LiveKitSdkRoom,
    ) -> LiveKitMediaSession:
        raise NotImplementedError


class SdkUnavailableLiveKitPublisherClient:
    async def start_publish(self, request: LiveKitPublishRequest) -> LiveKitPublisherResult:
        return LiveKitPublisherResult(ok=False, error="livekit-sdk-unavailable")

    async def stop_publish(self, *, camera_id: str, room: str) -> LiveKitPublisherResult:
        return LiveKitPublisherResult(ok=False, error="livekit-sdk-unavailable")


class NoopLiveKitMediaSession:
    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None


@dataclass
class LiveKitSdkActiveSession:
    request: LiveKitPublishRequest
    room: LiveKitSdkRoom
    media_session: LiveKitMediaSession


class LiveKitSdkPublisherClient:
    def __init__(
        self,
        *,
        rtc_module: LiveKitRtcModule | None = None,
        rtc_module_resolver: LiveKitRtcModuleResolver | None = None,
        media_session_factory: LiveKitMediaSessionFactory | None = None,
    ) -> None:
        self._rtc_module = rtc_module
        self._rtc_module_resolver = (
            _import_livekit_rtc if rtc_module_resolver is None else rtc_module_resolver
        )
        self._media_session_factory = (
            _noop_media_session_factory
            if media_session_factory is None
            else media_session_factory
        )
        self.active_sessions: dict[str, LiveKitSdkActiveSession] = {}

    async def start_publish(self, request: LiveKitPublishRequest) -> LiveKitPublisherResult:
        active = self.active_sessions.get(request.camera_id)
        if active is not None:
            if active.request.room != request.room:
                return LiveKitPublisherResult(ok=False, error="livekit-publish-room-mismatch")
            return LiveKitPublisherResult(ok=True)

        try:
            rtc_module = self._resolve_rtc_module()
        except ImportError:
            return LiveKitPublisherResult(ok=False, error="livekit-sdk-unavailable")
        except Exception:
            return LiveKitPublisherResult(ok=False, error="livekit-sdk-start-failed")

        room: LiveKitSdkRoom | None = None
        media_session: LiveKitMediaSession | None = None
        try:
            room = rtc_module.Room()
            options = rtc_module.RoomOptions(auto_subscribe=False)
            await room.connect(request.livekit_url, request.token, options)
            media_session = self._media_session_factory(request=request, room=room)
            await media_session.start()
        except Exception:
            await _safe_stop_media_session(media_session)
            await _safe_disconnect_room(room)
            return LiveKitPublisherResult(ok=False, error="livekit-sdk-start-failed")

        self.active_sessions[request.camera_id] = LiveKitSdkActiveSession(
            request=request,
            room=room,
            media_session=media_session,
        )
        return LiveKitPublisherResult(ok=True)

    async def stop_publish(self, *, camera_id: str, room: str) -> LiveKitPublisherResult:
        active = self.active_sessions.get(camera_id)
        if active is None:
            return LiveKitPublisherResult(ok=True)
        if active.request.room != room:
            return LiveKitPublisherResult(ok=False, error="livekit-publish-room-mismatch")

        try:
            await active.media_session.stop()
            await active.room.disconnect()
        except Exception:
            return LiveKitPublisherResult(ok=False, error="livekit-sdk-stop-failed")

        self.active_sessions.pop(camera_id, None)
        return LiveKitPublisherResult(ok=True)

    def _resolve_rtc_module(self) -> LiveKitRtcModule:
        if self._rtc_module is None:
            self._rtc_module = self._rtc_module_resolver()
        return self._rtc_module


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


def _import_livekit_rtc() -> LiveKitRtcModule:
    return cast(LiveKitRtcModule, importlib.import_module("livekit.rtc"))


def _noop_media_session_factory(
    *,
    request: LiveKitPublishRequest,
    room: LiveKitSdkRoom,
) -> LiveKitMediaSession:
    return NoopLiveKitMediaSession()


async def _safe_stop_media_session(media_session: LiveKitMediaSession | None) -> None:
    if media_session is None:
        return
    try:
        await media_session.stop()
    except Exception:
        return


async def _safe_disconnect_room(room: LiveKitSdkRoom | None) -> None:
    if room is None:
        return
    try:
        await room.disconnect()
    except Exception:
        return
