from uuid import uuid4

import pytest
from conftest import post_entry
from sqlalchemy import func, select
from test_transactions import balance

from app.models import Transaction, Transfer


@pytest.fixture
def transfer_data(client, account):
    other = client.post("/accounts", json={"name": "Bob"}).json()["id"]
    post_entry(client, account)
    return {
        "source_account_id": account,
        "destination_account_id": other,
        "amount": "30.00",
        "reference_id": "transfer-1",
    }


def test_transfer_atomic_and_duplicate(client, transfer_data, session_factory):
    response = client.post("/transfers", json=transfer_data)
    assert response.status_code == 201
    data = response.json()
    assert data["debit"]["transfer_id"] == data["credit"]["transfer_id"] == data["id"]
    assert balance(client, transfer_data["source_account_id"]) == 70
    assert balance(client, transfer_data["destination_account_id"]) == 30
    assert client.post("/transfers", json=transfer_data).status_code == 409
    assert balance(client, transfer_data["source_account_id"]) == 70
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Transfer)) == 1


@pytest.mark.parametrize("failure", ["insufficient", "missing", "same", "destination_overflow"])
def test_failed_transfer_rolls_back(client, transfer_data, session_factory, failure):
    source = transfer_data["source_account_id"]
    destination = transfer_data["destination_account_id"]
    if failure == "insufficient":
        transfer_data["amount"] = "101"
    elif failure == "missing":
        transfer_data["destination_account_id"] = str(uuid4())
    elif failure == "same":
        transfer_data["destination_account_id"] = source
    else:
        post_entry(client, destination, amount="999999999999999999.99")
    before = balance(client, destination)
    response = client.post("/transfers", json=transfer_data)
    assert response.status_code == {"missing": 404, "same": 422}.get(failure, 409)
    assert balance(client, source) == 100
    assert balance(client, destination) == before
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Transfer)) == 0
        assert (
            session.scalar(
                select(func.count())
                .select_from(Transaction)
                .where(Transaction.reference_id == "transfer-1")
            )
            == 0
        )


def test_destination_reference_conflict(client, transfer_data):
    destination = transfer_data["destination_account_id"]
    post_entry(client, destination, reference="transfer-1")
    assert client.post("/transfers", json=transfer_data).status_code == 409
    assert balance(client, transfer_data["source_account_id"]) == 100
