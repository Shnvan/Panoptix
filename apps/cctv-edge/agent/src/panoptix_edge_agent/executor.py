from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from panoptix_edge_agent.camera_credentials import (
    CameraCredentialStore,
    build_rtsp_url,
)
from panoptix_edge_agent.commands import GatewayCommand
from panoptix_edge_agent.media import MediaController
from panoptix_edge_agent.publish_state import PublishState


@dataclass(frozen=True)
class CommandExecutionResult:
    accepted: bool
    error: str | None = None


class CommandExecutor:
    def __init__(
        self,
        media_controller: MediaController,
        publish_state: PublishState | None = None,
        credential_store: CameraCredentialStore | None = None,
    ) -> None:
        self.media_controller = media_controller
        self.publish_state = publish_state if publish_state is not None else PublishState()
        self.credential_store = credential_store

    async def execute(self, command: GatewayCommand) -> CommandExecutionResult:
        if command.kind == "gateway.command.start_publish":
            return await self._execute_start_publish(command)
        if command.kind == "gateway.command.stop_publish":
            return await self._execute_stop_publish(command)
        return CommandExecutionResult(
            accepted=False,
            error="command-kind-unsupported",
        )

    async def _execute_start_publish(self, command: GatewayCommand) -> CommandExecutionResult:
        camera_id = _str_field(command.payload, "camera_id")
        room = _str_field(command.payload, "room")
        livekit_url = _str_field(command.payload, "livekit_url")
        token = _str_field(command.payload, "gateway_publish_token")
        token_expires_at = _str_field(command.payload, "token_expires_at")

        if camera_id is None or room is None or livekit_url is None or token is None or token_expires_at is None:
            return CommandExecutionResult(
                accepted=False,
                error="command-payload-incomplete",
            )

        if self.publish_state.is_publishing(camera_id):
            return CommandExecutionResult(accepted=True)

        source_url: str | None = None
        rtsp_username: str | None = None
        rtsp_password: str | None = None
        rtsp_transport: str | None = None
        if self.credential_store is not None:
            credential = self.credential_store.resolve(camera_id)
            if credential is None:
                return CommandExecutionResult(
                    accepted=False,
                    error="camera-credentials-not-found",
                )
            source_url = build_rtsp_url(credential)
            rtsp_username = credential.username
            rtsp_password = credential.password
            rtsp_transport = credential.rtsp_transport

        result = await self.media_controller.start_publish(
            camera_id=camera_id,
            room=room,
            livekit_url=livekit_url,
            token=token,
            source_url=source_url,
            rtsp_username=rtsp_username,
            rtsp_password=rtsp_password,
            rtsp_transport=rtsp_transport,
        )
        if not result.ok:
            return CommandExecutionResult(accepted=False, error=result.error)

        self.publish_state.start(
            camera_id=camera_id,
            room=room,
            token=token,
            token_expires_at=token_expires_at,
            started_at=datetime.now(timezone.utc),
        )
        return CommandExecutionResult(accepted=True)

    async def _execute_stop_publish(self, command: GatewayCommand) -> CommandExecutionResult:
        camera_id = _str_field(command.payload, "camera_id")
        room = _str_field(command.payload, "room")

        if camera_id is None or room is None:
            return CommandExecutionResult(
                accepted=False,
                error="command-payload-incomplete",
            )

        if not self.publish_state.is_publishing(camera_id):
            return CommandExecutionResult(accepted=True)

        result = await self.media_controller.stop_publish(
            camera_id=camera_id,
            room=room,
        )
        if not result.ok:
            return CommandExecutionResult(accepted=False, error=result.error)

        self.publish_state.stop(camera_id)
        return CommandExecutionResult(accepted=True)


def _str_field(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if isinstance(value, str) and value:
        return value
    return None
