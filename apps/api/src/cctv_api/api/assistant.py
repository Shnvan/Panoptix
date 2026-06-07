from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session as DbSession

from cctv_api.api.errors import ProblemDetail
from cctv_api.assistant import (
    AssistantMessage,
    AssistantProviderError,
    build_operations_snapshot,
    complete_chat,
)
from cctv_api.core.config import Settings, get_settings
from cctv_api.db import db_session
from cctv_api.models.enums import ActorType
from cctv_api.security.audit import record_audit_event
from cctv_api.security.dependencies import require_authenticated_user
from cctv_api.security.identity import Principal
from cctv_api.security.policy import require_role
from cctv_api.security.rate_limit import RateLimitConfig, get_rate_limiter
from cctv_api.security.users import get_or_create_user

router = APIRouter()


class AssistantChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class AssistantChatRequest(BaseModel):
    messages: list[AssistantChatMessage] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_conversation(self) -> "AssistantChatRequest":
        if sum(len(message.content) for message in self.messages) > 12000:
            raise ValueError("assistant-conversation-too-large")
        if self.messages[-1].role != "user":
            raise ValueError("assistant-last-message-must-be-user")
        for index, message in enumerate(self.messages):
            expected = "user" if index % 2 == 0 else "assistant"
            if message.role != expected:
                raise ValueError("assistant-message-order-invalid")
        return self


class AssistantStatusResponse(BaseModel):
    enabled: bool
    provider: str
    model: str
    max_history_messages: int = 20
    page_session_limit: int = 50


class AssistantChatResponse(BaseModel):
    message: str
    model: str
    context_categories: list[str]


@router.get("/admin/assistant/status")
def assistant_status(
    principal: Principal = Depends(require_authenticated_user),
    settings: Settings = Depends(get_settings),
) -> AssistantStatusResponse:
    require_role(principal, "admin")
    return AssistantStatusResponse(
        enabled=settings.AI_ASSISTANT_ENABLED,
        provider="openai-compatible",
        model=settings.AI_ASSISTANT_MODEL,
    )


@router.post("/admin/assistant/chat")
def assistant_chat(
    body: AssistantChatRequest,
    request: Request,
    principal: Principal = Depends(require_authenticated_user),
    db: DbSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> AssistantChatResponse:
    require_role(principal, "admin")
    if not settings.AI_ASSISTANT_ENABLED:
        raise ProblemDetail(
            status=503,
            title="Service Unavailable",
            detail="assistant-disabled",
            type_uri="https://panoptix.local/problems/service-unavailable",
        )

    actor = get_or_create_user(
        db,
        email=principal.email or principal.subject,
        idp_subject=principal.subject,
    )
    rate_result = get_rate_limiter().check(
        f"ai-assistant:{actor.id}",
        RateLimitConfig(
            max_requests=settings.RATE_LIMIT_AI_ASSISTANT_MAX,
            window_seconds=settings.RATE_LIMIT_AI_ASSISTANT_WINDOW,
        ),
    )
    if not rate_result.allowed:
        _record_assistant_audit(
            db,
            settings=settings,
            request=request,
            actor_id=actor.id,
            action="admin.assistant.rate_limited",
            payload=_audit_payload(body, settings, outcome="rate_limited"),
        )
        raise ProblemDetail(
            status=429,
            title="Too Many Requests",
            detail="assistant-rate-limited",
            type_uri="https://panoptix.local/problems/rate-limited",
            headers={"Retry-After": str(rate_result.retry_after)},
        )

    snapshot = build_operations_snapshot(db, settings)
    _record_assistant_audit(
        db,
        settings=settings,
        request=request,
        actor_id=actor.id,
        action="admin.assistant.requested",
        payload=_audit_payload(body, settings, outcome="requested"),
    )

    try:
        answer = complete_chat(
            settings,
            [AssistantMessage(role=item.role, content=item.content) for item in body.messages],
            snapshot,
        )
    except AssistantProviderError as exc:
        _record_assistant_audit(
            db,
            settings=settings,
            request=request,
            actor_id=actor.id,
            action="admin.assistant.failed",
            payload=_audit_payload(body, settings, outcome=exc.detail),
        )
        status = 429 if exc.detail == "assistant-provider-rate-limited" else 502
        raise ProblemDetail(
            status=status,
            title="Too Many Requests" if status == 429 else "Bad Gateway",
            detail=exc.detail,
            type_uri=(
                "https://panoptix.local/problems/rate-limited"
                if status == 429
                else "https://panoptix.local/problems/bad-gateway"
            ),
            headers=(
                {"Retry-After": str(exc.retry_after)}
                if exc.retry_after is not None
                else None
            ),
        ) from exc

    _record_assistant_audit(
        db,
        settings=settings,
        request=request,
        actor_id=actor.id,
        action="admin.assistant.completed",
        payload={
            **_audit_payload(body, settings, outcome="completed"),
            "response_character_count": len(answer),
        },
    )
    return AssistantChatResponse(
        message=answer,
        model=settings.AI_ASSISTANT_MODEL,
        context_categories=["health", "gateways", "cameras", "alerts", "backups"],
    )


def _audit_payload(
    body: AssistantChatRequest,
    settings: Settings,
    *,
    outcome: str,
) -> dict[str, object]:
    return {
        "model": settings.AI_ASSISTANT_MODEL,
        "message_count": len(body.messages),
        "request_character_count": sum(len(message.content) for message in body.messages),
        "context_categories": ["health", "gateways", "cameras", "alerts", "backups"],
        "outcome": outcome,
    }


def _record_assistant_audit(
    db: DbSession,
    *,
    settings: Settings,
    request: Request,
    actor_id: uuid.UUID,
    action: str,
    payload: dict[str, object],
) -> None:
    try:
        record_audit_event(
            db,
            actor_type=ActorType.user,
            actor_id=actor_id,
            action=action,
            resource="admin-assistant",
            payload=payload,
            audit_hmac_key_version=settings.AUDIT_HMAC_KEY_VERSION,
            audit_hmac_key=settings.AUDIT_HMAC_KEY,
            ip=getattr(request.state, "client_ip", None),
            ua=request.headers.get("user-agent"),
            session_id=getattr(request.state, "audit_session_id", None),
        )
    except Exception as exc:
        db.rollback()
        raise ProblemDetail(
            status=503,
            title="Service Unavailable",
            detail="audit-log-write-failed",
            type_uri="https://panoptix.local/problems/service-unavailable",
        ) from exc
