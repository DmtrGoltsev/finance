"""Harden immutable account/category ownership scopes.

Revision ID: 20260518_0003
Revises: 20260518_0002
Create Date: 2026-05-18

Rollback notes:
- Downgrade removes only guard triggers/functions.
- Existing account/category data remains unchanged.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260518_0003"
down_revision: str | None = "20260518_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_accounts_scope_update()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.ownership_type IS DISTINCT FROM NEW.ownership_type
                OR OLD.owner_user_id IS DISTINCT FROM NEW.owner_user_id
                OR OLD.household_id IS DISTINCT FROM NEW.household_id
            THEN
                RAISE EXCEPTION 'account ownership scope is immutable'
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_accounts_immutable_scope
        BEFORE UPDATE OF ownership_type, owner_user_id, household_id ON accounts
        FOR EACH ROW
        EXECUTE FUNCTION prevent_accounts_scope_update();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_categories_scope_update()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.category_scope IS DISTINCT FROM NEW.category_scope
                OR OLD.owner_user_id IS DISTINCT FROM NEW.owner_user_id
                OR OLD.household_id IS DISTINCT FROM NEW.household_id
            THEN
                RAISE EXCEPTION 'category scope is immutable'
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_categories_immutable_scope
        BEFORE UPDATE OF category_scope, owner_user_id, household_id ON categories
        FOR EACH ROW
        EXECUTE FUNCTION prevent_categories_scope_update();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_categories_immutable_scope ON categories")
    op.execute("DROP FUNCTION IF EXISTS prevent_categories_scope_update()")
    op.execute("DROP TRIGGER IF EXISTS trg_accounts_immutable_scope ON accounts")
    op.execute("DROP FUNCTION IF EXISTS prevent_accounts_scope_update()")
