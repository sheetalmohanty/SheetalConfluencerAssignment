# API reference

Base URL: `http://localhost:8000`. JSON request/response bodies. There is no
 authentication in this assignment. Interactive schemas: `/docs`; OpenAPI: `/openapi.json`.

## Create account

`POST /accounts` → `201 Created`

```json
{"name": "Alice"}
```

```json
{
  "id": "d9ad2400-bd54-44db-b891-e06bb3c9be5d",
  "name": "Alice",
  "balance": "0.00",
  "created_at": "2026-10-27T08:00:00Z"
}
```

Only `name` is accepted. Whitespace-only names and client-supplied balances are rejected.

## Add transaction

`POST /accounts/{account_id}/transactions` → `201 Created`

```json
{
  "type": "credit",
  "amount": "100.00",
  "description": "Opening deposit",
  "reference_id": "deposit-001"
}
```

```json
{
  "id": "f91e2163-828f-4f31-8f77-b653e983da15",
  "account_id": "d9ad2400-bd54-44db-b891-e06bb3c9be5d",
  "type": "credit",
  "amount": "100.00",
  "description": "Opening deposit",
  "reference_id": "deposit-001",
  "transfer_id": null,
  "created_at": "2026-10-27T08:01:00Z"
}
```

`type` is `credit` or `debit`. `amount` is positive with at most two meaningful
fractional decimal places. `description` is optional. Rejected debits create no
entry. Reusing a reference on the same account returns `409` with the existing
transaction ID, even if the request matches exactly. References can be reused on
other accounts. Transaction updates and deletions are not supported.

## Read balance

`GET /accounts/{account_id}/balance` → `200 OK`

```json
{"account_id": "d9ad2400-bd54-44db-b891-e06bb3c9be5d", "balance": "100.00"}
```

## Transaction history

`GET /accounts/{account_id}/transactions?type=credit&page=1&limit=20` → `200 OK`

| Query | Default | Validation |
| --- | --- | --- |
| `type` | Both types | `credit` or `debit` |
| `page` | `1` | Integer ≥ 1 |
| `limit` | `20` | Integer from 1 through 100 |

```json
{
  "items": [
    {
      "id": "f91e2163-828f-4f31-8f77-b653e983da15",
      "account_id": "d9ad2400-bd54-44db-b891-e06bb3c9be5d",
      "type": "credit",
      "amount": "100.00",
      "description": "Opening deposit",
      "reference_id": "deposit-001",
      "transfer_id": null,
      "created_at": "2026-10-27T08:01:00Z"
    }
  ],
  "pagination": {"page": 1, "limit": 20, "total_records": 1, "total_pages": 1}
}
```

Counts reflect the type filter. Results are ordered by `created_at DESC, id DESC`.
An existing account with no matches returns an empty list and zero total pages.
An out-of-range page returns an empty list with the actual totals. A nonexistent
account returns `404` even when it would otherwise have empty history.

## Transfer

`POST /transfers` → `201 Created`

```json
{
  "source_account_id": "00000000-0000-4000-8000-000000000001",
  "destination_account_id": "00000000-0000-4000-8000-000000000002",
  "amount": "30.00",
  "reference_id": "transfer-001",
  "description": "Shared expenses"
}
```

Response includes `id`, all request fields, `created_at`, and the complete
`debit` and `credit` entries in the transaction response format above. Both entries
have `transfer_id` equal to the transfer's `id`. The source and destination must
exist and differ. The supplied reference must be unused on both accounts. The
source debit, destination credit, transfer record, and both balance updates commit
or roll back together. Transfers appear in each account's normal history.

## Errors

All application errors use this envelope:

```json
{
  "error": {
    "code": "duplicate_transaction",
    "message": "Transaction reference already exists",
    "details": {
      "transaction_id": "f91e2163-828f-4f31-8f77-b653e983da15",
      "account_id": "d9ad2400-bd54-44db-b891-e06bb3c9be5d"
    }
  }
}
```

| HTTP | Code | Meaning |
| --- | --- | --- |
| 404 | `account_not_found` | Valid UUID without a matching account |
| 409 | `duplicate_transaction` | Reference already exists on an affected account |
| 409 | `insufficient_balance` | Debit would overdraw the account |
| 409 | `balance_limit_exceeded` | Credit would exceed the supported balance |
| 422 | `validation_error` | Invalid UUID, JSON, fields, type, amount, or pagination |
| 500 | `internal_error` | Unexpected server failure |
| 503 | `database_error` | Database operation could not complete |

Validation details contain a list of `location`, `message`, and `type` objects.
Other errors may have `details: null`. Unknown paths and unsupported methods use
`http_error` with the applicable HTTP status. Logs retain server-side diagnostics;
responses do not expose SQL or connection information.
