from __future__ import annotations

from dataclasses import dataclass

from panoptix_edge_agent.ffmpeg_rtsp_frame_source import (
    FfmpegProcessFactory,
    FfmpegRtspFrameSource,
    FfmpegRtspFrameSourceConfig,
)
from panoptix_edge_agent.livekit_publisher import (
    LiveKitMediaSession,
    LiveKitPublishRequest,
    LiveKitRtcModule,
    LiveKitSdkPublisherClient,
    LiveKitSdkRoom,
    LiveKitVideoTrackMediaSession,
)
from panoptix_edge_agent.publish_dry_run import (
    SyntheticPublishDryRun,
    SyntheticPublishDryRunConfig,
    SyntheticPublishDryRunResult,
)


@dataclass(frozen=True)
class FfmpegVideoTrackSettings:
    width: int = 1280
    height: int = 720
    frame_rate: int = 30
    ffmpeg_binary: str = "ffmpeg"
    stop_timeout_seconds: float = 5.0
    frame_stall_timeout_seconds: float = 10.0


class FfmpegVideoTrackMediaSessionFactory:
    def __init__(
        self,
        *,
        rtc_module: LiveKitRtcModule,
        settings: FfmpegVideoTrackSettings | None = None,
        process_factory: FfmpegProcessFactory | None = None,
    ) -> None:
        self.rtc_module = rtc_module
        self.settings = FfmpegVideoTrackSettings() if settings is None else settings
        self.process_factory = process_factory
        self.created_configs: list[FfmpegRtspFrameSourceConfig] = []

    def __call__(
        self,
        *,
        request: LiveKitPublishRequest,
        room: LiveKitSdkRoom,
    ) -> LiveKitMediaSession:
        config = FfmpegRtspFrameSourceConfig(
            rtsp_url=request.source_url,
            width=self.settings.width,
            height=self.settings.height,
            frame_rate=self.settings.frame_rate,
            ffmpeg_binary=self.settings.ffmpeg_binary,
            stop_timeout_seconds=self.settings.stop_timeout_seconds,
            rtsp_username=request.rtsp_username,
            rtsp_password=request.rtsp_password,
            rtsp_transport=request.rtsp_transport,
        )
        self.created_configs.append(config)
        frame_source = FfmpegRtspFrameSource(
            config,
            process_factory=self.process_factory,
        )
        return LiveKitVideoTrackMediaSession(
            request=request,
            room=room,
            rtc_module=self.rtc_module,
            frame_source=frame_source,
            frame_stall_timeout=self.settings.frame_stall_timeout_seconds,
        )


@dataclass(frozen=True)
class SyntheticFfmpegToLiveKitSmokeResult:
    dry_run_result: SyntheticPublishDryRunResult
    frame_source_configs: tuple[FfmpegRtspFrameSourceConfig, ...]

    @property
    def ok(self) -> bool:
        return self.dry_run_result.ok


def build_ffmpeg_video_track_media_session_factory(
    *,
    rtc_module: LiveKitRtcModule,
    settings: FfmpegVideoTrackSettings | None = None,
    process_factory: FfmpegProcessFactory | None = None,
) -> FfmpegVideoTrackMediaSessionFactory:
    return FfmpegVideoTrackMediaSessionFactory(
        rtc_module=rtc_module,
        settings=settings,
        process_factory=process_factory,
    )


def build_ffmpeg_livekit_publisher(
    *,
    rtc_module: LiveKitRtcModule,
    settings: FfmpegVideoTrackSettings | None = None,
    process_factory: FfmpegProcessFactory | None = None,
) -> LiveKitSdkPublisherClient:
    session_factory = build_ffmpeg_video_track_media_session_factory(
        rtc_module=rtc_module,
        settings=settings,
        process_factory=process_factory,
    )
    return LiveKitSdkPublisherClient(
        rtc_module=rtc_module,
        media_session_factory=session_factory,
    )


def run_synthetic_ffmpeg_to_livekit_smoke(
    *,
    rtc_module: LiveKitRtcModule,
    process_factory: FfmpegProcessFactory,
    config: SyntheticPublishDryRunConfig | None = None,
    settings: FfmpegVideoTrackSettings | None = None,
) -> SyntheticFfmpegToLiveKitSmokeResult:
    session_factory = build_ffmpeg_video_track_media_session_factory(
        rtc_module=rtc_module,
        settings=settings,
        process_factory=process_factory,
    )
    publisher = LiveKitSdkPublisherClient(
        rtc_module=rtc_module,
        media_session_factory=session_factory,
    )
    dry_run_result = SyntheticPublishDryRun(config=config, publisher=publisher).run()
    return SyntheticFfmpegToLiveKitSmokeResult(
        dry_run_result=dry_run_result,
        frame_source_configs=tuple(session_factory.created_configs),
    )
