from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from panoptix_edge_agent import cli
from panoptix_edge_agent.config import AgentConfig, ConfigError
from panoptix_edge_agent.discovery import (
    DiscoveryFinding,
    DiscoveryReport,
    DiscoverySignal,
    classify_ports,
    classify_device,
    run_discovery,
    validate_discovery_ranges,
    vendor_for_mac,
)


class FakeConnector:
    def __init__(self, open_ports: dict[tuple[str, int], bool]) -> None:
        self.open_ports = open_ports
        self.calls: list[tuple[str, int, float]] = []

    def connect(self, ip: str, port: int, timeout_seconds: float) -> bool:
        self.calls.append((ip, port, timeout_seconds))
        return self.open_ports.get((ip, port), False)


class FakeMacResolver:
    def __init__(self, signals: dict[str, DiscoverySignal]) -> None:
        self.signals = signals

    def resolve(self, networks: tuple[object, ...]) -> dict[str, DiscoverySignal]:
        return self.signals


class FakeDiscoverer:
    def __init__(self, signals: dict[str, DiscoverySignal]) -> None:
        self.signals = signals

    def discover(
        self,
        networks: tuple[object, ...],
        timeout_seconds: float,
    ) -> dict[str, DiscoverySignal]:
        return self.signals


class FakeHttpFingerprinter:
    def __init__(self, signals: dict[str, DiscoverySignal]) -> None:
        self.signals = signals

    def fingerprint(
        self,
        ip: str,
        open_ports: tuple[int, ...],
        timeout_seconds: float,
    ) -> DiscoverySignal:
        return self.signals.get(ip, DiscoverySignal())


def _config() -> AgentConfig:
    return AgentConfig(
        api_base_url="http://api.example.test",
        gateway_id="11111111-1111-1111-1111-111111111111",
        agent_version="0.1.0",
        request_timeout_seconds=3.0,
        dev_identity_enabled=True,
        discovery_approved_ranges=("192.168.50.0/30",),
        discovery_ports=(554, 80, 8000),
        discovery_timeout_seconds=0.2,
        discovery_max_hosts=8,
    )


def test_validate_discovery_ranges_rejects_unsafe_ranges() -> None:
    unsafe_ranges = [
        "8.8.8.0/24",
        "127.0.0.0/24",
        "224.0.0.0/24",
        "0.0.0.0/0",
        "169.254.1.0/24",
        "198.18.0.0/24",
    ]

    for cidr in unsafe_ranges:
        with pytest.raises(ConfigError):
            validate_discovery_ranges((cidr,), max_hosts=256)

    with pytest.raises(ConfigError, match="exceeds"):
        validate_discovery_ranges(("192.168.0.0/24",), max_hosts=32)


def test_run_discovery_records_open_tcp_results_only() -> None:
    connector = FakeConnector(
        {
            ("192.168.50.1", 554): True,
            ("192.168.50.2", 8000): True,
        }
    )
    now = datetime(2026, 5, 25, 10, 0, 0, tzinfo=timezone.utc)

    report = run_discovery(
        _config(),
        connector=connector,
        mac_resolver=FakeMacResolver({}),
        network_discoverers=(),
        http_fingerprinter=FakeHttpFingerprinter({}),
        now=lambda: now,
    )

    assert report.status == "completed"
    assert report.scanned_host_count == 2
    assert report.candidate_count == 2
    assert [finding.to_payload() for finding in report.findings] == [
        {
            "ip": "192.168.50.1",
            "hostname": None,
            "hostnames": [],
            "mac_address": None,
            "mac_vendor": None,
            "open_ports": [554],
            "status": "open",
            "candidate_kind": "possible_camera",
            "device_hint": "ip_camera",
            "confidence": "high",
            "observed_protocols": ["RTSP"],
            "evidence": ["tcp_port_554", "rtsp_port_554"],
        },
        {
            "ip": "192.168.50.2",
            "hostname": None,
            "hostnames": [],
            "mac_address": None,
            "mac_vendor": None,
            "open_ports": [8000],
            "status": "open",
            "candidate_kind": "possible_nvr",
            "device_hint": "nvr",
            "confidence": "medium",
            "observed_protocols": ["NVR_HTTP"],
            "evidence": ["tcp_port_8000", "nvr_web_port"],
        },
    ]
    assert len(connector.calls) == 6
    assert connector.calls[0] == ("192.168.50.1", 554, 0.2)


def test_classify_ports() -> None:
    assert classify_ports((554, 80)) == ("possible_camera", "high")
    assert classify_ports((8899,)) == ("possible_camera", "medium")
    assert classify_ports((8000,)) == ("possible_nvr", "medium")
    assert classify_ports((443,)) == ("unknown_device", "low")


