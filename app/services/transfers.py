from sqlalchemy.orm import Session

from app.models import Transfer
from app.schemas.transaction import TransactionCreate, TransactionRead
from app.schemas.transfer import TransferCreate, TransferRead
from app.services.transactions import apply_entry, check_reference, lock_accounts


def create_transfer(session: Session, data: TransferCreate) -> TransferRead:
    with session.begin():
        accounts = lock_accounts(session, [data.source_account_id, data.destination_account_id])
        for account_id in accounts:
            check_reference(session, account_id, data.reference_id)
        transfer = Transfer(**data.model_dump())
        session.add(transfer)
        session.flush()
        common = dict(
            amount=data.amount, reference_id=data.reference_id, description=data.description
        )
        debit = apply_entry(
            session,
            accounts[data.source_account_id],
            TransactionCreate(type="debit", **common),
            transfer_id=transfer.id,
        )
        credit = apply_entry(
            session,
            accounts[data.destination_account_id],
            TransactionCreate(type="credit", **common),
            transfer_id=transfer.id,
        )
        result = TransferRead(
            id=transfer.id,
            **data.model_dump(),
            created_at=transfer.created_at,
            debit=TransactionRead.model_validate(debit),
            credit=TransactionRead.model_validate(credit),
        )
    return result
