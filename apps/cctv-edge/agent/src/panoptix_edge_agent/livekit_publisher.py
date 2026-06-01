from __future__ import annotations

import importlib
import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol, cast
from urllib.parse import urlsplit

from panoptix_edge_agent.media import PublishResult, StopResult

logger = logging.getLogger(__name__)


class LiveKitPublisherError(ValueError):
    pass


@dataclass(frozen=True)
class LiveKitPublishRequest:
    camera_id: str
    room: str
    livekit_url: str
    token: str
    source_url: str
    rtsp_username: str | None = None
    rtsp_password: str | None = None
    rtsp_transport: str = "tcp"

    def __repr__(self) -> str:
        cred = ""
        if self.rtsp_username is not None:
            cred = ", rtsp_username='***', rtsp_password='***'"
        return (
            f"LiveKitPublishRequest(camera_id={self.camera_id!r}, "
            f"room={self.room!r}, livekit_url={self.livekit_url!r}, "
            f"token='***', source_url={self.source_url!r}, "
            f"rtsp_transport={self.rtsp_transport!r}{cred})"
        )

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


@dataclass(frozen=True)
class LiveKitVideoFrame:
    data: bytes
    width: int
    height: int
    timestamp_us: int
    pixel_format: Literal["RGBA"] = "RGBA"

    def validate(self) -> None:
        if self.width <= 0:
            raise LiveKitPublisherError("video frame width must be positive")
        if self.height <= 0:
            raise LiveKitPublisherError("video frame height must be positive")
        if self.timestamp_us < 0:
            raise LiveKitPublisherError("video frame timestamp_us must be non-negative")
        if self.pixel_format != "RGBA":
            raise LiveKitPublisherError("video frame pixel_format must be RGBA")
        expected_bytes = self.width * self.height * 4
        if len(self.data) != expected_bytes:
            raise LiveKitPublisherError("video frame data length does not match RGBA dimensions")


class LiveKitPublisherClient(Protocol):
    async def start_publish(self, request: LiveKitPublishRequest) -> LiveKitPublisherResult:
        raise NotImplementedError

    async def stop_publish(self, *, camera_id: str, room: str) -> LiveKitPublisherResult:
        raise NotImplementedError


class LiveKitSdkRoom(Protocol):
    @property
    def local_participant(self) -> LiveKitLocalParticipant:
        raise NotImplementedError

    async def connect(self, url: str, token: str, options: object) -> None:
        raise NotImplementedError

    async def disconnect(self) -> None:
        raise NotImplementedError


class LiveKitLocalParticipant(Protocol):
    async def publish_track(self, track: object, options: object) -> object:
        raise NotImplementedError

    async def unpublish_track(self, track_sid: str) -> None:
        raise NotImplementedError


class LiveKitVideoSource(Protocol):
    def capture_frame(self, frame: object, *, timestamp_us: int = 0) -> None:
        raise NotImplementedError

    async def aclose(self) -> None:
        raise NotImplementedError


class LiveKitLocalVideoTrackFactory(Protocol):
    def create_video_track(self, name: str, source: LiveKitVideoSource) -> object:
        raise NotImplementedError


class LiveKitRtcModule(Protocol):
    def Room(self) -> LiveKitSdkRoom:
        raise NotImplementedError

    def RoomOptions(self, *, auto_subscribe: bool) -> object:
        raise NotImplementedError

    def VideoSource(self, width: int, height: int, *, is_screencast: bool = False) -> LiveKitVideoSource:
        raise NotImplementedError

    def VideoFrame(self, *, width: int, height: int, type: object, data: bytes) -> object:
        raise NotImplementedError

    def TrackPublishOptions(self, *, source: object) -> object:
        raise NotImplementedError

    @property
    def LocalVideoTrack(self) -> LiveKitLocalVideoTrackFactory:
        raise NotImplementedError

    @property
    def TrackSource(self) -> object:
        raise NotImplementedError

    @property
    def VideoBufferType(self) -> object:
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


class LiveKitVideoFrameSource(Protocol):
    def __aiter__(self) -> AsyncIterator[LiveKitVideoFrame]:
        raise NotImplementedError


