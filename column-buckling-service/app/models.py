"""ORM 模型：每次核算请求与结果（含失败）各一行，供历史查询。"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CalculationRecord(Base):
    """一次压杆核算的请求与结果（成功或可读失败）。"""

    __tablename__ = "calculation_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)  # euler / buckling / batch
    success: Mapped[bool] = mapped_column(Boolean, index=True)
    control_mode: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)

    # 批量内定位；非批量请求为空。
    batch_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    batch_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 关键力学量，便于按条件直接过滤/排序。
    length: Mapped[float | None] = mapped_column(Float, nullable=True)
    effective_length_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    euler_critical_force: Mapped[float | None] = mapped_column(Float, nullable=True)
    capacity: Mapped[float | None] = mapped_column(Float, nullable=True)
    slenderness_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    imperfection: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 完整请求与结果（已清洗为可 JSON 序列化的普通值）。
    request_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    error_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
