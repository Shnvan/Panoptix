from __future__ import annotations

import http.client
import ipaddress
import re
import socket
import subprocess
import sys
from urllib.parse import urlparse
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from panoptix_edge_agent.config import AgentConfig, ConfigError

DiscoveryStatus = str
CandidateKind = str
Confidence = str
DeviceHint = str

_RFC1918_NETWORKS: tuple[ipaddress.IPv4Network, ...] = (
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
)
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_MAC_RE = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")
_LOCAL_NAME_RE = re.compile(r"([A-Za-z0-9][A-Za-z0-9-]{0,62}(?:\.local))")
_CAMERA_VENDOR_KEYWORDS = ("hikvision", "dahua", "axis", "hanwha", "uniview", "amcrest")
_ROUTER_VENDOR_KEYWORDS = ("tp-link", "ubiquiti", "mikrotik", "netgear", "asus", "cisco")
_CLIENT_VENDOR_KEYWORDS = ("apple", "samsung", "google", "intel")
_CLIENT_NAME_KEYWORDS = ("iphone", "ipad", "android", "macbook", "laptop")
_OUI_VENDOR_PREFIXES: dict[str, str] = {
    "00:1A:07": "Arecont Vision",
    "00:40:8C": "Axis",
    "00:60:6E": "D-Link",
    "00:90:8F": "Axis",
    "08:54:11": "Hikvision",
    "18:68:CB": "Dahua",
    "24:28:FD": "Hikvision",
    "3C:EF:8C": "Hikvision",
    "44:19:B6": "Hikvision",
    "48:EA:63": "Zhejiang Uniview",
    "70:4F:57": "TP-Link",
    "A4:14:37": "Hikvision",
    "AC:CC:8E": "Axis",
    "BC:AD:28": "Dahua",
    "C0:56:E3": "Hangzhou Hikvision",
    "D4:E8:53": "Dahua",
    "F0:18:98": "Apple",
}


class TcpConnector(Protocol):
    def connect(self, ip: str, port: int, timeout_seconds: float) -> bool:
        raise NotImplementedError


class MacResolver(Protocol):
    def resolve(self, networks: tuple[ipaddress.IPv4Network, ...]) -> dict[str, "DiscoverySignal"]:
        raise NotImplementedError


class NetworkDiscoverer(Protocol):
    def discover(
        self,
        networks: tuple[ipaddress.IPv4Network, ...],
        timeout_seconds: float,
    ) -> dict[str, "DiscoverySignal"]:
        raise NotImplementedError


class HttpFingerprinter(Protocol):
    def fingerprint(
        self,
        ip: str,
        open_ports: tuple[int, ...],
        timeout_seconds: float,
    ) -> "DiscoverySignal":
        raise NotImplementedError


class SocketTcpConnector:
    def connect(self, ip: str, port: int, timeout_seconds: float) -> bool:
        try:
            with socket.create_connection((ip, port), timeout=timeout_seconds):
                return True
        except OSError:
            return False


@dataclass(frozen=True)
class DiscoverySignal:
    mac_address: str | None = None
    mac_vendor: str | None = None
    hostnames: tuple[str, ...] = ()
    observed_protocols: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    def merge(self, other: "DiscoverySignal") -> "DiscoverySignal":
        return DiscoverySignal(
            mac_address=self.mac_address or other.mac_address,
            mac_vendor=self.mac_vendor or other.mac_vendor,
            hostnames=_dedupe((*self.hostnames, *other.hostnames)),
            observed_protocols=_dedupe((*self.observed_protocols, *other.observed_protocols)),
            evidence=_dedupe((*self.evidence, *other.evidence)),
        )


