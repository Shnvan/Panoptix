from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from panoptix_edge_agent.config import AgentConfig, ConfigError
from panoptix_edge_agent.media import MediaController, StubMediaController

if TYPE_CHECKING:
    from panoptix_edge_agent.ffmpeg_rtsp_frame_source import FfmpegProcessFactory
    from panoptix_edge_agent.livekit_publisher import LiveKitRtcModule


@dataclass(frozen=True)
class MediaFactoryResult:
    controller: MediaController
    mode: str
    error: str | None = None


def build_media_controller(
    config: AgentConfig,
    *,
    rtc_module: LiveKitRtcModule | None = None,
    process_factory: FfmpegProcessFactory | None = None,
) -> MediaFactoryResult:
    """Build the appropriate MediaController based on the agent config.

    Returns a ``MediaFactoryResult`` with the controller and its mode.
    When the mode is ``stub``, a no-op ``StubMediaController`` is returned.
    When the mode is ``livekit-ffmpeg``, the real ``LiveKitMediaController``
    backed by the LiveKit SDK and FFmpeg is constructed.
    """
    if config.media_publisher_mode == "stub":
        return MediaFactoryResult(
            controller=StubMediaController(),
            mode="stub",
        )
    if config.media_publisher_mode == "livekit-ffmpeg":
        return _build_livekit_ffmpeg(config, rtc_module=rtc_module, process_factory=process_factory)
    raise ConfigError(
        f"PANOPTIX_MEDIA_PUBLISHER_MODE must be 'stub' or 'livekit-ffmpeg', "
        f"got '{config.media_publisher_mode}'"
    )


def _build_livekit_ffmpeg(
    config: AgentConfig,
    *,
    rtc_module: LiveKitRtcModule | None = None,
    process_factory: FfmpegProcessFactory | None = None,
) -> MediaFactoryResult:
    from panoptix_edge_agent.ffmpeg_livekit_smoke import (
        FfmpegVideoTrackSettings,
        build_ffmpeg_video_track_media_session_factory,
    )
    from panoptix_edge_agent.livekit_publisher import (
        LiveKitMediaController,
        LiveKitSdkPublisherClient,
    )

    resolved_rtc: LiveKitRtcModule
    try:
        resolved_rtc = _resolve_rtc_module(rtc_module)
    except ImportError:
        return MediaFactoryResult(
            controller=StubMediaController(),
            mode="livekit-ffmpeg",
            error="livekit-sdk-unavailable",
        )
    except Exception:
        return MediaFactoryResult(
            controller=StubMediaController(),
            mode="livekit-ffmpeg",
            error="livekit-sdk-import-failed",
        )

    settings = FfmpegVideoTrackSettings(
        width=config.media_width,
        height=config.media_height,
        frame_rate=config.media_frame_rate,
        ffmpeg_binary=config.media_ffmpeg_binary,
    )
    session_factory = build_ffmpeg_video_track_media_session_factory(
        rtc_module=resolved_rtc,
        settings=settings,
        process_factory=process_factory,
    )
    publisher = LiveKitSdkPublisherClient(
        rtc_module=resolved_rtc,
        media_session_factory=session_factory,
    )
    controller = LiveKitMediaController(
        publisher=publisher,
        source_url=config.media_source_url,
    )
    return MediaFactoryResult(
        controller=controller,
        mode="livekit-ffmpeg",
    )


def _resolve_rtc_module(rtc_module: LiveKitRtcModule | None) -> LiveKitRtcModule:
    if rtc_module is not None:
        return rtc_module
    from typing import cast

    from panoptix_edge_agent.livekit_publisher import LiveKitRtcModule as RtcModuleType

    return cast(RtcModuleType, importlib.import_module("livekit.rtc"))