def test_run_discovery_enriches_safe_identity_signals_only_for_approved_ranges() -> None:
    connector = FakeConnector(
        {
            ("192.168.50.1", 80): True,
            ("192.168.50.2", 554): True,
        }
    )
    now = datetime(2026, 5, 25, 10, 0, 0, tzinfo=timezone.utc)

    report = run_discovery(
        _config(),
        connector=connector,
        mac_resolver=FakeMacResolver(
            {
                "192.168.50.1": DiscoverySignal(
                    mac_address="70:4F:57:AA:01:09",
                    mac_vendor="TP-Link",
                    observed_protocols=("ARP",),
                    evidence=("arp_neighbor",),
                ),
                "8.8.8.8": DiscoverySignal(
                    mac_address="AA:BB:CC:DD:EE:FF",
                    mac_vendor="Outside",
                    observed_protocols=("ARP",),
                    evidence=("arp_neighbor",),
                ),
            }
        ),
        network_discoverers=(
            FakeDiscoverer(
                {
                    "192.168.50.1": DiscoverySignal(
                        hostnames=("gateway.local",),
                        observed_protocols=("SSDP",),
                        evidence=("internet_gateway_service",),
                    ),
                    "192.168.50.2": DiscoverySignal(
                        hostnames=("cam-front-door.local",),
                        observed_protocols=("mDNS",),
                        evidence=("onvif_service",),
                    ),
                }
            ),
        ),
        http_fingerprinter=FakeHttpFingerprinter(
            {
                "192.168.50.1": DiscoverySignal(
                    observed_protocols=("HTTP",),
                    evidence=("http_service", "http_title_router"),
                )
            }
        ),
        now=lambda: now,
    )

    assert [finding.to_payload() for finding in report.findings] == [
        {
            "ip": "192.168.50.1",
            "hostname": "gateway.local",
            "hostnames": ["gateway.local"],
            "mac_address": "70:4F:57:AA:01:09",
            "mac_vendor": "TP-Link",
            "open_ports": [80],
            "status": "open",
            "candidate_kind": "unknown_device",
            "device_hint": "router",
            "confidence": "medium",
            "observed_protocols": ["SSDP", "ARP", "HTTP"],
            "evidence": [
                "internet_gateway_service",
                "arp_neighbor",
                "http_service",
                "http_title_router",
                "tcp_port_80",
            ],
        },
        {
            "ip": "192.168.50.2",
            "hostname": "cam-front-door.local",
            "hostnames": ["cam-front-door.local"],
            "mac_address": None,
            "mac_vendor": None,
            "open_ports": [554],
            "status": "open",
            "candidate_kind": "possible_camera",
            "device_hint": "ip_camera",
            "confidence": "high",
            "observed_protocols": ["mDNS", "RTSP"],
            "evidence": ["onvif_service", "tcp_port_554", "rtsp_port_554"],
        },
    ]


def test_discovery_can_report_service_only_client_device() -> None:
    now = datetime(2026, 5, 25, 10, 0, 0, tzinfo=timezone.utc)

    report = run_discovery(
        _config(),
        connector=FakeConnector({}),
        mac_resolver=FakeMacResolver(
            {
                "192.168.50.2": DiscoverySignal(
                    mac_address="F0:18:98:12:44:90",
                    mac_vendor="Apple",
                    observed_protocols=("ARP",),
                    evidence=("arp_neighbor",),
                )
            }
        ),
        network_discoverers=(),
        http_fingerprinter=FakeHttpFingerprinter({}),
        now=lambda: now,
    )

    assert [finding.to_payload() for finding in report.findings] == [
        {
            "ip": "192.168.50.2",
            "hostname": None,
            "hostnames": [],
            "mac_address": "F0:18:98:12:44:90",
            "mac_vendor": "Apple",
            "open_ports": [],
            "status": "open",
            "candidate_kind": "unknown_device",
            "device_hint": "client_device_possible",
            "confidence": "low",
            "observed_protocols": ["ARP"],
            "evidence": ["arp_neighbor"],
        }
    ]


def test_vendor_and_enriched_classification_helpers() -> None:
    assert vendor_for_mac("a4-14-37-91-22-10") == "Hikvision"
    assert classify_device((80,), DiscoverySignal(evidence=("http_title_printer",))) == (
        "unknown_device",
        "medium",
        "printer",
    )


def test_cli_discover_once_posts_sanitized_report(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config()
    posted: list[dict[str, Any]] = []
    now = datetime(2026, 5, 25, 10, 0, 0, tzinfo=timezone.utc)

    class FakeClient:
        def __init__(self, agent_config: AgentConfig) -> None:
            assert agent_config is config

        def send_discovery_run(self, payload: dict[str, Any]) -> dict[str, Any]:
            posted.append(payload)
            return {"accepted": True}

    monkeypatch.setattr(cli, "load_config_from_env", lambda: config)
    monkeypatch.setattr("panoptix_edge_agent.client.GatewayApiClient", FakeClient)
    monkeypatch.setattr(
        "panoptix_edge_agent.discovery.run_discovery",
        lambda agent_config: DiscoveryReport(
            started_at=now,
            finished_at=now,
            status="completed",
            approved_ranges=agent_config.discovery_approved_ranges,
            ports=agent_config.discovery_ports,
            scanned_host_count=2,
            candidate_count=1,
            findings=(
                DiscoveryFinding(
                    ip="192.168.50.1",
                    open_ports=(554,),
                    candidate_kind="possible_camera",
                    confidence="high",
                    device_hint="ip_camera",
                ),
            ),
            agent_version=agent_config.agent_version,
        ),
    )

    assert cli.main(["--discover-once"]) == 0
    assert len(posted) == 1
    assert posted[0]["approved_ranges"] == ["192.168.50.0/30"]
    assert posted[0]["ports"] == [554, 80, 8000]
    assert set(posted[0]) == {
        "started_at",
        "finished_at",
        "status",
        "approved_ranges",
        "ports",
        "scanned_host_count",
        "candidate_count",
        "findings",
        "agent_version",
    }
