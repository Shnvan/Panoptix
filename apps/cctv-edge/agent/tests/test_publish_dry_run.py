from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from panoptix_edge_agent.livekit_publisher import LiveKitPublisherResult
from panoptix_edge_agent.mediamtx_process import MediamtxStartResult, MediamtxStopResult
from panoptix_edge_agent.publish_dry_run import (
    FakeDryRunLiveKitPublisherClient,
    SyntheticPublishDryRun,
    SyntheticPublishDryRunConfig,
    run_synthetic_publish_dry_run,
)

NOW = datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc)


class FakeMediamtxLifecycle:
    def __init__(
        self,
        start_result: MediamtxStartResult | None = None,
        stop_result: MediamtxStopResult | None = None,
    ) -> None:
        self.start_result = MediamtxStartResult(ok=True, started=True) if start_result is None else start_result
        self.stop_result = MediamtxStopResult(ok=True, stopped=True) if stop_result is None else stop_result
        self.start_calls = 0
        self.stop_calls = 0

    def start(self) -> MediamtxStartResult:
        self.start_calls += 1
        return self.start_result

    def stop(self) -> MediamtxStopResult:
        self.stop_calls += 1
        return self.stop_result


def test_synthetic_publish_dry_run_accepts_start_and_stop() -> None:
    result = run_synthetic_publish_dry_run()

    assert result.ok is True
    assert result.accepted_commands == 2
    assert result.rejected_commands == 0
    assert result.errors == ()
    assert len(result.publisher_start_calls) == 1
    assert result.publisher_start_calls[0].camera_id == "camera-1"
    assert result.publisher_start_calls[0].room == "camera_ab12cd34"
    assert result.publisher_start_calls[0].livekit_url == "wss://livekit.example.test"
    assert result.publisher_start_calls[0].source_url == "rtsp://127.0.0.1:8554/synthetic-camera-1"
    assert result.publisher_start_calls[0].token_present is True
    assert result.publisher_stop_calls == ({"camera_id": "camera-1", "room": "camera_ab12cd34"},)


def test_synthetic_publish_dry_run_uses_custom_safe_config() -> None:
    config = SyntheticPublishDryRunConfig(
        gateway_id="gateway-2",
        signing_key="another-signing-key",
        camera_id="camera-2",
        room="camera_custom",
        livekit_url="ws://livekit.local.test",
        gateway_publish_token="custom-token",
        source_url="rtsp://127.0.0.1:8554/custom-synthetic",
    )

    result = run_synthetic_publish_dry_run(config)

    assert result.ok is True
    assert result.publisher_start_calls[0].camera_id == "camera-2"
    assert result.publisher_start_calls[0].room == "camera_custom"
    assert result.publisher_start_calls[0].livekit_url == "ws://livekit.local.test"
    assert result.publisher_start_calls[0].source_url == "rtsp://127.0.0.1:8554/custom-synthetic"


def test_synthetic_publish_dry_run_can_include_fake_mediamtx_lifecycle() -> None:
    lifecycle = FakeMediamtxLifecycle()
    dry_run = SyntheticPublishDryRun(mediamtx_lifecycle=lifecycle)

    result = dry_run.run(now=NOW)

    assert result.ok is True
    assert result.mediamtx_started is True
    assert result.mediamtx_stopped is True
    assert lifecycle.start_calls == 1
    assert lifecycle.stop_calls == 1


def test_synthetic_publish_dry_run_reports_mediamtx_start_failure() -> None:
    lifecycle = FakeMediamtxLifecycle(
        start_result=MediamtxStartResult(ok=False, error="mediamtx-start-failed")
    )
    dry_run = SyntheticPublishDryRun(mediamtx_lifecycle=lifecycle)

    result = dry_run.run(now=NOW)

    assert result.ok is False
    assert result.accepted_commands == 0
    assert result.rejected_commands == 1
    assert result.errors == ("mediamtx-start-failed",)
    assert result.publisher_start_calls == ()
    assert lifecycle.start_calls == 1
    assert lifecycle.stop_calls == 0


