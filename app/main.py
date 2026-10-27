from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from sqlalchemy import text

from app.errors import ERROR_RESPONSES, register_error_handlers
from app.routes import accounts, transactions, transfers
from app.routes.accounts import DB

app = FastAPI(
    title="Transaction Ledger API",
    responses=ERROR_RESPONSES,
    version="0.1.0",
    description=(
        "Single-currency ledger with immutable entries, atomic balance updates, and transfers. "
        "Monetary values are decimal strings. See README.md for assumptions."
    ),
)
register_error_handlers(app)
app.include_router(accounts.router)
app.include_router(transactions.router)
app.include_router(transfers.router)


@app.get("/health", tags=["Health"])
def health(session: DB):
    session.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def frontend():
    return FileResponse(Path(__file__).parent / "static" / "index.html")
