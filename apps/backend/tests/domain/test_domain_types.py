from __future__ import annotations

import sys
import types
import unittest
from decimal import Decimal
from pathlib import Path

BACKEND_SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(BACKEND_SRC))

app_package = types.ModuleType("app")
app_package.__path__ = [str(BACKEND_SRC / "app")]  # type: ignore[attr-defined]
sys.modules.setdefault("app", app_package)

from app.domain import (  # noqa: E402
    RESERVED_POST_MVP_SOURCE_TYPES,
    Account,
    AccountType,
    Money,
    OwnershipType,
    SourceType,
    parse_money_decimal,
    validate_mvp_source_type_for_write,
)


class DomainTypesTest(unittest.TestCase):
    def test_enums_are_wire_string_compatible(self) -> None:
        self.assertEqual(AccountType.CASH, "cash")
        self.assertEqual(AccountType.CARD.value, "card")
        self.assertEqual(AccountType.METAL.value, "metal")
        self.assertEqual(OwnershipType.SHARED.value, "shared")
        self.assertEqual(SourceType.MANUAL.value, "manual")

    def test_mvp_source_type_write_helper_accepts_manual_only(self) -> None:
        self.assertIs(validate_mvp_source_type_for_write("manual"), SourceType.MANUAL)

        for source_type in RESERVED_POST_MVP_SOURCE_TYPES:
            with self.assertRaisesRegex(ValueError, "post-MVP"):
                validate_mvp_source_type_for_write(source_type)

    def test_money_rejects_float_and_keeps_decimal_wire_format(self) -> None:
        self.assertEqual(parse_money_decimal("1000.000001"), Decimal("1000.000001"))
        self.assertEqual(Money.from_wire("10.50", "RUB").amount_wire(), "10.50")

        with self.assertRaisesRegex(TypeError, "float"):
            parse_money_decimal(10.5)  # type: ignore[arg-type]

        with self.assertRaisesRegex(ValueError, "DecimalString"):
            parse_money_decimal("1.0000001")

    def test_minimal_account_dataclass_supports_authz_fixtures(self) -> None:
        account = Account(
            id="acc_1",
            name="Cash",
            account_type=AccountType.CASH,
            ownership_type=OwnershipType.PERSONAL,
            currency="RUB",
            owner_user_id="user_1",
        )

        self.assertEqual(account.owner_user_id, "user_1")
        self.assertIsNone(account.household_id)


if __name__ == "__main__":
    unittest.main()
