from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


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
