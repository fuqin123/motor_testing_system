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
    phase_imbalance_pct: float | None = Field(default=None, ge=0, le=100)
    vibration_limit_mm_s: float | None = Field(default=None, ge=0, le=100)
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


class MotorUpsert(BaseModel):
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9][A-Za-z0-9-]{0,31}$")
    name: str = Field(min_length=1, max_length=128)
    location: str = Field(default="", max_length=128)
    group_name: str = Field(default="未分组", max_length=64)
    rated_kw: float = Field(default=0, ge=0, le=100000)
    rated_current_a: float = Field(default=0, ge=0, le=100000)
    pilot: bool = False
    enabled: bool = True
    node_code: str = Field(default="N-01", max_length=32)
    vfd_model: str = Field(default="", max_length=64)
    install_date: str = Field(default="", max_length=16)
    last_maintenance: str = Field(default="", max_length=64)
    temp_limit_c: float = Field(default=85, ge=20, le=200)
    current_limit_a: float = Field(default=0, ge=0, le=20000)
    temp_deviation_pct: float = Field(default=8, ge=0, le=100)
    current_deviation_pct: float = Field(default=10, ge=0, le=100)
    phase_imbalance_pct: float = Field(default=10, ge=0, le=100)
    vibration_limit_mm_s: float = Field(default=4.5, ge=0, le=100)
    rise_rate_limit_c_per_day: float = Field(default=1, ge=0, le=50)
    notify_enabled: bool = True


class GatewayUpsert(BaseModel):
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9][A-Za-z0-9-]{0,31}$")
    name: str = Field(min_length=1, max_length=128)
    host: str = Field(min_length=1, max_length=64)
    port: int = Field(default=502, ge=1, le=65535)
    framer: Literal["rtu", "tcp"] = "rtu"
    enabled: bool = True
    model: str = Field(default="LoRa 网关", max_length=64)
    firmware: str = Field(default="—", max_length=32)
    note: str = Field(default="", max_length=255)


class SensorUpsert(BaseModel):
    id: int | None = None
    code: str | None = Field(default=None, max_length=32)
    motor_code: str = Field(min_length=1, max_length=32)
    gateway_code: str = Field(min_length=1, max_length=32)
    kind: Literal["temperature", "current", "vibration"]
    name: str = Field(default="", max_length=128)
    slave_id: int = Field(default=1, ge=1, le=247)
    register_address: int = Field(default=0, ge=0, le=65535)
    register_count: int = Field(default=1, ge=1, le=16)
    scale: float = Field(default=0.1, gt=0, le=1000)
    unit: str = Field(default="℃", max_length=8)
    enabled: bool = True
    power_type: str = Field(default="市电供电", max_length=16)
    firmware: str = Field(default="—", max_length=32)


class FeishuAppSettingsUpdate(BaseModel):
    enabled: bool | None = None
    app_id: str | None = Field(default=None, max_length=128)
    app_secret: str | None = Field(default=None, max_length=256)
    chat_id: str | None = Field(default=None, max_length=128)
