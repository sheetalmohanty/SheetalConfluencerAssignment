from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Money = Annotated[Decimal, Field(gt=0, max_digits=20, decimal_places=2, allow_inf_nan=False)]
Reference = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
TransactionType = Literal["credit", "debit"]


class TransactionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: TransactionType
    amount: Money
    description: str = Field(default="", max_length=2000)
    reference_id: Reference

    @field_validator("amount", mode="before")
    @classmethod
    def reject_boolean(cls, value):
        if isinstance(value, bool):
            raise ValueError("Amount must be a decimal number")
        return value


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    account_id: UUID
    type: TransactionType
    amount: Decimal
    description: str
    reference_id: str
    transfer_id: UUID | None
    created_at: datetime


class Pagination(BaseModel):
    page: int
    limit: int
    total_records: int
    total_pages: int


class TransactionHistory(BaseModel):
    items: list[TransactionRead]
    pagination: Pagination
