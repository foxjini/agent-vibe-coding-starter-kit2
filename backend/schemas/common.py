from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    """api-rules.md 규격의 실패 응답: {"error": {"code": "...", "message": "..."}}"""
    error: ErrorDetail


class DataResponse(BaseModel, Generic[T]):
    """api-rules.md 규격의 성공 응답: {"data": ...}"""
    data: T
