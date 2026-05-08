from __future__ import annotations

from typing import Any

from panoptix_edge_agent.client import AgentClientError, CameraStatusReport
from panoptix_edge_agent.config import AgentConfig
from panoptix_edge_agent.runner import HeartbeatRunner


class FakeClient:
    def __init__(self, response: dict[str, object] | None = None, error: AgentClientError | None = None) -> None:
        self.response = {} if response is None else response
        self.error = error
        self.calls: list[tuple[str, tuple[CameraStatusReport, ...]]] = []

    def send_heartbeat(
        self,
        *,
        status: str = "online",
        cameras: tuple[CameraStatusReport, ...] = (),
    ) -> dict[str, Any]:
        self.calls.append((status, cameras))
        if self.error is not None:
            raise self.error
        return self.response


def test_run_once_sends_online_heartbeat_with_configured_cameras() -> None:
    config = AgentConfig(
        api_base_url="http://api.example.test",
        gateway_id="gateway-1",
        camera_ids=("camera-1", "camera-2"),
    )
    client = FakeClient(response={"pending_commands": []})
    runner = HeartbeatRunner(config, client=client)

    result = runner.run_once()

    assert result.ok is True
    assert result.response == {"pending_commands": []}
    assert len(client.calls) == 1
    status, cameras = client.calls[0]
    assert status == "online"
    assert [camera.camera_id for camera in cameras] == ["camera-1", "camera-2"]
    assert [camera.status for camera in cameras] == ["online", "online"]


def test_run_once_returns_error_result_when_client_fails() -> None:
    config = AgentConfig(api_base_url="http://api.example.test", gateway_id="gateway-1")
    runner = HeartbeatRunner(config, client=FakeClient(error=AgentClientError("boom")))

    result = runner.run_once()

    assert result.ok is False
    assert result.error == "boom"
