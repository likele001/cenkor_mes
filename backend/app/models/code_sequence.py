from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CodeSequence(Base):
    """租户/业务类型维度的递增序号（支持按日重置）。"""

    __tablename__ = "code_sequences"
    __table_args__ = (
        UniqueConstraint("biz_type", "period_key", name="uq_code_sequences"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    biz_type: Mapped[str] = mapped_column(String(32), nullable=False)
    period_key: Mapped[str] = mapped_column(String(16), nullable=False, server_default="")
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