def test_synthetic_publish_dry_run_reports_mediamtx_stop_failure_after_commands() -> None:
    lifecycle = FakeMediamtxLifecycle(
        stop_result=MediamtxStopResult(ok=False, error="mediamtx-stop-failed")
    )
    dry_run = SyntheticPublishDryRun(mediamtx_lifecycle=lifecycle)

    result = dry_run.run(now=NOW)

    assert result.ok is False
    assert result.accepted_commands == 2
    assert result.rejected_commands == 0
    assert result.errors == ("mediamtx-stop-failed",)
    assert result.mediamtx_started is True
    assert result.mediamtx_stopped is False
    assert lifecycle.stop_calls == 1


def test_synthetic_publish_dry_run_duplicate_start_is_idempotent() -> None:
    config = SyntheticPublishDryRunConfig(duplicate_start=True)
    dry_run = SyntheticPublishDryRun(config=config)

    result = dry_run.run(now=NOW)

    assert result.ok is True
    assert result.accepted_commands == 3
    assert result.rejected_commands == 0
    assert len(result.publisher_start_calls) == 1
    assert result.publisher_stop_calls == ({"camera_id": "camera-1", "room": "camera_ab12cd34"},)


def test_synthetic_publish_dry_run_stop_without_active_publish_is_safe() -> None:
    dry_run = SyntheticPublishDryRun()
    commands = dry_run.build_commands(now=NOW)

    result = dry_run.run(commands=(commands[-1],), now=NOW)

    assert result.ok is True
    assert result.accepted_commands == 1
    assert result.rejected_commands == 0
    assert result.publisher_start_calls == ()
    assert result.publisher_stop_calls == ()


def test_synthetic_publish_dry_run_rejects_tampered_command_before_executor() -> None:
    dry_run = SyntheticPublishDryRun()
    start, stop = dry_run.build_commands(now=NOW)
    tampered = replace(
        start,
        payload={
            "camera_id": "camera-1",
            "room": "camera_ab12cd34",
            "livekit_url": "wss://evil.example.test",
            "gateway_publish_token": "dry-run-gateway-publish-token",
            "token_expires_at": "2026-05-07T12:01:00Z",
        },
    )

    result = dry_run.run(commands=(tampered, stop), now=NOW)

    assert result.ok is False
    assert result.accepted_commands == 1
    assert result.rejected_commands == 1
    assert result.errors == ("gateway-command-signature-invalid",)
    assert result.publisher_start_calls == ()
    assert result.publisher_stop_calls == ()


def test_synthetic_publish_dry_run_rejects_wrong_gateway() -> None:
    dry_run = SyntheticPublishDryRun()
    start, = dry_run.build_commands(now=NOW)[:1]
    wrong_gateway = replace(start, gateway_id="wrong-gateway")

    result = dry_run.run(commands=(wrong_gateway,), now=NOW)

    assert result.ok is False
    assert result.accepted_commands == 0
    assert result.rejected_commands == 1
    assert result.errors == ("gateway-command-target-mismatch",)
    assert result.publisher_start_calls == ()


def test_synthetic_publish_dry_run_surfaces_publisher_start_failure() -> None:
    publisher = FakeDryRunLiveKitPublisherClient(
        start_result=LiveKitPublisherResult(ok=False, error="publish-start-failed")
    )
    dry_run = SyntheticPublishDryRun(publisher=publisher)

    result = dry_run.run(now=NOW)

    assert result.ok is False
    assert result.accepted_commands == 1
    assert result.rejected_commands == 1
    assert result.errors == ("publish-start-failed",)
    assert len(result.publisher_start_calls) == 1
    assert result.publisher_stop_calls == ()


def test_synthetic_publish_dry_run_surfaces_publisher_stop_failure() -> None:
    publisher = FakeDryRunLiveKitPublisherClient(
        stop_result=LiveKitPublisherResult(ok=False, error="publish-stop-failed")
    )
    dry_run = SyntheticPublishDryRun(publisher=publisher)

    result = dry_run.run(now=NOW)

    assert result.ok is False
    assert result.accepted_commands == 1
    assert result.rejected_commands == 1
    assert result.errors == ("publish-stop-failed",)
    assert len(result.publisher_start_calls) == 1
    assert result.publisher_stop_calls == ({"camera_id": "camera-1", "room": "camera_ab12cd34"},)
