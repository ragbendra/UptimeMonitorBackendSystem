from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator

from app.models.enums import MonitorMethod, MonitorStatus


MIN_CHECK_INTERVAL_SECONDS = 30


class MonitorCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    target_url: AnyHttpUrl
    check_interval_seconds: int = Field(ge=MIN_CHECK_INTERVAL_SECONDS)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Monitor name is required.")
        return cleaned


class MonitorUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    target_url: AnyHttpUrl | None = None
    check_interval_seconds: int | None = Field(default=None, ge=MIN_CHECK_INTERVAL_SECONDS)
    status: MonitorStatus | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Monitor name is required.")
        return cleaned


class MonitorResponse(BaseModel):
    id: int
    name: str
    target_url: str
    method: MonitorMethod
    check_interval_seconds: int
    consecutive_failure_threshold: int
    status: MonitorStatus
    consecutive_failures: int
    last_checked_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
