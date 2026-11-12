"""运行期可编辑配置（通知策略、试点信息）。"""

from sqlalchemy.orm import Session

from app.db.init_db import DEFAULT_NOTIFICATION_CONFIG
from app.db.models import AppConfig


def get_config(db: Session, key: str) -> dict:
    row = db.get(AppConfig, key)
    return dict(row.value) if row and isinstance(row.value, dict) else {}


def save_config(db: Session, key: str, value: dict, actor: str) -> dict:
    row = db.get(AppConfig, key)
    if row is None:
        row = AppConfig(key=key, value=value, updated_by=actor)
        db.add(row)
    else:
        row.value = value
        row.updated_by = actor
    db.flush()
    return dict(row.value)


def get_notification_config(db: Session) -> dict:
    config = {**DEFAULT_NOTIFICATION_CONFIG, **get_config(db, "notifications")}
    if not isinstance(config.get("owners"), list):
        config["owners"] = list(DEFAULT_NOTIFICATION_CONFIG["owners"])
    return config


def save_notification_config(db: Session, value: dict, actor: str) -> dict:
    merged = {**DEFAULT_NOTIFICATION_CONFIG, **get_config(db, "notifications"), **value}
    return save_config(db, "notifications", merged, actor)


def choose_owner(rule_key: str, config: dict) -> str:
    owners = [str(item) for item in config.get("owners", []) if str(item).strip()]
    if not owners:
        return "设备运维组"
    if rule_key.startswith("temp"):
        return owners[0]
    if rule_key.startswith("current"):
        return owners[1] if len(owners) > 1 else owners[0]
    return owners[-1]


def level_switch_enabled(level: str, config: dict) -> bool:
    if level == "crit":
        return bool(config.get("critical_enabled", True))
    if level == "warn":
        return bool(config.get("warning_enabled", True))
    return bool(config.get("info_enabled", True))
