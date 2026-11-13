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
from app.schemas import FeishuAppSettingsUpdate, FeishuTestResponse, NotificationSettingsUpdate
from app.services.acceptance import acceptance_snapshot
from app.services.feishu import send_test_message
from app.services.feishu_app import send_test_app
from app.services.feishu_longconn import connection_status, ensure_connection
from app.services.settings import (
    get_feishu_app_config,
    get_notification_config,
    public_feishu_app_config,
    save_feishu_app_config,
    save_notification_config,
)

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
    app_config = get_feishu_app_config(db)
    app_public = public_feishu_app_config(app_config)
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
                "phase_imbalance_pct": motor.phase_imbalance_pct,
                "vibration_limit_mm_s": motor.vibration_limit_mm_s,
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
            **app_public,
            "configured": (
                app_public["enabled"]
                and app_public["secret_set"]
                and bool(app_public["app_id"])
                and bool(app_public["chat_id"])
            )
            or settings.feishu_configured,
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


@router.get("/settings/feishu")
def get_feishu_settings(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    config = get_feishu_app_config(db)
    public = public_feishu_app_config(config)
    return {
        **public,
        "group_name": get_notification_config(db).get("group_name", "设备运维告警群"),
        "long_connection": connection_status(),
    }


@router.put("/settings/feishu")
def update_feishu_settings(
    payload: FeishuAppSettingsUpdate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    changes = payload.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(status_code=422, detail="没有需要更新的字段")
    existing = get_feishu_app_config(db)
    enabled = bool(changes.get("enabled", existing.get("enabled")))
    app_id = str(changes.get("app_id", existing.get("app_id", ""))).strip()
    chat_id = str(changes.get("chat_id", existing.get("chat_id", ""))).strip()
    secret = str(changes.get("app_secret", "")).strip()
    if enabled and (not app_id or not chat_id or not (secret or existing.get("app_secret"))):
        raise HTTPException(
            status_code=422,
            detail="启用飞书应用前请填写 App ID、App Secret 和 Chat ID",
        )
    config = save_feishu_app_config(
        db, {**changes, "app_id": app_id, "chat_id": chat_id}, user.name
    )
    audit(
        db,
        user,
        "update_feishu_app",
        "feishu_app",
        {"app_id": app_id, "chat_id": chat_id, "enabled": enabled},
    )
    db.commit()
    public = public_feishu_app_config(config)
    status = ensure_connection(config)
    return {**public, "long_connection": status}


@router.post("/settings/feishu/app/test", response_model=FeishuTestResponse)
def test_feishu_app(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> FeishuTestResponse:
    config = get_feishu_app_config(db)
    if not (config.get("app_id") and config.get("app_secret") and config.get("chat_id")):
        raise HTTPException(status_code=422, detail="飞书应用凭据或 Chat ID 未配置")
    try:
        result = send_test_app(config)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"飞书测试失败: {exc}") from exc
    return FeishuTestResponse(
        status=result.status,
        attempts=result.attempts,
        response_code=result.response_code,
        detail=(
            "测试消息已发送"
            if result.status == "sent"
            else f"测试消息发送失败: {result.response_body or '请检查飞书应用配置'}"
        ),
    )
