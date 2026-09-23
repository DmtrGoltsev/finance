from __future__ import annotations

import ipaddress
from dataclasses import dataclass

from .schemas import RecommendationSourceInput

TRUSTED_SOURCE_HOSTS = {
    "moex.com": "official",
    "www.moex.com": "official",
    "iss.moex.com": "official",
    "cbr.ru": "official",
    "www.cbr.ru": "official",
    "minfin.gov.ru": "official",
    "www.minfin.gov.ru": "official",
    "e-disclosure.ru": "disclosure",
    "www.e-disclosure.ru": "disclosure",
    "interfax.ru": "news",
    "www.interfax.ru": "news",
    "tass.ru": "news",
    "www.tass.ru": "news",
    "rbc.ru": "news",
    "www.rbc.ru": "news",
}
TAX_SOURCE_HOSTS = {
    "nalog.gov.ru": "official",
    "www.nalog.gov.ru": "official",
}


class UntrustedRecommendationSource(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ValidatedRecommendationSource:
    source: RecommendationSourceInput
    trust_tier: str


def validate_recommendation_sources(
    sources: list[RecommendationSourceInput],
    *,
    issuer_hosts: list[str],
    allow_tax_sources: bool = False,
) -> list[ValidatedRecommendationSource]:
    allowed = dict(TRUSTED_SOURCE_HOSTS)
    if allow_tax_sources:
        allowed.update(TAX_SOURCE_HOSTS)
    for configured in issuer_hosts:
        normalized = configured.strip().casefold().rstrip(".")
        if normalized and not _is_forbidden_host(normalized):
            allowed[normalized] = "issuer"

    validated: list[ValidatedRecommendationSource] = []
    for source in sources:
        url = source.url
        hostname = (url.host or "").casefold().rstrip(".")
        if (
            url.scheme != "https"
            or url.username is not None
            or url.password is not None
            or (url.port is not None and url.port != 443)
            or _is_forbidden_host(hostname)
            or hostname not in allowed
        ):
            raise UntrustedRecommendationSource("recommendation source host is not allowed")
        validated.append(ValidatedRecommendationSource(source=source, trust_tier=allowed[hostname]))
    return validated


def _is_forbidden_host(hostname: str) -> bool:
    if not hostname or hostname == "localhost" or hostname.endswith(".localhost"):
        return True
    try:
        address = ipaddress.ip_address(hostname.strip("[]"))
    except ValueError:
        return False
    return not address.is_global
