# Transaction Ledger

A Python 3.12 backend using FastAPI, SQLAlchemy 2, Psycopg, and PostgreSQL 17.
Dependencies are managed with uv. Includes account creation, immutable credit/debit
entries, balances, filtered and paginated history, and atomic money transfers.

## Run with Docker

Prerequisite: Docker with Compose.

```bash
docker compose up --build -d
docker compose exec api uv run --no-sync python scripts/seed.py
```

Compose waits for PostgreSQL, runs Alembic migrations in a separate one-shot service,
then starts the API. No manual database creation is needed. The seed command is
optional and safe to rerun.

- HTML frontend: http://localhost:8000
- API: http://localhost:8000
- Interactive API documentation: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json
- Database readiness: http://localhost:8000/health
- PostgreSQL: `localhost:5433`, database/user/password: `ledger`

```bash
docker compose logs api migrate
docker compose down
```

The named volume preserves data across restarts. `docker compose down -v` removes
the volume and **permanently deletes the local database**.

## Run Python locally

Prerequisites: uv and Docker. uv installs the configured Python version if needed.

```bash
cp .env.example .env
uv sync --locked
docker compose up -d --wait db
uv run alembic upgrade head
uv run python scripts/seed.py
uv run uvicorn app.main:app --reload
```

`DATABASE_URL` can be provided in `.env` or as an environment variable. Docker
Compose provides its own internal URL. Development credentials are local defaults.

## Demo data

`scripts/seed.py` creates three accounts and 51 transactions:

| Account | Fixed ID | Initial seeded balance | Entries |
| --- | --- | --- | --- |
| Alice Demo | `00000000-0000-4000-8000-000000000001` | `990.00` | 50 |
| Bob Demo | `00000000-0000-4000-8000-000000000002` | `1000.00` | 1 |
| Charlie Empty | `00000000-0000-4000-8000-000000000003` | `0.00` | 0 |

The script uses the same ledger write logic as the API, runs atomically, and uses
fixed references. It verifies existing seed records, skips matching records, and
rejects conflicting records. Additional application transactions are preserved.
It does not reset balances or load data during application startup.

```bash
curl 'http://localhost:8000/accounts/00000000-0000-4000-8000-000000000001/transactions?type=debit&page=2&limit=10'
```

## API

Full examples, response shapes, and errors are in [docs/api.md](docs/api.md).
Interactive documentation is generated from the request and response schemas.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/accounts` | Create an account at zero balance |
| GET | `/accounts/{account_id}/balance` | Read current balance |
| POST | `/accounts/{account_id}/transactions` | Post a credit or debit |
| GET | `/accounts/{account_id}/transactions` | Filter and paginate history |
| POST | `/transfers` | Atomically debit one account and credit another |
| GET | `/health` | Check database connectivity |

## Design and integrity

- `app/routes/` handles HTTP; `app/schemas/` validates input and shapes output;
  `app/services/` owns business rules and transaction boundaries; `app/models/`
  defines database tables. `app/database.py` manages sessions.
- Every account starts at zero. Transaction rows represent successful entries;
  rejected attempts are not stored and do not consume their reference.
- Money uses Python `Decimal` and PostgreSQL `NUMERIC(20, 2)`. The maximum amount
  or balance is `999999999999999999.99`. Overflow is rejected before committing.
- Every write locks affected account rows using `SELECT ... FOR UPDATE` before
  checking references and balances. Insertion and balance updates share one
  database transaction. The service commits before returning an HTTP success.
- Transfers lock accounts in UUID order to avoid opposing-transfer deadlocks.
  A transfer has two linked transaction rows, with the same reference on both
  accounts. If that reference exists on either account, the transfer is rejected.
- Database constraints enforce positive amounts, valid types, nonnegative balances,
  foreign keys, and uniqueness of `(account_id, reference_id)`.
- PostgreSQL triggers reject updates/deletes to transaction and transfer rows.
  The API exposes no account deletion or direct balance update operations.
- Balances are maintained by the service write path. Direct administrative SQL can
  bypass the balance calculation; database credentials should be restricted in a
  production deployment. No claim is made that arbitrary privileged SQL preserves
  ledger consistency.
- History uses `created_at DESC, id DESC` with a supporting index. Count and page
  queries share a repeatable-read snapshot. New writes between separate page
  requests can shift offset-based page boundaries.
- Migrations are explicit, versioned Alembic files; application startup does not
  create tables automatically.

## Tests and checks

Tests use real PostgreSQL, including row locking, uniqueness, triggers, rollback,
and concurrent requests. They do not substitute SQLite.

```bash
uv sync --locked
docker compose --profile test up -d --wait test-db
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run alembic check
```

The test database defaults to
`postgresql+psycopg://ledger:ledger@localhost:5434/ledger_test`; override with
`TEST_DATABASE_URL`. Its name must end in `_test`. Tests run migrations and
**truncate all ledger tables in this test database before each test**. The test
service uses temporary storage and is isolated from the development database.
Run tests serially; fixtures are not designed for pytest-xdist.

To create a migration after editing models:

```bash
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
```

Review generated migrations, especially custom triggers, before applying them.

## Assumptions

- One implicit currency with two decimal places; no exchange rates or currency
  conversion. Amounts with fractional precision beyond two nonzero decimal places
  are rejected. Equivalent values such as `1.000` are accepted as `1.00`.
- Responses encode money as strings to preserve precision. Requests accept decimal
  strings (recommended) or JSON numbers. Amounts must be finite and positive.
- Names and references are trimmed, nonblank, and at most 200 characters.
  Descriptions are optional, default to an empty string, and allow 2,000 characters.
  Unknown body fields are rejected. Names need not be unique.
- IDs are system-generated UUIDs, timestamps are database-generated timezone-aware
  values, and clients cannot set initial balances or creation timestamps.
- References are case-sensitive and account-scoped. Reuse always returns `409`,
  including when the payload matches. No existing transaction is modified.
- Pagination defaults to page 1 and limit 20, with limits from 1 to 100. Empty
  histories have zero total pages; pages beyond the last return an empty list.
- Insufficient balance, duplicate references, and balance overflow return `409`;
  nonexistent accounts return `404`; invalid UUIDs, bodies, and pagination return
  `422`. Unexpected/database failures have consistent sanitized errors.
- Authentication, authorization, pending payment workflows, failed-attempt auditing,
  account management, and external payment providers are outside this assignment.

If port 8000 is occupied, choose another host port:

```bash
API_PORT=8001 docker compose up --build -d
```

Then open http://localhost:8001/docs. For a locally run API, use Uvicorn's
`--port 8001` option instead.

## Minimal frontend

Open `/` on the running API to create accounts, post credits/debits, view balances
and paginated history, and transfer money. The page is `app/static/index.html`: plain
HTML, a little CSS, and browser JavaScript using same-origin `fetch`. No frontend
installation or separate server is required. Select “Use demo Alice” after seeding,
or create an account to select its generated ID. The last API response and any
validation errors are displayed on the page. With `API_PORT=8001`, open
http://localhost:8001/.
