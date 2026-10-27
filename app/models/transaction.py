from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("account_id", "reference_id", name="uq_account_reference"),
        CheckConstraint("type IN ('credit', 'debit')", name="transaction_type_valid"),
        CheckConstraint("amount > 0", name="transaction_amount_positive"),
        CheckConstraint("length(btrim(reference_id)) > 0", name="transaction_reference_nonblank"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    type: Mapped[str] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    description: Mapped[str] = mapped_column(Text, default="")
    reference_id: Mapped[str] = mapped_column(Text)
    transfer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("transfers.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


Index(
    "ix_transactions_history",
    Transaction.account_id,
    Transaction.created_at.desc(),
    Transaction.id.desc(),
)
