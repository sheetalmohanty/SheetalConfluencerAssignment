import pytest
from sqlalchemy import func, select

from app.models import Account, Transaction
from scripts import seed as seed_module


def test_seed_is_repeatable_and_balances_reconcile(session_factory, monkeypatch):
    monkeypatch.setattr(seed_module, "SessionLocal", session_factory)
    seed_module.seed()
    seed_module.seed()
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Account)) == 3
        assert session.scalar(select(func.count()).select_from(Transaction)) == 51
        for account in session.scalars(select(Account)):
            entries = session.scalars(
                select(Transaction).where(Transaction.account_id == account.id)
            )
            expected = sum(e.amount if e.type == "credit" else -e.amount for e in entries)
            assert account.balance == expected


def test_seed_conflict_rolls_back_all_changes(session_factory, monkeypatch):
    monkeypatch.setattr(seed_module, "SessionLocal", session_factory)
    with session_factory() as session, session.begin():
        session.add(Account(id=seed_module.SEED_ACCOUNTS[1][0], name="Existing account"))
    with pytest.raises(RuntimeError, match="Seed account conflict"):
        seed_module.seed()
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Account)) == 1
        assert session.scalar(select(func.count()).select_from(Transaction)) == 0
