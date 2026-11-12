"""建表与配置初始化。生产环境由 Alembic 负责结构迁移。"""

import logging

from app.core.config import settings
from app.db.base import Base
from app.db.models import AppConfig  # noqa: F401  (确保模型注册)
from app.db.session import SessionLocal, engine

logger = logging.getLogger(__name__)

DEFAULT_NOTIFICATION_CONFIG = {
    "critical_enabled": True,
    "warning_enabled": True,
    "info_enabled": True,
    "quiet_hours_enabled": True,
    "quiet_start": "22:00",
    "quiet_end": "06:00",
    "group_name": "设备运维告警群",
    "owners": ["王工 · 设备科", "李工 · 电气", "惠哥 · 生产"],
}


def init_db() -> None:
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.get(AppConfig, "notifications") is None:
            db.add(AppConfig(key="notifications", value=DEFAULT_NOTIFICATION_CONFIG))
        if db.get(AppConfig, "pilot") is None:
            db.add(
                AppConfig(
                    key="pilot",
                    value={
                        "start_date": settings.pilot_start_date,
                        "days": settings.pilot_days,
                        "scope": settings.pilot_scope,
                    },
                )
            )
        db.commit()
    logger.info("数据库初始化完成")
