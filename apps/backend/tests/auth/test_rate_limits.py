from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import sys
import unittest

AUTH_PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "src" / "app"
if str(AUTH_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(AUTH_PACKAGE_ROOT))

from auth.rate_limits import RateLimitConfig, RateLimitKey


class RateLimitDefaultTests(unittest.TestCase):
    def test_adr_auth_rate_limit_defaults(self) -> None:
        config = RateLimitConfig.default()

        self.assertEqual(config.rule(RateLimitKey.REGISTRATION_IP_HOUR).limit, 5)
        self.assertEqual(config.rule(RateLimitKey.REGISTRATION_IP_DAY).limit, 20)
        self.assertEqual(config.rule(RateLimitKey.LOGIN_ACCOUNT_15M).limit, 5)
        self.assertEqual(config.rule(RateLimitKey.LOGIN_IP_15M).limit, 20)
        self.assertEqual(config.rule(RateLimitKey.PASSWORD_RESET_EMAIL_HOUR).limit, 3)
        self.assertEqual(config.rule(RateLimitKey.PASSWORD_RESET_IP_HOUR).limit, 10)
        self.assertEqual(config.rule(RateLimitKey.PASSWORD_RESET_CONFIRM_IP_HOUR).limit, 5)
        self.assertEqual(config.rule(RateLimitKey.INVITE_CREATE_HOUSEHOLD_DAY).limit, 10)
        self.assertEqual(config.rule(RateLimitKey.INVITE_CREATE_ACTOR_DAY).limit, 20)
        self.assertEqual(config.rule(RateLimitKey.INVITE_RESEND_INVITE_HOUR).limit, 3)
        self.assertEqual(config.rule(RateLimitKey.INVITE_RESEND_ACTOR_DAY).limit, 10)
        self.assertEqual(config.rule(RateLimitKey.INVITE_TOKEN_IP_HOUR).limit, 10)

    def test_default_windows_match_adr(self) -> None:
        config = RateLimitConfig.default()

        self.assertEqual(config.rule(RateLimitKey.LOGIN_ACCOUNT_15M).window, timedelta(minutes=15))
        self.assertEqual(config.rule(RateLimitKey.PASSWORD_RESET_EMAIL_HOUR).window, timedelta(hours=1))
        self.assertEqual(config.rule(RateLimitKey.INVITE_CREATE_HOUSEHOLD_DAY).window, timedelta(days=1))

    def test_overrides_are_configurable_without_mutating_defaults(self) -> None:
        config = RateLimitConfig.default()
        overridden = config.with_overrides({"login.account.15m": 7})

        self.assertEqual(overridden.rule(RateLimitKey.LOGIN_ACCOUNT_15M).limit, 7)
        self.assertEqual(config.rule(RateLimitKey.LOGIN_ACCOUNT_15M).limit, 5)


if __name__ == "__main__":
    unittest.main()
