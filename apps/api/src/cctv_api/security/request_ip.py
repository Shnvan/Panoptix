from __future__ import annotations

import ipaddress

from fastapi import Request

from cctv_api.core.config import Settings

_CF_CONNECTING_IP_HEADER = "cf-connecting-ip"


def browser_request_ip(request: Request, settings: Settings) -> str | None:
    if settings.TRUST_CF_CONNECTING_IP:
        trusted_ip = _trusted_cf_connecting_ip(request)
        if trusted_ip is not None:
            return trusted_ip
    return request.client.host if request.client is not None else None


def _trusted_cf_connecting_ip(request: Request) -> str | None:
    values = request.headers.getlist(_CF_CONNECTING_IP_HEADER)
    if len(values) != 1:
        return None

    value = values[0].strip()
    if not value or "," in value:
        return None

    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None
