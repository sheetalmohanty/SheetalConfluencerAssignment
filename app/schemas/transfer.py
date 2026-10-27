from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.transaction import Money, Reference, TransactionRead


class TransferCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_account_id: UUID
    destination_account_id: UUID
    amount: Money
    reference_id: Reference
    description: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_transfer(self):
        if self.source_account_id == self.destination_account_id:
            raise ValueError("Source and destination accounts must be different")
        return self


class TransferRead(BaseModel):
    id: UUID
    source_account_id: UUID
    destination_account_id: UUID
    amount: Decimal
    reference_id: str
    description: str
    created_at: datetime
    debit: TransactionRead
    credit: TransactionRead
