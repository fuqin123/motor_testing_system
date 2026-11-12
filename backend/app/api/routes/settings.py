from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import audit, get_current_user, get_db
from app.api.routes.system import _sampling
from app.api.serializers import pilot_info
from app.core.config import settings
from app.core.security import UserContext
from app.db.models import Motor
from app.schemas import FeishuTestResponse, NotificationSettingsUpdate
from app.services.acceptance import acceptance_snapshot
from app.services.feishu import send_test_message
from app.services.settings import get_notification_config, save_notification_config

router = APIRouter(tags=["设置"])


def _validate_clock(value: str) -> None:
    try:
        datetime.strptime(value, "%H:%M")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"时间格式应为 HH:MM: {value}") from exc


@router.get("/settings")
def get_settings(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    motors = list(db.scalars(select(Motor).order_by(Motor.code)).all())
    notification = get_notification_config(db)
    return {
        "motors": [
            {
                "code": motor.code,
                "name": motor.name,
                "pilot": motor.pilot,
                "enabled": motor.enabled,
                "rated_current_a": motor.rated_current_a,
                "temp_limit_c": motor.temp_limit_c,
                "current_limit_a": motor.current_limit_a,
                "temp_deviation_pct": motor.temp_deviation_pct,
                "current_deviation_pct": motor.current_deviation_pct,
                "rise_rate_limit_c_per_day": motor.rise_rate_limit_c_per_day,
                "notify_enabled": motor.notify_enabled,
            }
            for motor in motors
        ],
        "notifications": notification,
        "sampling": _sampling(db),
        "lora": {
            "frequency_mhz": settings.lora_frequency_mhz,
            "baud_rate": settings.lora_baud_rate,
            "sf": settings.lora_sf,
            "bw_khz": settings.lora_bw_khz,
            "cr": settings.lora_cr,
        },
        "feishu": {
            "configured": settings.feishu_configured,
            "masked_webhook": settings.masked_webhook(),
            "group_name": notification.get("group_name", "设备运维告警群"),
        },
        "pilot": pilot_info(settings.pilot_start_date, settings.pilot_days, settings.pilot_scope),
        "acceptance": acceptance_snapshot(db),
    }


@router.put("/settings/notifications")
def update_notifications(
    payload: NotificationSettingsUpdate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    changes = payload.model_dump(exclude_none=True)
    for key in ("quiet_start", "quiet_end"):
        if key in changes:
            _validate_clock(changes[key])
    if not changes:
        raise HTTPException(status_code=422, detail="没有需要更新的字段")
    config = save_notification_config(db, changes, user.name)
    audit(db, user, "update_notifications", "notifications", changes)
    db.commit()
    return config


@router.post("/settings/feishu/test", response_model=FeishuTestResponse)
def test_feishu(
    user: UserContext = Depends(get_current_user),
) -> FeishuTestResponse:
    result = send_test_message(user.name)
    return FeishuTestResponse(**result)
