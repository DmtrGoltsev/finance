"""Auth rate-limit defaults and override hooks.

Defaults mirror ADR-0001 engineering defaults. P1-B02 remains open, so every
rule is marked pending Product/Security approval and must be configurable by
deployment environment before release.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


class RateLimitKey(StrEnum):
    REGISTRATION_IP_HOUR = "registration.ip.hour"
    REGISTRATION_IP_DAY = "registration.ip.day"
    LOGIN_ACCOUNT_15M = "login.account.15m"
    LOGIN_IP_15M = "login.ip.15m"
    PASSWORD_RESET_EMAIL_HOUR = "password_reset.email.hour"
    PASSWORD_RESET_IP_HOUR = "password_reset.ip.hour"
    PASSWORD_RESET_CONFIRM_IP_HOUR = "password_reset_confirm.ip.hour"
    INVITE_CREATE_HOUSEHOLD_DAY = "invite_create.household.day"
    INVITE_CREATE_ACTOR_DAY = "invite_create.actor.day"
    INVITE_RESEND_INVITE_HOUR = "invite_resend.invite.hour"
    INVITE_RESEND_ACTOR_DAY = "invite_resend.actor.day"
    INVITE_TOKEN_IP_HOUR = "invite_token.ip.hour"
    EXPORT_CREATE_USER_HOUR = "export_create.user.hour"
    EXPORT_CREATE_USER_DAY = "export_create.user.day"


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    key: RateLimitKey
    limit: int
    window: timedelta
    scope: str
    description: str
    progressive_delay: bool = False
    pending_product_security_approval: bool = True

    @property
    def window_seconds(self) -> int:
        return int(self.window.total_seconds())

    def with_limit(self, limit: int) -> "RateLimitRule":
        if limit <= 0:
            raise ValueError("rate limit overrides must be positive")
        return RateLimitRule(
            key=self.key,
            limit=limit,
            window=self.window,
            scope=self.scope,
            description=self.description,
            progressive_delay=self.progressive_delay,
            pending_product_security_approval=self.pending_product_security_approval,
        )


ADR_ENGINEERING_DEFAULT_RULES: tuple[RateLimitRule, ...] = (
    RateLimitRule(
        RateLimitKey.REGISTRATION_IP_HOUR,
        5,
        timedelta(hours=1),
        "ip",
        "Registration attempts per IP per hour.",
    ),
    RateLimitRule(
        RateLimitKey.REGISTRATION_IP_DAY,
        20,
        timedelta(days=1),
        "ip",
        "Registration attempts per IP per day.",
    ),
    RateLimitRule(
        RateLimitKey.LOGIN_ACCOUNT_15M,
        5,
        timedelta(minutes=15),
        "account_or_email",
        "Login attempts per account/email per 15 minutes.",
        progressive_delay=True,
    ),
    RateLimitRule(
        RateLimitKey.LOGIN_IP_15M,
        20,
        timedelta(minutes=15),
        "ip",
        "Login attempts per IP per 15 minutes.",
        progressive_delay=True,
    ),
    RateLimitRule(
        RateLimitKey.PASSWORD_RESET_EMAIL_HOUR,
        3,
        timedelta(hours=1),
        "email",
        "Password reset requests per email per hour.",
    ),
    RateLimitRule(
        RateLimitKey.PASSWORD_RESET_IP_HOUR,
        10,
        timedelta(hours=1),
        "ip",
        "Password reset requests per IP per hour.",
    ),
    RateLimitRule(
        RateLimitKey.PASSWORD_RESET_CONFIRM_IP_HOUR,
        5,
        timedelta(hours=1),
        "ip",
        "Invalid password reset confirmation token attempts per IP per hour.",
    ),
    RateLimitRule(
        RateLimitKey.INVITE_CREATE_HOUSEHOLD_DAY,
        10,
        timedelta(days=1),
        "household",
        "Invite creates per household per day.",
    ),
    RateLimitRule(
        RateLimitKey.INVITE_CREATE_ACTOR_DAY,
        20,
        timedelta(days=1),
        "actor",
        "Invite creates per actor per day.",
    ),
    RateLimitRule(
        RateLimitKey.INVITE_RESEND_INVITE_HOUR,
        3,
        timedelta(hours=1),
        "invite",
        "Invite resends per invite per hour.",
    ),
    RateLimitRule(
        RateLimitKey.INVITE_RESEND_ACTOR_DAY,
        10,
        timedelta(days=1),
        "actor",
        "Invite resends per actor per day.",
    ),
    RateLimitRule(
        RateLimitKey.INVITE_TOKEN_IP_HOUR,
        10,
        timedelta(hours=1),
        "ip",
        "Invite accept/decline token attempts per IP per hour.",
    ),
    RateLimitRule(
        RateLimitKey.EXPORT_CREATE_USER_HOUR,
        3,
        timedelta(hours=1),
        "user",
        "Export job creates per user per hour.",
    ),
    RateLimitRule(
        RateLimitKey.EXPORT_CREATE_USER_DAY,
        10,
        timedelta(days=1),
        "user",
        "Export job creates per user per day.",
    ),
)

DEFAULT_RATE_LIMIT_RULES = MappingProxyType({rule.key: rule for rule in ADR_ENGINEERING_DEFAULT_RULES})


@dataclass(frozen=True, slots=True)
class RateLimitConfig:
    rules: Mapping[RateLimitKey, RateLimitRule]

    @classmethod
    def default(cls) -> "RateLimitConfig":
        return cls(rules=DEFAULT_RATE_LIMIT_RULES)

    def rule(self, key: RateLimitKey | str) -> RateLimitRule:
        normalized_key = RateLimitKey(key)
        return self.rules[normalized_key]

    def with_overrides(self, overrides: Mapping[RateLimitKey | str, int]) -> "RateLimitConfig":
        """Return a copy with environment/deployment-provided limit overrides."""

        updated = dict(self.rules)
        for key, limit in overrides.items():
            normalized_key = RateLimitKey(key)
            updated[normalized_key] = updated[normalized_key].with_limit(limit)
        return RateLimitConfig(rules=MappingProxyType(updated))
