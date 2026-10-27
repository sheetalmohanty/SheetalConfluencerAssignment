from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_session
from app.schemas.account import AccountCreate, AccountRead, BalanceRead
from app.services.accounts import create_account, require_account

router = APIRouter(prefix="/accounts", tags=["Accounts"])
DB = Annotated[Session, Depends(get_session)]


@router.post("", response_model=AccountRead, status_code=201)
def post_account(data: AccountCreate, session: DB):
    return create_account(session, data.name)


@router.get("/{account_id}/balance", response_model=BalanceRead)
def get_balance(account_id: UUID, session: DB):
    account = require_account(session, account_id)
    return BalanceRead(account_id=account.id, balance=account.balance)
