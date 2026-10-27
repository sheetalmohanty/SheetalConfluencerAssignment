from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Numeric, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="account_name_nonblank"),
        CheckConstraint("balance >= 0", name="account_balance_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(Text)
    balance: Mapped[Decimal] = mapped_column(Numeric(20, 2), server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
