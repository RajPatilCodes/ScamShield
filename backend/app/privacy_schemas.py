from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .schemas import AnalysisRequest, Credentials, AnalysisHistoryItem, AnalysisHistoryResponse


class SavedHistoryItem(AnalysisHistoryItem):
    record_key: str
    expires_at: int
    provenance: str


class SavedHistoryResponse(AnalysisHistoryResponse):
    items: list[SavedHistoryItem]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TransientRequest(AnalysisRequest):
    model_config = ConfigDict(extra="forbid")


class SaveRequest(TransientRequest):
    save: Literal[True]


class ConsentRequest(Strict):
    granted: bool
    version: str = Field(max_length=40)
    expected_version: int = Field(ge=0)


class ReauthRequest(Strict):
    password: str = Field(min_length=8, max_length=1024)
    action: Literal["export_create", "export_download", "delete_account", "delete_saved"]
    target: str = Field(min_length=1, max_length=36)
    password_bytes = field_validator("password")(Credentials.password_bytes.__func__)


class ExportRequest(Strict):
    grant: str = Field(min_length=1, max_length=256)


class DeletionRequest(ExportRequest):
    scope: Literal["account", "saved"]
    receipt: str | None = Field(default=None, min_length=32, max_length=256, pattern=r"^[A-Za-z0-9_-]+$")


class ReceiptRequest(Strict):
    receipt: str = Field(min_length=32, max_length=256, pattern=r"^[A-Za-z0-9_-]+$")


class AnalysisDeleteRequest(Strict):
    record_key: str = Field(min_length=36, max_length=36)
