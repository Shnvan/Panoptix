from __future__ import annotations

import enum


class CameraSourceType(str, enum.Enum):
    rtsp = "rtsp"
    nvr_rtsp = "nvr_rtsp"
    onvif_profile_s = "onvif_profile_s"
    onvif_profile_t = "onvif_profile_t"
    synthetic_rtsp_test_source = "synthetic_rtsp_test_source"


class GatewayStatus(str, enum.Enum):
    enabled = "enabled"
    disabled = "disabled"
    retired = "retired"


class CameraEventKind(str, enum.Enum):
    online = "online"
    offline = "offline"
    degraded = "degraded"
    reconnecting = "reconnecting"
    retired = "retired"


class EventSource(str, enum.Enum):
    heartbeat = "heartbeat"
    livekit_webhook = "livekit_webhook"
    mediamtx_callback = "mediamtx_callback"
    admin_action = "admin_action"


class StreamKind(str, enum.Enum):
    viewer_subscribe = "viewer_subscribe"
    gateway_publish = "gateway_publish"


class CameraPublishStatus(str, enum.Enum):
    idle = "idle"
    starting = "starting"
    publishing = "publishing"
    stop_pending = "stop_pending"


class ActorType(str, enum.Enum):
    user = "user"
    gateway = "gateway"
    system = "system"
    break_glass = "break_glass"
    service_token_monitor = "service_token_monitor"


class DpaKind(str, enum.Enum):
    ropa = "ropa"
    processor_dpa = "processor_dpa"
    pia = "pia"
    breach_log = "breach_log"
    retention_policy = "retention_policy"
    bystander_signage_attestation = "bystander_signage_attestation"
    cross_border_transfer_basis = "cross_border_transfer_basis"


class SubjectType(str, enum.Enum):
    user = "user"
    bystander = "bystander"
    site_contact = "site_contact"


class RequestType(str, enum.Enum):
    access = "access"
    correction = "correction"
    deletion = "deletion"
    objection = "objection"
    restriction = "restriction"
    other = "other"


class CommandStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    expired = "expired"
    cancelled = "cancelled"


class BackupUploadStatus(str, enum.Enum):
    pending = "pending"
    uploaded = "uploaded"
    failed = "failed"


class EventSeverity(str, enum.Enum):
    informational = "informational"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class EventOutcome(str, enum.Enum):
    success = "success"
    failure = "failure"
    denied = "denied"
    error = "error"


class EventCategory(str, enum.Enum):
    authentication = "authentication"
    authorization = "authorization"
    data_access = "data_access"
    admin = "admin"
    system = "system"
    compliance = "compliance"

