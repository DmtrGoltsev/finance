from __future__ import annotations

import unittest

from app.auth import router as auth_router


class AuthRouterContractTests(unittest.TestCase):
    def test_login_placeholder_route_matches_openapi_sessions_path(self) -> None:
        self.assertEqual(auth_router.LOGIN_SESSION_ROUTE, "/sessions")
        self.assertNotEqual(auth_router.LOGIN_SESSION_ROUTE, "/sessions/login")

    def test_current_session_route_matches_openapi_path(self) -> None:
        self.assertEqual(auth_router.CURRENT_SESSION_ROUTE, "/sessions/current")


if __name__ == "__main__":
    unittest.main()
