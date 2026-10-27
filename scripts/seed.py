"""Load deterministic demo data. Safe to rerun; never resets existing balances."""

import sys
from decimal import Decimal
from pathlib import Path
from uuid import UUID

# Also supports direct execution from a checkout before installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.errors import LedgerError  # noqa: E402
from app.models import Account, Transaction  # noqa: E402
from app.schemas.transaction import TransactionCreate  # noqa: E402
from app.services.transactions import apply_entry, lock_accounts  # noqa: E402

SEED_ACCOUNTS = (
    (UUID("00000000-0000-4000-8000-000000000001"), "Alice Demo"),
    (UUID("00000000-0000-4000-8000-000000000002"), "Bob Demo"),
    (UUID("00000000-0000-4000-8000-000000000003"), "Charlie Empty"),
)


def seed():
    # One atomic seed operation; conflicts roll back the entire run.
    with SessionLocal() as session, session.begin():
        # Serialize seed runs without locking unrelated API operations.
        from sqlalchemy import text

        session.execute(text("SELECT pg_advisory_xact_lock(8675309)"))
        for account_id, name in SEED_ACCOUNTS:
            account = session.get(Account, account_id)
            if account is None:
                session.add(Account(id=account_id, name=name))
            elif account.name != name:
                raise RuntimeError(f"Seed account conflict: {account_id}")
        session.flush()
        accounts = lock_accounts(session, [a[0] for a in SEED_ACCOUNTS])
        for index in range(51):
            account_id = SEED_ACCOUNTS[0 if index < 50 else 1][0]
            kind = "credit" if index == 0 or index % 2 == 0 else "debit"
            amount = Decimal("1000.00") if index in (0, 50) else Decimal("10.00")
            data = TransactionCreate(
                type=kind,
                amount=amount,
                description=f"Demo transaction {index + 1}",
                reference_id=f"seed-v1-{index + 1:03d}",
            )
            existing = session.scalar(
                select(Transaction).where(
                    Transaction.account_id == account_id,
                    Transaction.reference_id == data.reference_id,
                )
            )
            if existing:
                if any(getattr(existing, key) != value for key, value in data.model_dump().items()):
                    raise RuntimeError(f"Seed transaction conflict: {data.reference_id}")
            else:
                apply_entry(session, accounts[account_id], data)
    print("Seed complete: 3 demo accounts, 51 demo transactions (existing records preserved).")
    for account_id, name in SEED_ACCOUNTS:
        print(f"  {name}: {account_id}")


if __name__ == "__main__":
    try:
        seed()
    except (RuntimeError, LedgerError) as exc:
        raise SystemExit(f"Seed failed: {exc}") from exc
