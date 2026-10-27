from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.routes.accounts import DB
from app.schemas.transaction import (
    TransactionCreate,
    TransactionHistory,
    TransactionRead,
    TransactionType,
)
from app.services.transactions import create_transaction, transaction_history

router = APIRouter(prefix="/accounts/{account_id}/transactions", tags=["Transactions"])


@router.post("", response_model=TransactionRead, status_code=201)
def post_transaction(account_id: UUID, data: TransactionCreate, session: DB):
    return create_transaction(session, account_id, data)


@router.get("", response_model=TransactionHistory)
def get_history(
    account_id: UUID,
    session: DB,
    type: TransactionType | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return transaction_history(session, account_id, type, page, limit)
