"""核算历史记录的持久化模型。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, JSON

from app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CalculationRecord(Base):
    """一次核算请求与结果的留痕（批量请求作为一条记录保存）。"""

    __tablename__ = "calculation_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True, nullable=False)
    endpoint = Column(String(64), index=True, nullable=False)
    status = Column(String(16), index=True, nullable=False)  # success / error / partial
    request_payload = Column(JSON, nullable=False)
    response_payload = Column(JSON, nullable=True)
    error_message = Column(String(1024), nullable=True)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "endpoint": self.endpoint,
            "status": self.status,
            "request_payload": self.request_payload,
            "response_payload": self.response_payload,
            "error_message": self.error_message,
        }
