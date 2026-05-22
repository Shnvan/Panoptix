from __future__ import annotations

from collections.abc import Iterable

from fastapi import Request

from cctv_api.core.config import Settings
from cctv_api.security.request_ip import browser_request_ip


def _request(headers: Iterable[tuple[bytes, bytes]], *, client_ip: str = "100.64.0.2") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/me",
            "headers": list(headers),
            "client": (client_ip, 443),
        }
    )


def test_trusted_cf_connecting_ip_wins_when_enabled() -> None:
    request = _request([(b"cf-connecting-ip", b"203.0.113.42")])

    assert (
        browser_request_ip(request, Settings(TRUST_CF_CONNECTING_IP=True))
        == "203.0.113.42"
    )


def test_cf_connecting_ip_is_ignored_when_trust_is_disabled() -> None:
    request = _request([(b"cf-connecting-ip", b"203.0.113.42")])

    assert browser_request_ip(request, Settings(TRUST_CF_CONNECTING_IP=False)) == "100.64.0.2"


def test_invalid_or_multi_value_cf_connecting_ip_falls_back_to_request_client() -> None:
    comma_value = _request([(b"cf-connecting-ip", b"203.0.113.42, 203.0.113.43")])
    duplicate_values = _request(
        [
            (b"cf-connecting-ip", b"203.0.113.42"),
            (b"cf-connecting-ip", b"203.0.113.43"),
        ]
    )
    invalid_value = _request([(b"cf-connecting-ip", b"not-an-ip")])
    settings = Settings(TRUST_CF_CONNECTING_IP=True)

    assert browser_request_ip(comma_value, settings) == "100.64.0.2"
    assert browser_request_ip(duplicate_values, settings) == "100.64.0.2"
    assert browser_request_ip(invalid_value, settings) == "100.64.0.2"


def test_trusted_cf_connecting_ip_accepts_ipv6() -> None:
    request = _request([(b"cf-connecting-ip", b"2001:db8::8")])

    assert browser_request_ip(request, Settings(TRUST_CF_CONNECTING_IP=True)) == "2001:db8::8"
