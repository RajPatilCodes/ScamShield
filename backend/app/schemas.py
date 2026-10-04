from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=1024)

    @field_validator("password")
    @classmethod
    def password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 4096:
            raise ValueError("Password exceeds 4096 UTF-8 bytes")
        return value


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str
    session_id: str
    expires_in: int = 600


class EmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr = Field(max_length=255)


class ChallengeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_-]+$")


class RecoveryRequest(ChallengeRequest):
    password: str = Field(min_length=8, max_length=1024)
    password_bytes = field_validator("password")(Credentials.password_bytes.__func__)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str = Field(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_-]+$")


class AnalysisRequest(BaseModel):
    content: str = Field(min_length=1, max_length=10000)

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Content must not be blank")
        return value


class AnalysisResponse(BaseModel):
    score: int
    verdict: str
    flags: list[str] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class AnalysisHistoryItem(AnalysisResponse):
    id: int
    content: str
    created_at: datetime


class AnalysisHistoryResponse(BaseModel):
    items: list[AnalysisHistoryItem]
    page: int
    page_size: int
    total: int
