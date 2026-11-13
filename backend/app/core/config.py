"""应用配置，全部通过 MP_ 前缀环境变量覆盖。"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_prefix="MP_",
        extra="ignore",
    )

    app_name: str = "MotorPulse 大电机风险监测平台"
    app_version: str = "0.4.1"
    app_env: Literal["dev", "prod"] = "dev"
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"

    database_url: str = "sqlite:///./data/motor.db"
    auto_create_tables: bool = True
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    auth_mode: Literal["off", "proxy"] = "off"
    auth_proxy_header: str = "X-Auth-User"
    auth_role_header: str = "X-Auth-Role"
    default_user: str = "设备科 · 观察员"

    timezone: str = "Asia/Shanghai"
    poll_interval_minutes: int = 15
    poll_on_start: bool = True
    run_collector: bool = True
    collector_mode: Literal["modbus", "simulator"] = "modbus"
    modbus_timeout_seconds: float = 3.0
    modbus_retries: int = 2
    modbus_register_gap_seconds: float = 0.05
    retention_days: int = 180
    baseline_days: int = 30
    rise_rate_days: int = 7
    baseline_cache_minutes: int = 60
    alarm_suppression_minutes: int = 30

    feishu_enabled: bool = False
    feishu_webhook_url: str = ""
    feishu_webhook_secret: str = ""
    feishu_timeout_seconds: float = 5.0
    feishu_max_attempts: int = 3

    pilot_start_date: str = "2026-10-26"
    pilot_days: int = 30
    pilot_scope: str = "M-01 循环水泵 / M-02 循环水泵 / M-03 主排风机"

    lora_frequency_mhz: int = 470
    lora_baud_rate: int = 1200
    lora_sf: int = 7
    lora_bw_khz: int = 125
    lora_cr: str = "4/5"

    seed_demo_on_start: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def poll_interval_seconds(self) -> int:
        return self.poll_interval_minutes * 60

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def feishu_configured(self) -> bool:
        return bool(self.feishu_enabled and self.feishu_webhook_url)

    def masked_webhook(self) -> str:
        url = self.feishu_webhook_url
        if not url:
            return ""
        if len(url) <= 18:
            return "••••••••"
        return f"{url[:16]}••••••••{url[-4:]}"

    def ensure_sqlite_dir(self) -> None:
        prefix = "sqlite:///"
        if self.database_url.startswith(prefix):
            raw_path = self.database_url.removeprefix(prefix)
            if raw_path and raw_path != ":memory:":
                Path(raw_path).parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
