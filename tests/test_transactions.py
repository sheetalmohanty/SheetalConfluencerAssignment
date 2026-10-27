from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from conftest import post_entry
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import IntegrityError

from app.models import Account, Transaction
from app.schemas.transaction import TransactionCreate
from app.services.transactions import create_transaction


def balance(client, account):
    return Decimal(client.get(f"/accounts/{account}/balance").json()["balance"])


def test_credit_debit_and_insufficient_balance(client, account):
    assert post_entry(client, account).status_code == 201
    assert post_entry(client, account, "debit", "30.00", "debit-1").status_code == 201
    assert balance(client, account) == 70
    response = post_entry(client, account, "debit", "100.00", "failed")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_balance"
    assert balance(client, account) == 70
    assert (
        client.get(f"/accounts/{account}/transactions").json()["pagination"]["total_records"] == 2
    )
    # A rejected request does not consume the reference.
    assert post_entry(client, account, "debit", "70.00", "failed").status_code == 201
    assert balance(client, account) == 0


def test_duplicate_reference_scoped_to_account(client, account):
    original = post_entry(client, account).json()
    response = post_entry(client, account, amount="200.00")
    assert response.status_code == 409
    assert response.json()["error"]["details"]["transaction_id"] == original["id"]
    assert balance(client, account) == 100
    other = client.post("/accounts", json={"name": "Bob"}).json()["id"]
    assert post_entry(client, other).status_code == 201


@pytest.mark.parametrize(
    "patch",
    [
        {"type": "invalid"},
        {"amount": "0"},
        {"amount": "-1"},
        {"amount": "0.001"},
        {"amount": "NaN"},
        {"amount": "Infinity"},
        {"amount": True},
        {"amount": "1000000000000000000.00"},
        {"reference_id": " "},
        {"reference_id": None},
        {"created_at": "2020-01-01"},
        {"description": None},
    ],
)
def test_invalid_transactions(client, account, patch):
    data = {"type": "credit", "amount": "1.00", "reference_id": "test"} | patch
    assert client.post(f"/accounts/{account}/transactions", json=data).status_code == 422
    assert balance(client, account) == 0


def test_missing_account(client):
    assert post_entry(client, str(uuid4())).status_code == 404


def test_pagination_filters_and_ordering(client, account, session_factory):
    for i in range(7):
        assert (
            post_entry(
                client, account, "credit" if i % 2 == 0 else "debit", "10.00", f"ref-{i}"
            ).status_code
            == 201
        )
    with session_factory() as session:
        expected = [
            str(i)
            for i in session.scalars(
                select(Transaction.id).order_by(
                    Transaction.created_at.desc(), Transaction.id.desc()
                )
            )
        ]
    first = client.get(f"/accounts/{account}/transactions?page=1&limit=3").json()
    second = client.get(f"/accounts/{account}/transactions?page=2&limit=3").json()
    assert first["pagination"] == {"page": 1, "limit": 3, "total_records": 7, "total_pages": 3}
    assert [t["id"] for t in first["items"] + second["items"]] == expected[:6]
    filtered = client.get(f"/accounts/{account}/transactions?type=debit&limit=2").json()
    assert filtered["pagination"]["total_records"] == 3
    assert all(t["type"] == "debit" for t in filtered["items"])
    assert client.get(f"/accounts/{account}/transactions?page=10").json()["items"] == []


@pytest.mark.parametrize("query", ["page=0", "limit=0", "limit=101", "page=no", "type=other"])
def test_invalid_pagination(client, account, query):
    assert client.get(f"/accounts/{account}/transactions?{query}").status_code == 422


def test_empty_history(client, account):
    assert client.get(f"/accounts/{account}/transactions").json() == {
        "items": [],
        "pagination": {"page": 1, "limit": 20, "total_records": 0, "total_pages": 0},
    }


def test_immutable_in_api_and_database(client, account, session_factory):
    transaction = post_entry(client, account).json()
    path = f"/accounts/{account}/transactions/{transaction['id']}"
    assert client.patch(path, json={"amount": "200"}).status_code in (404, 405)
    assert client.delete(path).status_code in (404, 405)
    for sql in ("UPDATE transactions SET amount = 200", "DELETE FROM transactions"):
        with session_factory() as session, pytest.raises(IntegrityError), session.begin():
            session.execute(text(sql))
    assert balance(client, account) == 100


def test_database_constraints(client, account, session_factory):
    post_entry(client, account)
    with session_factory() as session, pytest.raises(IntegrityError), session.begin():
        session.add(
            Transaction(
                account_id=account, type="credit", amount=1, description="", reference_id="ref-1"
            )
        )
    with session_factory() as session, pytest.raises(IntegrityError), session.begin():
        session.execute(text("UPDATE accounts SET balance = -1"))


def test_insert_failure_rolls_back_balance(client, account, session_factory):
    def fail_insert(*args):
        raise RuntimeError("Injected transaction insert failure")

    event.listen(Transaction, "before_insert", fail_insert)
    try:
        with session_factory() as session, pytest.raises(RuntimeError):
            create_transaction(
                session,
                UUID(account),
                TransactionCreate(type="credit", amount="50", reference_id="rollback"),
            )
    finally:
        event.remove(Transaction, "before_insert", fail_insert)
    assert balance(client, account) == 0
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Transaction)) == 0


def test_balance_overflow(client, account):
    assert post_entry(client, account, amount="999999999999999999.99").status_code == 201
    response = post_entry(client, account, amount="0.01", reference="overflow")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "balance_limit_exceeded"


def test_far_out_page_is_empty(client, account):
    post_entry(client, account)
    response = client.get(f"/accounts/{account}/transactions?page=1000000000000000000000")
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_lock_refreshes_a_previously_loaded_account(client, account, session_factory):
    with session_factory() as session:
        cached = session.get(Account, UUID(account))
        assert cached.balance == 0
        session.commit()
        post_entry(client, account)
        create_transaction(
            session,
            UUID(account),
            TransactionCreate(type="credit", amount="20", reference_id="refresh"),
        )
    assert balance(client, account) == 120
