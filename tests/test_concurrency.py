from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import UUID

from conftest import post_entry
from sqlalchemy import func, select

from app.errors import LedgerError
from app.models import Account, Transaction
from app.schemas.transaction import TransactionCreate
from app.schemas.transfer import TransferCreate
from app.services.transactions import create_transaction
from app.services.transfers import create_transfer


def run_concurrently(session_factory, operations):
    barrier = Barrier(len(operations))

    def run(operation):
        with session_factory() as session:
            barrier.wait(timeout=10)
            try:
                operation(session)
                return "success"
            except LedgerError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=len(operations)) as pool:
        return list(pool.map(run, operations))


def test_concurrent_debits_cannot_overdraw(client, account, session_factory):
    post_entry(client, account)
    operations = [
        lambda session, i=i: create_transaction(
            session,
            UUID(account),
            TransactionCreate(type="debit", amount="30", reference_id=f"concurrent-{i}"),
        )
        for i in range(8)
    ]
    results = run_concurrently(session_factory, operations)
    assert results.count("success") == 3
    assert results.count("insufficient_balance") == 5
    with session_factory() as session:
        assert session.get(Account, UUID(account)).balance == Decimal("10.00")
        assert session.scalar(select(func.count()).select_from(Transaction)) == 4


def test_concurrent_duplicate_is_applied_once(client, account, session_factory):
    operations = [
        lambda session: create_transaction(
            session,
            UUID(account),
            TransactionCreate(type="credit", amount="10", reference_id="same"),
        )
        for _ in range(8)
    ]
    results = run_concurrently(session_factory, operations)
    assert results.count("success") == 1
    assert results.count("duplicate_transaction") == 7
    with session_factory() as session:
        assert session.get(Account, UUID(account)).balance == Decimal("10.00")


def test_opposing_transfers_do_not_deadlock(client, account, session_factory):
    other = client.post("/accounts", json={"name": "Bob"}).json()["id"]
    post_entry(client, account)
    post_entry(client, other)
    operations = [
        lambda session, i=i: create_transfer(
            session,
            TransferCreate(
                source_account_id=account if i % 2 else other,
                destination_account_id=other if i % 2 else account,
                amount="10",
                reference_id=f"transfer-{i}",
            ),
        )
        for i in range(8)
    ]
    assert run_concurrently(session_factory, operations) == ["success"] * 8
    with session_factory() as session:
        assert session.get(Account, UUID(account)).balance == 100
        assert session.get(Account, UUID(other)).balance == 100