@dataclass(frozen=True)
class DiscoveryFinding:
    ip: str
    open_ports: tuple[int, ...]
    candidate_kind: CandidateKind
    confidence: Confidence
    device_hint: DeviceHint
    hostname: str | None = None
    hostnames: tuple[str, ...] = ()
    mac_address: str | None = None
    mac_vendor: str | None = None
    observed_protocols: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ip": self.ip,
            "hostname": self.hostname,
            "hostnames": list(self.hostnames),
            "mac_address": self.mac_address,
            "mac_vendor": self.mac_vendor,
            "open_ports": list(self.open_ports),
            "status": "open",
            "candidate_kind": self.candidate_kind,
            "device_hint": self.device_hint,
            "confidence": self.confidence,
            "observed_protocols": list(self.observed_protocols),
            "evidence": list(self.evidence),
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
    mac_resolver: MacResolver | None = None,
    network_discoverers: tuple[NetworkDiscoverer, ...] | None = None,
    http_fingerprinter: HttpFingerprinter | None = None,
    now: Callable[[], datetime] | None = None,
) -> DiscoveryReport:
    clock = _utcnow if now is None else now
    started_at = clock()
    networks = validate_discovery_ranges(
        config.discovery_approved_ranges,
        max_hosts=config.discovery_max_hosts,
    )
    tcp = SocketTcpConnector() if connector is None else connector
    open_ports_by_ip: dict[str, list[int]] = {}
    signals_by_ip: dict[str, DiscoverySignal] = {}
    scanned_host_count = 0
    status = "completed"
    error: str | None = None

    discoverers = (
        (MulticastMdnsDiscoverer(), SsdpDiscoverer()) if network_discoverers is None else network_discoverers
    )
    for discoverer in discoverers:
        try:
            _merge_signal_map(
                signals_by_ip,
                _filter_signal_map(discoverer.discover(networks, config.discovery_timeout_seconds), networks),
            )
        except Exception:
            status = "partial"
            error = "network-discovery-error"

    for network in networks:
        for host in network.hosts():
            ip = str(host)
            scanned_host_count += 1
            open_ports: list[int] = []
            for port in config.discovery_ports:
                try:
                    if tcp.connect(ip, port, config.discovery_timeout_seconds):
                        open_ports.append(port)
                except Exception:
                    status = "partial"
                    error = "tcp-probe-error"
            if open_ports:
                open_ports_by_ip[ip] = open_ports

    resolver = SystemMacResolver() if mac_resolver is None else mac_resolver
    try:
        _merge_signal_map(signals_by_ip, _filter_signal_map(resolver.resolve(networks), networks))
    except Exception:
        status = "partial"
        error = "mac-discovery-error"

    fingerprinter = SafeHttpFingerprinter() if http_fingerprinter is None else http_fingerprinter
    for ip, open_ports in open_ports_by_ip.items():
        try:
            _merge_signal(
                signals_by_ip,
                ip,
                fingerprinter.fingerprint(ip, tuple(open_ports), config.discovery_timeout_seconds),
            )
        except Exception:
            status = "partial"
            error = "http-fingerprint-error"

    findings: list[DiscoveryFinding] = []
    for ip in sorted(set(open_ports_by_ip) | set(signals_by_ip), key=ipaddress.ip_address):
        ports_tuple = tuple(open_ports_by_ip.get(ip, ()))
        signal = signals_by_ip.get(ip, DiscoverySignal())
        kind, confidence, device_hint = classify_device(ports_tuple, signal)
        hostnames = tuple(hostname for hostname in signal.hostnames if hostname)
        findings.append(
            DiscoveryFinding(
                ip=ip,
                open_ports=ports_tuple,
                candidate_kind=kind,
                confidence=confidence,
                device_hint=device_hint,
                hostname=hostnames[0] if hostnames else None,
                hostnames=hostnames,
                mac_address=signal.mac_address,
                mac_vendor=signal.mac_vendor,
                observed_protocols=_protocols_for_ports(ports_tuple, signal),
                evidence=_evidence_for_ports(ports_tuple, signal),
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
    kind, confidence, _device_hint = classify_device(open_ports, DiscoverySignal())
    return kind, confidence


def classify_device(
    open_ports: tuple[int, ...],
    signal: DiscoverySignal | None = None,
) -> tuple[CandidateKind, Confidence, DeviceHint]:
    ports = set(open_ports)
    metadata = signal or DiscoverySignal()
    evidence = set(metadata.evidence)
    vendor = (metadata.mac_vendor or "").lower()
    names = " ".join(metadata.hostnames).lower()

    if (
        554 in ports
        or "onvif_service" in evidence
        or "http_title_camera" in evidence
        or _contains_any(vendor, _CAMERA_VENDOR_KEYWORDS)
    ):
        return "possible_camera", "high" if 554 in ports else "medium", "ip_camera"
    if 8899 in ports:
        return "possible_camera", "medium", "ip_camera"
    if (
        8000 in ports
        or 8080 in ports
        or "nvr_service" in evidence
        or "dvr_service" in evidence
        or "http_title_nvr" in evidence
    ):
        return "possible_nvr", "medium", "nvr"
    if "printer_service" in evidence or "http_title_printer" in evidence or 631 in ports or 9100 in ports:
        return "unknown_device", "medium", "printer"
    if (
        "internet_gateway_service" in evidence
        or "http_title_router" in evidence
        or _contains_any(vendor, _ROUTER_VENDOR_KEYWORDS)
    ):
        return "unknown_device", "medium", "router"
    if 161 in ports or "switch_service" in evidence:
        return "unknown_device", "medium", "switch_possible"
    if _contains_any(vendor, _CLIENT_VENDOR_KEYWORDS) or _contains_any(names, _CLIENT_NAME_KEYWORDS):
        return "unknown_device", "low", "client_device_possible"
    return "unknown_device", "low", "unknown_network_device"


class SystemMacResolver:
    def resolve(self, networks: tuple[ipaddress.IPv4Network, ...]) -> dict[str, DiscoverySignal]:
        output = ""
        if sys.platform != "win32":
            output = _run_command(("ip", "neigh", "show"))
        if not output:
            output = _run_command(("arp", "-a"))
        return _parse_neighbor_output(output, networks)


class MulticastMdnsDiscoverer:
    def discover(
        self,
        networks: tuple[ipaddress.IPv4Network, ...],
        timeout_seconds: float,
    ) -> dict[str, DiscoverySignal]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.settimeout(min(max(timeout_seconds, 0.1), 2.0))
        signals: dict[str, DiscoverySignal] = {}
        try:
            sock.sendto(_build_mdns_services_query(), ("224.0.0.251", 5353))
            deadline = datetime.now(timezone.utc).timestamp() + min(max(timeout_seconds, 0.1), 2.0)
            while datetime.now(timezone.utc).timestamp() < deadline:
                try:
                    data, addr = sock.recvfrom(4096)
                except TimeoutError:
                    break
                except OSError:
                    break
                ip = addr[0]
                if not _ip_in_networks(ip, networks):
                    continue
                signal = _mdns_signal_from_payload(data)
                if signal is not None:
                    _merge_signal(signals, ip, signal)
        except OSError:
            return {}
        finally:
            sock.close()
        return signals


class SsdpDiscoverer:
    def discover(
        self,
        networks: tuple[ipaddress.IPv4Network, ...],
        timeout_seconds: float,
    ) -> dict[str, DiscoverySignal]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.settimeout(min(max(timeout_seconds, 0.1), 2.0))
        message = (
            "M-SEARCH * HTTP/1.1\r\n"
            "HOST: 239.255.255.250:1900\r\n"
            'MAN: "ssdp:discover"\r\n'
            "MX: 1\r\n"
            "ST: ssdp:all\r\n\r\n"
        ).encode("ascii")
        signals: dict[str, DiscoverySignal] = {}
        try:
            sock.sendto(message, ("239.255.255.250", 1900))
            deadline = datetime.now(timezone.utc).timestamp() + min(max(timeout_seconds, 0.1), 2.0)
            while datetime.now(timezone.utc).timestamp() < deadline:
                try:
                    data, addr = sock.recvfrom(4096)
                except TimeoutError:
                    break
                except OSError:
                    break
                signal_ip = _approved_ssdp_ip(data, addr[0], networks)
                if signal_ip is None:
                    continue
                _merge_signal(signals, signal_ip, _ssdp_signal_from_payload(data))
        except OSError:
            return {}
        finally:
            sock.close()
        return signals


class SafeHttpFingerprinter:
    def fingerprint(
        self,
        ip: str,
        open_ports: tuple[int, ...],
        timeout_seconds: float,
    ) -> DiscoverySignal:
        signal = DiscoverySignal()
        if 80 in open_ports:
            signal = signal.merge(_http_probe(ip, 80, False, timeout_seconds))
        if 443 in open_ports:
            signal = signal.merge(_http_probe(ip, 443, True, timeout_seconds))
        return signal


def _protocols_for_ports(open_ports: tuple[int, ...], signal: DiscoverySignal) -> tuple[str, ...]:
    protocols: list[str] = list(signal.observed_protocols)
    for port, protocol in (
        (554, "RTSP"),
        (80, "HTTP"),
        (443, "HTTPS"),
        (8000, "NVR_HTTP"),
        (8080, "HTTP_ALT"),
        (8899, "CAMERA_VENDOR_PORT"),
        (161, "SNMP"),
        (631, "IPP"),
        (9100, "JETDIRECT"),
    ):
        if port in open_ports:
            protocols.append(protocol)
    return _dedupe(protocols)


def _evidence_for_ports(open_ports: tuple[int, ...], signal: DiscoverySignal) -> tuple[str, ...]:
    evidence: list[str] = list(signal.evidence)
    for port in open_ports:
        evidence.append(f"tcp_port_{port}")
    if 554 in open_ports:
        evidence.append("rtsp_port_554")
    if 8000 in open_ports or 8080 in open_ports:
        evidence.append("nvr_web_port")
    if 8899 in open_ports:
        evidence.append("camera_vendor_port_8899")
    return _dedupe(evidence)


def _merge_signal_map(target: dict[str, DiscoverySignal], source: dict[str, DiscoverySignal]) -> None:
    for ip, signal in source.items():
        _merge_signal(target, ip, signal)


def _merge_signal(target: dict[str, DiscoverySignal], ip: str, signal: DiscoverySignal) -> None:
    target[ip] = target.get(ip, DiscoverySignal()).merge(signal)


def _filter_signal_map(
    signals: dict[str, DiscoverySignal],
    networks: tuple[ipaddress.IPv4Network, ...],
) -> dict[str, DiscoverySignal]:
    return {ip: signal for ip, signal in signals.items() if _ip_in_networks(ip, networks)}


def _ip_in_networks(ip: str, networks: tuple[ipaddress.IPv4Network, ...]) -> bool:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return isinstance(address, ipaddress.IPv4Address) and any(address in network for network in networks)


def _run_command(command: tuple[str, ...]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=2, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout if result.returncode == 0 else ""


def _parse_neighbor_output(
    output: str,
    networks: tuple[ipaddress.IPv4Network, ...],
) -> dict[str, DiscoverySignal]:
    signals: dict[str, DiscoverySignal] = {}
    for line in output.splitlines():
        ip_match = _IP_RE.search(line)
        mac_match = _MAC_RE.search(line)
        if ip_match is None or mac_match is None:
            continue
        ip = ip_match.group(0)
        if not _ip_in_networks(ip, networks):
            continue
        mac = _normalize_mac(mac_match.group(0))
        if mac is None:
            continue
        signals[ip] = DiscoverySignal(
            mac_address=mac,
            mac_vendor=vendor_for_mac(mac),
            observed_protocols=("ARP",),
            evidence=("arp_neighbor",),
        )
    return signals


def vendor_for_mac(mac_address: str) -> str | None:
    normalized = _normalize_mac(mac_address)
    if normalized is None:
        return None
    return _OUI_VENDOR_PREFIXES.get(normalized[:8])


def _normalize_mac(value: str) -> str | None:
    hex_chars = re.sub(r"[^0-9A-Fa-f]", "", value)
    if len(hex_chars) != 12 or hex_chars == "000000000000":
        return None
    octets = [hex_chars[index : index + 2].upper() for index in range(0, 12, 2)]
    return ":".join(octets)


def _build_mdns_services_query() -> bytes:
    labels = [b"_services", b"_dns-sd", b"_udp", b"local"]
    query = b"\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00"
    for label in labels:
        query += bytes([len(label)]) + label
    return query + b"\x00\x00\x0c\x00\x01"


def _mdns_signal_from_payload(data: bytes) -> DiscoverySignal | None:
    text = _safe_ascii(data).lower()
    hostnames = tuple(sorted(set(_LOCAL_NAME_RE.findall(_safe_ascii(data)))))
    evidence: list[str] = ["mdns_advertised"]
    if "_ipp._tcp" in text or "_printer" in text:
        evidence.append("printer_service")
    if "_onvif" in text or "_axis-video" in text:
        evidence.append("onvif_service")
    if "_workstation" in text or "_airplay" in text or "_raop" in text:
        evidence.append("client_service")
    if not hostnames and evidence == ["mdns_advertised"]:
        return DiscoverySignal(observed_protocols=("mDNS",), evidence=tuple(evidence))
    return DiscoverySignal(
        hostnames=hostnames[:8],
        observed_protocols=("mDNS",),
        evidence=tuple(evidence),
    )


def _approved_ssdp_ip(
    data: bytes,
    fallback_ip: str,
    networks: tuple[ipaddress.IPv4Network, ...],
) -> str | None:
    headers = _parse_http_headers(data)
    location = headers.get("location")
    if location:
        parsed = urlparse(location)
        host = parsed.hostname
        if host and _ip_in_networks(host, networks):
            return host
    return fallback_ip if _ip_in_networks(fallback_ip, networks) else None


def _ssdp_signal_from_payload(data: bytes) -> DiscoverySignal:
    headers = _parse_http_headers(data)
    combined = " ".join(
        value.lower() for key, value in headers.items() if key in {"server", "st", "usn"}
    )
    evidence = ["ssdp_advertised"]
    if "internetgatewaydevice" in combined or "wanipconnection" in combined:
        evidence.append("internet_gateway_service")
    if "onvif" in combined or "camera" in combined:
        evidence.append("onvif_service")
    if "printer" in combined:
        evidence.append("printer_service")
    if "mediareceiver" in combined or "mediaserver" in combined:
        evidence.append("client_service")
    return DiscoverySignal(observed_protocols=("SSDP",), evidence=tuple(evidence))


def _parse_http_headers(data: bytes) -> dict[str, str]:
    text = _safe_ascii(data[:4096])
    headers: dict[str, str] = {}
    for line in text.splitlines()[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()[:256]
    return headers


def _http_probe(ip: str, port: int, tls: bool, timeout_seconds: float) -> DiscoverySignal:
    connection_class = http.client.HTTPSConnection if tls else http.client.HTTPConnection
    protocol = "HTTPS" if tls else "HTTP"
    evidence = [f"{protocol.lower()}_service"]
    try:
        conn = connection_class(ip, port=port, timeout=min(max(timeout_seconds, 0.1), 2.0))
        try:
            conn.request("GET", "/", headers={"User-Agent": "Panoptix-Edge-Agent discovery"})
            response = conn.getresponse()
            body = response.read(4096)
        finally:
            conn.close()
    except OSError:
        return DiscoverySignal(observed_protocols=(protocol,), evidence=tuple(evidence))

    title = _extract_title_hint(body)
    if title is not None:
        evidence.append(title)
    return DiscoverySignal(observed_protocols=(protocol,), evidence=tuple(evidence))


def _extract_title_hint(body: bytes) -> str | None:
    text = _safe_ascii(body[:4096]).lower()
    title_match = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
    haystack = title_match.group(1) if title_match else text
    haystack = re.sub(r"\s+", " ", haystack)
    if _contains_any(haystack, ("camera", "ipcam", "webcam", "hikvision", "dahua", "axis")):
        return "http_title_camera"
    if _contains_any(haystack, ("nvr", "dvr", "recorder")):
        return "http_title_nvr"
    if _contains_any(haystack, ("router", "gateway", "tplink", "tp-link", "ubiquiti", "mikrotik")):
        return "http_title_router"
    if _contains_any(haystack, ("printer", "ipp", "jetdirect")):
        return "http_title_printer"
    return "http_title_present" if title_match else None


def _safe_ascii(data: bytes) -> str:
    return data.decode("utf-8", errors="ignore")


def _dedupe(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return tuple(result)


def _contains_any(value: str, needles: tuple[str, ...]) -> bool:
    return any(needle in value for needle in needles)


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
