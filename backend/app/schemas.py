from typing import Literal

from pydantic import BaseModel, Field, field_validator


class CloseAlarmRequest(BaseModel):
    solution: str = Field(default="", max_length=2000)


class BulkCloseRequest(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)
    solution: str = Field(default="批量闭环：已现场确认处理。", max_length=2000)


class ThresholdUpdate(BaseModel):
    temp_limit_c: float | None = Field(default=None, ge=20, le=200)
    current_limit_a: float | None = Field(default=None, ge=0, le=20000)
    temp_deviation_pct: float | None = Field(default=None, ge=0, le=100)
    current_deviation_pct: float | None = Field(default=None, ge=0, le=100)
    rise_rate_limit_c_per_day: float | None = Field(default=None, ge=0, le=50)
    notify_enabled: bool | None = None
    pilot: bool | None = None


class NotificationSettingsUpdate(BaseModel):
    critical_enabled: bool | None = None
    warning_enabled: bool | None = None
    info_enabled: bool | None = None
    quiet_hours_enabled: bool | None = None
    quiet_start: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    quiet_end: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    group_name: str | None = Field(default=None, max_length=64)
    owners: list[str] | None = Field(default=None, max_length=20)

    @field_validator("owners")
    @classmethod
    def normalize_owners(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [item.strip() for item in value if item.strip()]
        return cleaned[:20]


class PollResponse(BaseModel):
    accepted: bool
    message: str


class FeishuTestResponse(BaseModel):
    status: Literal["sent", "failed", "skipped"]
    attempts: int
    response_code: int | None
    detail: str
