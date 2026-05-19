from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PrincipalKind(str, Enum):
    USER = "user"
    GATEWAY = "gateway"


@dataclass(frozen=True)
class Principal:
    kind: PrincipalKind
    subject: str
    email: str | None = None
    roles: frozenset[str] = field(default_factory=frozenset)
    permissions: frozenset[str] = field(default_factory=frozenset)
    gateway_id: str | None = None
    is_dev: bool = False

    def to_response(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "subject": self.subject,
            "email": self.email,
            "roles": sorted(self.roles),
            "permissions": sorted(self.permissions),
            "gateway_id": self.gateway_id,
            "is_dev": self.is_dev,
        }
