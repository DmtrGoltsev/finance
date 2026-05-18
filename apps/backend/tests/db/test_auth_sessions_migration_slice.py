from __future__ import annotations

import ast
import importlib.util
import py_compile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
REVISION_PATH = REPO_ROOT / "db" / "migrations" / "versions" / "20260518_0002_auth_sessions.py"


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        if isinstance(node.func, ast.Name):
            return node.func.id
    return None


def _literal_arg(node: ast.Call, index: int) -> str | None:
    if len(node.args) <= index:
        return None
    value = node.args[index]
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return None


class AuthSessionsMigrationSliceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = REVISION_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.calls = [node for node in ast.walk(cls.tree) if isinstance(node, ast.Call)]

    def test_revision_compiles(self) -> None:
        py_compile.compile(str(REVISION_PATH), doraise=True)

    def test_revision_imports_when_alembic_is_available(self) -> None:
        if (
            importlib.util.find_spec("alembic") is None
            or importlib.util.find_spec("sqlalchemy") is None
        ):
            self.skipTest("Alembic/SQLAlchemy are unavailable")

        spec = importlib.util.spec_from_file_location("auth_sessions_revision", REVISION_PATH)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertEqual("20260518_0002", module.revision)
        self.assertEqual("20260517_0001", module.down_revision)

    def test_creates_only_sessions_table(self) -> None:
        created_tables = [
            _literal_arg(call, 0)
            for call in self.calls
            if _call_name(call) == "create_table" and _literal_arg(call, 0)
        ]

        self.assertEqual(["sessions"], created_tables)
        self.assertNotIn("password_reset_tokens", created_tables)
        self.assertNotIn("audit_events", created_tables)

    def test_required_columns_constraints_and_indexes_are_present(self) -> None:
        for required in (
            "postgresql.UUID(as_uuid=True)",
            '"session_token_hash"',
            '"refresh_token_hash"',
            '"csrf_token_hash"',
            '"session_version"',
            '"expires_at"',
            "transport IN ('cookie', 'android_bearer')",
            "status IN ('active', 'revoked', 'expired')",
            "session_token_hash IS NOT NULL OR refresh_token_hash IS NOT NULL",
            "uq_sessions_session_token_hash",
            "uq_sessions_refresh_token_hash",
            "ix_sessions_user_active_expires",
            "ix_sessions_session_version",
            "status = 'active'",
        ):
            self.assertIn(required, self.source)

    def test_downgrade_drops_sessions_table(self) -> None:
        dropped_tables = [
            _literal_arg(call, 0)
            for call in self.calls
            if _call_name(call) == "drop_table" and _literal_arg(call, 0)
        ]

        self.assertEqual(["sessions"], dropped_tables)


if __name__ == "__main__":
    unittest.main()
