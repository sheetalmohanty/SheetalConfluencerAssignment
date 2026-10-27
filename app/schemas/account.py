from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    balance: Decimal
    created_at: datetime


class BalanceRead(BaseModel):
    account_id: UUID
    balance: Decimal
