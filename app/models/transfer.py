from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Transfer(Base):
    __tablename__ = "transfers"
    __table_args__ = (
        CheckConstraint("source_account_id <> destination_account_id", name="transfer_distinct"),
        CheckConstraint("amount > 0", name="transfer_amount_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    destination_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT")
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    description: Mapped[str] = mapped_column(Text)
    reference_id: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
