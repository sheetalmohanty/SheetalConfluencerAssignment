from uuid import uuid4

import pytest


def test_account_starts_at_zero(client):
    response = client.post("/accounts", json={"name": " Alice "})
    assert response.status_code == 201
    account = response.json()
    assert account["name"] == "Alice"
    assert account["balance"] == "0.00"
    assert account["created_at"]
    assert client.get(f"/accounts/{account['id']}/balance").json() == {
        "account_id": account["id"],
        "balance": "0.00",
    }


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": "  "},
        {"name": "A", "balance": 100},
        {"name": "A", "id": str(uuid4())},
        {"name": None},
    ],
)
def test_invalid_account(client, body):
    response = client.post("/accounts", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_missing_and_invalid_accounts(client):
    assert client.get(f"/accounts/{uuid4()}/balance").status_code == 404
    assert client.get("/accounts/bad-id/balance").status_code == 422
    assert client.get(f"/accounts/{uuid4()}/transactions").status_code == 404


def test_malformed_json(client):
    response = client.post(
        "/accounts", content="{broken", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