class LiveKitVideoFrameSourceFactory(Protocol):
    def __call__(self, request: LiveKitPublishRequest) -> LiveKitVideoFrameSource:
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

    def is_healthy(self) -> bool:
        return True


class LiveKitVideoTrackMediaSession:
    def __init__(
        self,
        *,
        request: LiveKitPublishRequest,
        room: LiveKitSdkRoom,
        rtc_module: LiveKitRtcModule,
        frame_source: LiveKitVideoFrameSource,
        track_name: str | None = None,
    ) -> None:
        self.request = request
        self.room = room
        self.rtc_module = rtc_module
        self.frame_source = frame_source
        self.track_name = track_name or f"camera-{request.camera_id}-video"
        self.video_source: LiveKitVideoSource | None = None
        self.track: object | None = None
        self.publication: object | None = None
        self.frame_task: asyncio.Task[None] | None = None
        self.frame_pump_error: str | None = None
        self._stopped = False

    async def start(self) -> None:
        first_frame = await self._read_first_frame()
        logger.info(
            "livekit first frame read camera_id=%s room=%s width=%s height=%s",
            self.request.camera_id,
            self.request.room,
            first_frame.width,
            first_frame.height,
        )
        self.video_source = self.rtc_module.VideoSource(first_frame.width, first_frame.height)
        self.track = self.rtc_module.LocalVideoTrack.create_video_track(
            self.track_name,
            self.video_source,
        )
        options = self.rtc_module.TrackPublishOptions(source=_track_source_camera(self.rtc_module))
        try:
            self.publication = await self.room.local_participant.publish_track(
                self.track,
                options,
            )
            logger.info(
                "livekit track published camera_id=%s room=%s",
                self.request.camera_id,
                self.request.room,
            )
            self._capture_frame(first_frame)
            self.frame_task = asyncio.create_task(self._pump_frames())
        except Exception:
            await self._cleanup_after_start_failure()
            raise

    async def stop(self) -> None:
        errors: list[BaseException] = []
        self._stopped = True
        if self.frame_task is not None:
            self.frame_task.cancel()
            try:
                await self.frame_task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                errors.append(exc)
            self.frame_task = None

        track_sid = _publication_sid(self.publication)
        if track_sid is not None:
            try:
                await self.room.local_participant.unpublish_track(track_sid)
            except Exception as exc:
                errors.append(exc)

        try:
            await _safe_aclose(self.video_source)
        except Exception as exc:
            errors.append(exc)
        try:
            await _safe_aclose(self.frame_source)
        except Exception as exc:
            errors.append(exc)

        if errors:
            raise LiveKitPublisherError("livekit video track stop failed")

    async def _read_first_frame(self) -> LiveKitVideoFrame:
        iterator = self.frame_source.__aiter__()
        try:
            first_frame = await anext(iterator)
        except StopAsyncIteration as exc:
            await _safe_aclose(self.frame_source)
            raise LiveKitPublisherError("video frame source produced no frames") from exc
        first_frame.validate()
        return first_frame

    async def _pump_frames(self) -> None:
        try:
            async for frame in self.frame_source:
                if self._stopped:
                    return
                self._capture_frame(frame)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.frame_pump_error = "livekit-frame-pump-failed"
            logger.warning(
                "livekit frame pump failed camera_id=%s room=%s error_type=%s",
                self.request.camera_id,
                self.request.room,
                type(exc).__name__,
            )

    def is_healthy(self) -> bool:
        if self._stopped or self.frame_pump_error is not None:
            return False
        if self.frame_task is None:
            return self.publication is not None
        return not self.frame_task.done()

    def _capture_frame(self, frame: LiveKitVideoFrame) -> None:
        if self.video_source is None:
            raise LiveKitPublisherError("video source is not initialized")
        frame.validate()
        sdk_frame = self.rtc_module.VideoFrame(
            width=frame.width,
            height=frame.height,
            type=_video_buffer_type_rgba(self.rtc_module),
            data=frame.data,
        )
        self.video_source.capture_frame(sdk_frame, timestamp_us=frame.timestamp_us)

    async def _cleanup_after_start_failure(self) -> None:
        await _safe_aclose(self.video_source)
        await _safe_aclose(self.frame_source)


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
        logger.info(
            "livekit start publish received camera_id=%s room=%s",
            request.camera_id,
            request.room,
        )
        active = self.active_sessions.get(request.camera_id)
        if active is not None:
            if active.request.room != request.room:
                return LiveKitPublisherResult(ok=False, error="livekit-publish-room-mismatch")
            if _media_session_is_healthy(active.media_session):
                return LiveKitPublisherResult(ok=True)
            logger.warning(
                "livekit active session unhealthy; restarting camera_id=%s room=%s",
                request.camera_id,
                request.room,
            )
            await _safe_stop_media_session(active.media_session)
            await _safe_disconnect_room(active.room)
            self.active_sessions.pop(request.camera_id, None)

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

    def is_publishing_healthy(self, *, camera_id: str, room: str) -> bool:
        active = self.active_sessions.get(camera_id)
        return (
            active is not None
            and active.request.room == room
            and _media_session_is_healthy(active.media_session)
        )

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

    def build_video_track_media_session_factory(
        self,
        frame_source_factory: LiveKitVideoFrameSourceFactory,
    ) -> LiveKitMediaSessionFactory:
        def factory(
            *,
            request: LiveKitPublishRequest,
            room: LiveKitSdkRoom,
        ) -> LiveKitMediaSession:
            return LiveKitVideoTrackMediaSession(
                request=request,
                room=room,
                rtc_module=self._resolve_rtc_module(),
                frame_source=frame_source_factory(request),
            )

        return factory


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
        source_url: str | None = None,
        rtsp_username: str | None = None,
        rtsp_password: str | None = None,
        rtsp_transport: str | None = None,
    ) -> PublishResult:
        resolved_source = source_url if source_url is not None else self.source_url
        request = LiveKitPublishRequest(
            camera_id=camera_id,
            room=room,
            livekit_url=livekit_url,
            token=token,
            source_url=resolved_source,
            rtsp_username=rtsp_username,
            rtsp_password=rtsp_password,
            rtsp_transport=rtsp_transport or "tcp",
        )
        try:
            request.validate()
        except LiveKitPublisherError as exc:
            return PublishResult(ok=False, error=str(exc))

        active = self.active_sessions.get(camera_id)
        if active is not None:
            if active.room != room:
                return PublishResult(ok=False, error="livekit-publish-room-mismatch")
            if self.is_publishing_healthy(camera_id=camera_id, room=room):
                return PublishResult(ok=True)
            logger.warning(
                "livekit media controller clearing unhealthy session camera_id=%s room=%s",
                camera_id,
                room,
            )
            await self.publisher.stop_publish(camera_id=camera_id, room=room)
            self.active_sessions.pop(camera_id, None)

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

    def is_publishing_healthy(self, *, camera_id: str, room: str) -> bool:
        active = self.active_sessions.get(camera_id)
        if active is None or active.room != room:
            return False
        health_check = getattr(self.publisher, "is_publishing_healthy", None)
        if health_check is None:
            return True
        result = health_check(camera_id=camera_id, room=room)
        return bool(result)


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


async def _safe_aclose(target: object | None) -> None:
    if target is None:
        return
    close = getattr(target, "aclose", None)
    if close is not None:
        await close()
        return
    close = getattr(target, "close", None)
    if close is not None:
        result = close()
        if result is not None:
            await result


def _media_session_is_healthy(media_session: LiveKitMediaSession) -> bool:
    health_check = getattr(media_session, "is_healthy", None)
    if health_check is None:
        return True
    return bool(health_check())


def _track_source_camera(rtc_module: LiveKitRtcModule) -> object:
    track_source = rtc_module.TrackSource
    camera = getattr(track_source, "SOURCE_CAMERA", None)
    if camera is not None:
        return camera
    return getattr(track_source, "CAMERA")


def _video_buffer_type_rgba(rtc_module: LiveKitRtcModule) -> object:
    video_buffer_type = rtc_module.VideoBufferType
    return getattr(video_buffer_type, "RGBA")


def _publication_sid(publication: object | None) -> str | None:
    if publication is None:
        return None
    sid = getattr(publication, "sid", None)
    if isinstance(sid, str) and sid:
        return sid
    return None
