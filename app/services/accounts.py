from uuid import UUID

from sqlalchemy.orm import Session

from app.errors import LedgerError
from app.models import Account


def require_account(session: Session, account_id: UUID) -> Account:
    account = session.get(Account, account_id)
    if account is None:
        raise LedgerError(
            "account_not_found", "Account not found", 404, {"account_id": str(account_id)}
        )
    return account


def create_account(session: Session, name: str, *, account_id: UUID | None = None) -> Account:
    with session.begin():
        account = Account(name=name)
        if account_id is not None:
            account.id = account_id
        session.add(account)
        session.flush()
    return account
