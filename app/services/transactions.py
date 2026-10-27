from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import LedgerError
from app.models import Account, Transaction
from app.schemas.transaction import (
    Pagination,
    TransactionCreate,
    TransactionHistory,
    TransactionRead,
)
from app.services.accounts import require_account

MAX_MONEY = Decimal("999999999999999999.99")


def lock_accounts(session: Session, account_ids: list[UUID]) -> dict[UUID, Account]:
    # Deterministic ordering prevents deadlocks for transfers in opposite directions.
    accounts = session.scalars(
        select(Account)
        .where(Account.id.in_(account_ids))
        .order_by(Account.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    found = {account.id: account for account in accounts}
    for account_id in account_ids:
        if account_id not in found:
            raise LedgerError(
                "account_not_found", "Account not found", 404, {"account_id": str(account_id)}
            )
    return found


def check_reference(session: Session, account_id: UUID, reference: str):
    existing = session.scalar(
        select(Transaction).where(
            Transaction.account_id == account_id, Transaction.reference_id == reference
        )
    )
    if existing:
        raise LedgerError(
            "duplicate_transaction",
            "Transaction reference already exists",
            details={"transaction_id": str(existing.id), "account_id": str(account_id)},
        )


def apply_entry(
    session: Session, account: Account, data: TransactionCreate, *, transfer_id: UUID | None = None
) -> Transaction:
    balance = account.balance + (data.amount if data.type == "credit" else -data.amount)
    if balance < 0:
        raise LedgerError("insufficient_balance", "Account has insufficient balance")
    if balance > MAX_MONEY:
        raise LedgerError("balance_limit_exceeded", "Resulting balance exceeds the supported limit")
    entry = Transaction(account_id=account.id, **data.model_dump(), transfer_id=transfer_id)
    account.balance = balance
    session.add(entry)
    session.flush()
    return entry


def create_transaction(session: Session, account_id: UUID, data: TransactionCreate) -> Transaction:
    with session.begin():
        account = lock_accounts(session, [account_id])[account_id]
        check_reference(session, account_id, data.reference_id)
        entry = apply_entry(session, account, data)
    return entry


def transaction_history(
    session: Session, account_id: UUID, transaction_type: str | None, page: int, limit: int
) -> TransactionHistory:
    # One snapshot keeps the count and page consistent during concurrent inserts.
    with session.begin():
        session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        require_account(session, account_id)
        filters = [Transaction.account_id == account_id]
        if transaction_type:
            filters.append(Transaction.type == transaction_type)
        total = session.scalar(select(func.count()).select_from(Transaction).where(*filters)) or 0
        offset = (page - 1) * limit
        entries = []
        if offset < total:
            entries = session.scalars(
                select(Transaction)
                .where(*filters)
                .order_by(Transaction.created_at.desc(), Transaction.id.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        return TransactionHistory(
            items=[TransactionRead.model_validate(e) for e in entries],
            pagination=Pagination(
                page=page,
                limit=limit,
                total_records=total,
                total_pages=(total + limit - 1) // limit,
            ),
        )
