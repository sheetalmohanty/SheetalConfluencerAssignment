"""Create ledger tables and enforce immutable transaction/transfer records."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("balance", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("length(btrim(name)) > 0", name="account_name_nonblank"),
        sa.CheckConstraint("balance >= 0", name="account_balance_nonnegative"),
    )
    op.create_table(
        "transfers",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column(
            "source_account_id",
            postgresql.UUID(),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "destination_account_id",
            postgresql.UUID(),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reference_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("source_account_id <> destination_account_id", name="transfer_distinct"),
        sa.CheckConstraint("amount > 0", name="transfer_amount_positive"),
    )
    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reference_id", sa.Text(), nullable=False),
        sa.Column(
            "transfer_id",
            postgresql.UUID(),
            sa.ForeignKey("transfers.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("account_id", "reference_id", name="uq_account_reference"),
        sa.CheckConstraint("type IN ('credit', 'debit')", name="transaction_type_valid"),
        sa.CheckConstraint("amount > 0", name="transaction_amount_positive"),
        sa.CheckConstraint(
            "length(btrim(reference_id)) > 0", name="transaction_reference_nonblank"
        ),
    )
    op.create_index(
        "ix_transactions_history",
        "transactions",
        ["account_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.execute("""
        CREATE FUNCTION reject_ledger_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Ledger records are immutable' USING ERRCODE = '23514';
        END;
        $$ LANGUAGE plpgsql;
    """)
    for table in ("transactions", "transfers"):
        op.execute(f"""CREATE TRIGGER immutable_{table}
                       BEFORE UPDATE OR DELETE ON {table}
                       FOR EACH ROW EXECUTE FUNCTION reject_ledger_mutation()""")


def downgrade():
    op.drop_table("transactions")
    op.drop_table("transfers")
    op.drop_table("accounts")
    op.execute("DROP FUNCTION reject_ledger_mutation()")
