from datetime import datetime

from pydantic import BaseModel, HttpUrl, field_validator

from app.config import Cloud


class CreateURL(BaseModel):
    original_url: HttpUrl

    @field_validator("original_url", mode="before")
    @classmethod
    def check_length(cls, value: object) -> object:
        if isinstance(value, str) and len(value) > 2048:
            raise ValueError("URL must be at most 2048 characters")
        return value


class URLRecord(BaseModel):
    id: str
    original_url: str
    created_at: datetime
    updated_at: datetime
    origin_cloud: Cloud
    writer_epoch: int
    version: int = 1
    deleted: bool = False
