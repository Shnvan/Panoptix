from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from panoptix_edge_agent.config import AgentConfig, ConfigError

DiscoveryStatus = str
CandidateKind = str
Confidence = str

_RFC1918_NETWORKS: tuple[ipaddress.IPv4Network, ...] = (
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
)


class TcpConnector(Protocol):
    def connect(self, ip: str, port: int, timeout_seconds: float) -> bool:
        raise NotImplementedError


class SocketTcpConnector:
    def connect(self, ip: str, port: int, timeout_seconds: float) -> bool:
        try:
            with socket.create_connection((ip, port), timeout=timeout_seconds):
                return True
        except OSError:
            return False


@dataclass(frozen=True)
class DiscoveryFinding:
    ip: str
    open_ports: tuple[int, ...]
    candidate_kind: CandidateKind
    confidence: Confidence
    hostname: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ip": self.ip,
            "hostname": self.hostname,
            "open_ports": list(self.open_ports),
            "status": "open",
            "candidate_kind": self.candidate_kind,
            "confidence": self.confidence,
        }
        return payload


@dataclass(frozen=True)
class DiscoveryReport:
    started_at: datetime
    finished_at: datetime
    status: DiscoveryStatus
    approved_ranges: tuple[str, ...]
    ports: tuple[int, ...]
    scanned_host_count: int
    candidate_count: int
    findings: tuple[DiscoveryFinding, ...]
    agent_version: str
    error: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "started_at": _format_datetime(self.started_at),
            "finished_at": _format_datetime(self.finished_at),
            "status": self.status,
            "approved_ranges": list(self.approved_ranges),
            "ports": list(self.ports),
            "scanned_host_count": self.scanned_host_count,
            "candidate_count": self.candidate_count,
            "findings": [finding.to_payload() for finding in self.findings],
            "agent_version": self.agent_version,
        }
        if self.error is not None:
            payload["error"] = self.error
        return payload


def run_discovery(
    config: AgentConfig,
    *,
    connector: TcpConnector | None = None,
    now: Callable[[], datetime] | None = None,
) -> DiscoveryReport:
    clock = _utcnow if now is None else now
    started_at = clock()
    networks = validate_discovery_ranges(
        config.discovery_approved_ranges,
        max_hosts=config.discovery_max_hosts,
    )
    tcp = SocketTcpConnector() if connector is None else connector
    findings: list[DiscoveryFinding] = []
    scanned_host_count = 0
    status = "completed"
    error: str | None = None

    for network in networks:
        for host in network.hosts():
            scanned_host_count += 1
            open_ports: list[int] = []
            for port in config.discovery_ports:
                try:
                    if tcp.connect(str(host), port, config.discovery_timeout_seconds):
                        open_ports.append(port)
                except Exception:
                    status = "partial"
                    error = "tcp-probe-error"
            if open_ports:
                kind, confidence = classify_ports(tuple(open_ports))
                findings.append(
                    DiscoveryFinding(
                        ip=str(host),
                        open_ports=tuple(open_ports),
                        candidate_kind=kind,
                        confidence=confidence,
                    )
                )

    finished_at = clock()
    return DiscoveryReport(
        started_at=started_at,
        finished_at=finished_at,
        status=status,
        approved_ranges=tuple(str(network) for network in networks),
        ports=config.discovery_ports,
        scanned_host_count=scanned_host_count,
        candidate_count=len(findings),
        findings=tuple(findings),
        agent_version=config.agent_version,
        error=error,
    )


def validate_discovery_ranges(raw_ranges: tuple[str, ...], *, max_hosts: int) -> tuple[ipaddress.IPv4Network, ...]:
    if not raw_ranges:
        raise ConfigError("PANOPTIX_DISCOVERY_APPROVED_RANGES is required for discovery")
    if max_hosts < 1:
        raise ConfigError("PANOPTIX_DISCOVERY_MAX_HOSTS must be at least 1")

    networks: list[ipaddress.IPv4Network] = []
    for raw in raw_ranges:
        try:
            network = ipaddress.ip_network(raw, strict=False)
        except ValueError as exc:
            raise ConfigError(f"PANOPTIX_DISCOVERY_APPROVED_RANGES contains invalid CIDR: {raw}") from exc
        if not isinstance(network, ipaddress.IPv4Network):
            raise ConfigError("PANOPTIX_DISCOVERY_APPROVED_RANGES supports IPv4 CIDRs only")
        _validate_private_network(network, max_hosts=max_hosts)
        networks.append(network)
    return tuple(networks)


def classify_ports(open_ports: tuple[int, ...]) -> tuple[CandidateKind, Confidence]:
    ports = set(open_ports)
    if 554 in ports:
        return "possible_camera", "high"
    if 8899 in ports:
        return "possible_camera", "medium"
    if 8000 in ports or 8080 in ports:
        return "possible_nvr", "medium"
    return "unknown_device", "low"


def _validate_private_network(network: ipaddress.IPv4Network, *, max_hosts: int) -> None:
    if (
        not any(network.subnet_of(allowed) for allowed in _RFC1918_NETWORKS)
        or network.is_loopback
        or network.is_multicast
        or network.is_unspecified
        or network.is_link_local
        or network.is_reserved
        or network.prefixlen == 0
    ):
        raise ConfigError("PANOPTIX_DISCOVERY_APPROVED_RANGES must contain private camera LAN/VLAN CIDRs only")
    if _host_count(network) > max_hosts:
        raise ConfigError("PANOPTIX_DISCOVERY_APPROVED_RANGES exceeds PANOPTIX_DISCOVERY_MAX_HOSTS")


def _host_count(network: ipaddress.IPv4Network) -> int:
    if network.prefixlen >= 31:
        return network.num_addresses
    return max(0, network.num_addresses - 2)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
