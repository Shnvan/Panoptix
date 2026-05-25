from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx

from cctv_api.core.config import Settings

IpIntelligenceStatus = Literal["ok", "not_configured", "unavailable"]


@dataclass(frozen=True)
class IpLocation:
    continent: str | None = None
    country_code: str | None = None
    country: str | None = None
    region: str | None = None
    city: str | None = None
    timezone: str | None = None


@dataclass(frozen=True)
class IpNetwork:
    asn: int | None = None
    organization: str | None = None
    domain: str | None = None
    connection_type: str | None = None


@dataclass(frozen=True)
class IpCompany:
    name: str | None = None
    domain: str | None = None
    type: str | None = None


@dataclass(frozen=True)
class IpCarrier:
    name: str | None = None


@dataclass(frozen=True)
class IpSecurity:
    is_anonymous: bool | None = None
    is_vpn: bool | None = None
    is_proxy: bool | None = None
    is_tor: bool | None = None
    is_tor_exit: bool | None = None
    is_cloud_provider: bool | None = None
    is_relay: bool | None = None
    is_threat: bool | None = None
    is_attacker: bool | None = None
    is_abuser: bool | None = None


@dataclass(frozen=True)
class IpIntelligenceResult:
    ip_type: str | None = None
    location: IpLocation = IpLocation()
    network: IpNetwork = IpNetwork()
    company: IpCompany = IpCompany()
    carrier: IpCarrier = IpCarrier()
    security: IpSecurity = IpSecurity()

    @property
    def has_data(self) -> bool:
        return any(
            value is not None
            for value in (
                self.ip_type,
                *self.location.__dict__.values(),
                *self.network.__dict__.values(),
                *self.company.__dict__.values(),
                *self.carrier.__dict__.values(),
                *self.security.__dict__.values(),
            )
        )


class IpIntelligenceProvider(Protocol):
    def lookup(self, ip: str) -> IpIntelligenceResult | None: ...


@dataclass(frozen=True)
class IpIntelligenceProviderState:
    status: IpIntelligenceStatus
    provider_name: str | None = None
    provider: IpIntelligenceProvider | None = None

    @property
    def available(self) -> bool:
        return self.provider is not None and self.status == "ok"


@dataclass
class IpregistryIpIntelligenceProvider:
    api_key: str
    timeout_seconds: float = 10.0

    def lookup(self, ip: str) -> IpIntelligenceResult | None:
        response = httpx.get(
            f"https://api.ipregistry.co/{ip}",
            headers={"Authorization": f"ApiKey {self.api_key}"},
            timeout=self.timeout_seconds,
        )
        if response.status_code in {400, 404}:
            return None
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise ValueError("ipregistry-response-invalid")
        result = _ipregistry_result(payload)
        return result if result.has_data else None


def get_ip_intelligence_provider(settings: Settings) -> IpIntelligenceProviderState:
    if not settings.ACTOR_IP_ENRICHMENT_ENABLED:
        return IpIntelligenceProviderState(status="not_configured")

    api_key = settings.ACTOR_IP_IPREGISTRY_API_KEY.strip()
    if not api_key:
        return IpIntelligenceProviderState(status="not_configured")

    return IpIntelligenceProviderState(
        status="ok",
        provider_name="ipregistry",
        provider=IpregistryIpIntelligenceProvider(api_key=api_key),
    )


def ip_intelligence_payload(result: IpIntelligenceResult | None) -> dict[str, object]:
    if result is None:
        return {
            "ip_type": None,
            "location": {
                "continent": None,
                "country_code": None,
                "country": None,
                "region": None,
                "city": None,
                "timezone": None,
            },
            "network": {
                "asn": None,
                "organization": None,
                "domain": None,
                "connection_type": None,
            },
            "company": {
                "name": None,
                "domain": None,
                "type": None,
            },
            "carrier": {"name": None},
            "security": {
                "is_anonymous": None,
                "is_vpn": None,
                "is_proxy": None,
                "is_tor": None,
                "is_tor_exit": None,
                "is_cloud_provider": None,
                "is_relay": None,
                "is_threat": None,
                "is_attacker": None,
                "is_abuser": None,
            },
        }
    return {
        "ip_type": result.ip_type,
        "location": {
            "continent": result.location.continent,
            "country_code": result.location.country_code,
            "country": result.location.country,
            "region": result.location.region,
            "city": result.location.city,
            "timezone": result.location.timezone,
        },
        "network": {
            "asn": result.network.asn,
            "organization": result.network.organization,
            "domain": result.network.domain,
            "connection_type": result.network.connection_type,
        },
        "company": {
            "name": result.company.name,
            "domain": result.company.domain,
            "type": result.company.type,
        },
        "carrier": {"name": result.carrier.name},
        "security": {
            "is_anonymous": result.security.is_anonymous,
            "is_vpn": result.security.is_vpn,
            "is_proxy": result.security.is_proxy,
            "is_tor": result.security.is_tor,
            "is_tor_exit": result.security.is_tor_exit,
            "is_cloud_provider": result.security.is_cloud_provider,
            "is_relay": result.security.is_relay,
            "is_threat": result.security.is_threat,
            "is_attacker": result.security.is_attacker,
            "is_abuser": result.security.is_abuser,
        },
    }


def _ipregistry_result(payload: Mapping[str, object]) -> IpIntelligenceResult:
    location = _mapping(payload.get("location"))
    continent = _mapping(location.get("continent"))
    country = _mapping(location.get("country"))
    region = _mapping(location.get("region"))
    connection = _mapping(payload.get("connection"))
    company = _mapping(payload.get("company"))
    carrier = _mapping(payload.get("carrier"))
    security = _mapping(payload.get("security"))
    timezone = _mapping(payload.get("time_zone"))
    return IpIntelligenceResult(
        ip_type=_string(payload.get("type")),
        location=IpLocation(
            continent=_string(continent.get("name")),
            country_code=_string(country.get("code")),
            country=_string(country.get("name")),
            region=_string(region.get("name")),
            city=_string(location.get("city")),
            timezone=_string(timezone.get("id")),
        ),
        network=IpNetwork(
            asn=_integer(connection.get("asn")),
            organization=_string(connection.get("organization")),
            domain=_string(connection.get("domain")),
            connection_type=_string(connection.get("type")),
        ),
        company=IpCompany(
            name=_string(company.get("name")),
            domain=_string(company.get("domain")),
            type=_string(company.get("type")),
        ),
        carrier=IpCarrier(name=_string(carrier.get("name"))),
        security=IpSecurity(
            is_anonymous=_boolean(security.get("is_anonymous")),
            is_vpn=_boolean(security.get("is_vpn")),
            is_proxy=_boolean(security.get("is_proxy")),
            is_tor=_boolean(security.get("is_tor")),
            is_tor_exit=_boolean(security.get("is_tor_exit")),
            is_cloud_provider=_boolean(security.get("is_cloud_provider")),
            is_relay=_boolean(security.get("is_relay")),
            is_threat=_boolean(security.get("is_threat")),
            is_attacker=_boolean(security.get("is_attacker")),
            is_abuser=_boolean(security.get("is_abuser")),
        ),
    )


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _boolean(value: object) -> bool | None:
    return value if isinstance(value, bool) else None
