from fastapi import APIRouter

from app.routes.accounts import DB
from app.schemas.transfer import TransferCreate, TransferRead
from app.services.transfers import create_transfer

router = APIRouter(prefix="/transfers", tags=["Transfers"])


@router.post("", response_model=TransferRead, status_code=201)
def post_transfer(data: TransferCreate, session: DB):
    return create_transfer(session, data)
