"""Guard transaction transfers with account scope and currency checks.

Revision ID: 20260518_0005
Revises: 20260518_0004
Create Date: 2026-05-18

Rollback notes:
- Downgrade removes only the transfer safety trigger and function.
- Existing transactions and prerequisite account rows are preserved.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260518_0005"
down_revision: str | None = "20260518_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


FUNCTION_NAME = "finance_validate_transaction_transfer_safety"
TRIGGER_NAME = "trg_transactions_transfer_safety"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {FUNCTION_NAME}()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            source_account accounts%ROWTYPE;
            counterparty_account accounts%ROWTYPE;
        BEGIN
            IF NEW.transaction_type <> 'transfer' THEN
                RETURN NEW;
            END IF;

            SELECT * INTO source_account
            FROM accounts
            WHERE id = NEW.account_id;

            SELECT * INTO counterparty_account
            FROM accounts
            WHERE id = NEW.counterparty_account_id;

            IF source_account.id IS NULL OR counterparty_account.id IS NULL THEN
                RAISE EXCEPTION 'transfer safety check failed'
                    USING ERRCODE = '23514',
                    CONSTRAINT = 'transactions_transfer_same_scope_guard';
            END IF;

            IF source_account.currency <> NEW.currency
                OR counterparty_account.currency <> NEW.currency THEN
                RAISE EXCEPTION 'transfer safety check failed'
                    USING ERRCODE = '23514',
                    CONSTRAINT = 'transactions_transfer_same_currency_guard';
            END IF;

            IF NEW.transfer_scope = 'personal_same_owner' THEN
                IF source_account.ownership_type = 'personal'
                    AND counterparty_account.ownership_type = 'personal'
                    AND source_account.owner_user_id = counterparty_account.owner_user_id
                    AND source_account.owner_user_id IS NOT NULL THEN
                    RETURN NEW;
                END IF;
            ELSIF NEW.transfer_scope = 'household_same_household' THEN
                IF source_account.ownership_type = 'shared'
                    AND counterparty_account.ownership_type = 'shared'
                    AND source_account.household_id = counterparty_account.household_id
                    AND source_account.household_id IS NOT NULL THEN
                    RETURN NEW;
                END IF;
            END IF;

            RAISE EXCEPTION 'transfer safety check failed'
                USING ERRCODE = '23514',
                CONSTRAINT = 'transactions_transfer_same_scope_guard';
        END;
        $$;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {TRIGGER_NAME}
        BEFORE INSERT OR UPDATE OF
            account_id,
            counterparty_account_id,
            transaction_type,
            currency,
            transfer_scope
        ON transactions
        FOR EACH ROW
        EXECUTE FUNCTION {FUNCTION_NAME}();
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {TRIGGER_NAME} ON transactions;")
    op.execute(f"DROP FUNCTION IF EXISTS {FUNCTION_NAME}();")
