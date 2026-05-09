from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PublishSession:
    camera_id: str
    room: str
    token: str
    token_expires_at: str
    started_at: datetime


class PublishState:
    def __init__(self) -> None:
        self._sessions: dict[str, PublishSession] = {}

    def start(
        self,
        *,
        camera_id: str,
        room: str,
        token: str,
        token_expires_at: str,
        started_at: datetime,
    ) -> bool:
        if camera_id in self._sessions:
            return False
        self._sessions[camera_id] = PublishSession(
            camera_id=camera_id,
            room=room,
            token=token,
            token_expires_at=token_expires_at,
            started_at=started_at,
        )
        return True

    def stop(self, camera_id: str) -> bool:
        if camera_id not in self._sessions:
            return False
        del self._sessions[camera_id]
        return True

    def is_publishing(self, camera_id: str) -> bool:
        return camera_id in self._sessions

    def active_sessions(self) -> dict[str, PublishSession]:
        return dict(self._sessions)
