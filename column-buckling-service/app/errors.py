"""跨层统一的业务异常与可读错误结构。"""

from typing import Any


class ServiceError(Exception):
    """所有可预期的输入/业务错误。

    一定带可读中文说明、稳定错误码与涉事字段，
    由全局异常处理器统一转成 JSON，绝不让进程崩溃。
    """

    def __init__(
        self,
        code: str,
        message: str,
        field: str | None = None,
        status_code: int = 422,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field
        self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.field is not None:
            body["field"] = self.field
        if self.details:
            body["details"] = self.details
        return body
