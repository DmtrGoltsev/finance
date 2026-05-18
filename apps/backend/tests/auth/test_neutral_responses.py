from __future__ import annotations

import unittest
from pathlib import Path
import sys

AUTH_PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "src" / "app"
if str(AUTH_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(AUTH_PACKAGE_ROOT))

from auth.schemas import NeutralFlow
from auth.service import (
    neutral_invite_request_response,
    neutral_login_failure_response,
    neutral_password_reset_request_response,
    neutral_response_for,
)


class NeutralResponseTests(unittest.TestCase):
    def test_password_reset_request_response_is_neutral(self) -> None:
        response = neutral_password_reset_request_response(request_id="req-1")

        self.assertEqual(response.flow, NeutralFlow.PASSWORD_RESET_REQUEST)
        self.assertEqual(response.status, "accepted")
        self.assertEqual(response.request_id, "req-1")
        public_text = repr(response.to_public_dict()).lower()
        self.assertNotIn("exists", public_text)
        self.assertNotIn("not found", public_text)
        self.assertNotIn("unknown", public_text)

    def test_invite_request_response_is_neutral(self) -> None:
        response = neutral_invite_request_response()

        self.assertEqual(response.flow, NeutralFlow.INVITE_REQUEST)
        self.assertEqual(response.status, "accepted")
        public_text = repr(response.to_public_dict()).lower()
        self.assertNotIn("already invited", public_text)
        self.assertNotIn("registered", public_text)

    def test_login_failure_response_is_account_neutral(self) -> None:
        response = neutral_login_failure_response()

        self.assertEqual(response.flow, NeutralFlow.LOGIN_FAILURE)
        self.assertEqual(response.status, "denied")
        public_text = repr(response.to_public_dict()).lower()
        self.assertNotIn("email", public_text)
        self.assertNotIn("account", public_text)
        self.assertNotIn("user", public_text)

    def test_neutral_response_for_accepts_string_flow(self) -> None:
        response = neutral_response_for("password_reset_request")

        self.assertEqual(response.flow, NeutralFlow.PASSWORD_RESET_REQUEST)


if __name__ == "__main__":
    unittest.main()
