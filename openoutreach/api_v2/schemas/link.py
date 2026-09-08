"""Tenant-safe tracked-link API contracts."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _http_url(value: str) -> str:
    from openoutreach.emails.tracking import _validate_destination_url
    _validate_destination_url(value)
    return value


class LinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=200)
    destination_url: str = Field(min_length=1, max_length=2048)
    default_utm: dict[str, str] = Field(default_factory=dict)
    is_active: bool = True

    @field_validator("destination_url")
    @classmethod
    def safe_destination(cls, value: str) -> str:
        return _http_url(value)


class LinkUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Optional[str] = Field(None, min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    destination_url: Optional[str] = Field(None, min_length=1, max_length=2048)
    default_utm: Optional[dict[str, str]] = None
    is_active: Optional[bool] = None

    @field_validator("destination_url")
    @classmethod
    def safe_destination(cls, value: Optional[str]) -> Optional[str]:
        return _http_url(value) if value is not None else value


class LinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    campaign_id: str
    key: str
    name: str
    destination_url: str
    is_active: bool
    default_utm: dict[str, str] = Field(default_factory=dict)
    total_clicks: int = 0
    unique_clicks: int = 0
    created_at: datetime
    updated_at: datetime
    last_clicked_at: Optional[datetime] = None
