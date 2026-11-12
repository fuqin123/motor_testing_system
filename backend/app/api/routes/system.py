from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.serializers import gateway_dict, pilot_info
from app.core.config import settings
from app.core.security import UserContext
from app.core.time import iso, next_poll_time, utcnow
from app.db.models import Gateway, Motor, PollCycle, Sensor
from app.schemas import PollResponse
from app.services.acceptance import acceptance_snapshot
from app.services.collector import get_collector, request_manual_poll
from app.services.settings import get_notification_config

router = APIRouter(tags=["系统"])


def _sampling(db: Session) -> dict:
    last_cycle = db.scalar(select(PollCycle).order_by(PollCycle.started_at.desc()).limit(1))
    collector = get_collector()
    status = collector.status() if collector else None
    next_run = (
        status.get("next_run_at")
        if status and status.get("next_run_at")
        else iso(next_poll_time(utcnow(), settings.poll_interval_minutes))
    )
    return {
        "interval_minutes": settings.poll_interval_minutes,
        "last_poll_at": (
            iso(last_cycle.finished_at or last_cycle.started_at) if last_cycle else None
        ),
        "next_poll_at": next_run,
        "collector_mode": settings.collector_mode,
        "collector_running": bool(status and status.get("thread_alive")),
    }


@router.get("/system/me")
def me(user: UserContext = Depends(get_current_user)) -> dict:
    return {"name": user.name, "role": user.role, "auth_mode": user.auth_mode}


@router.get("/system/info")
def system_info(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    notification = get_notification_config(db)
    gateways = list(db.scalars(select(Gateway).order_by(Gateway.code)).all())
    pilot = pilot_info(settings.pilot_start_date, settings.pilot_days, settings.pilot_scope)
    collector = get_collector()
    return {
        "app": {
            "name": settings.app_name,
            "version": settings.app_version,
            "env": settings.app_env,
            "timezone": settings.timezone,
        },
        "user": {"name": user.name, "role": user.role, "auth_mode": user.auth_mode},
        "counts": {
            "motors": db.scalar(select(func.count(Motor.id)).where(Motor.enabled.is_(True))) or 0,
            "gateways": len([gateway for gateway in gateways if gateway.enabled]),
            "sensors": db.scalar(select(func.count(Sensor.id)).where(Sensor.enabled.is_(True)))
            or 0,
        },
        "sampling": _sampling(db),
        "collector": collector.status() if collector else {"thread_alive": False, "running": False},
        "retention_days": settings.retention_days,
        "baseline_days": settings.baseline_days,
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
        "pilot": pilot,
        "acceptance": acceptance_snapshot(db),
        "gateways": [gateway_dict(gateway) for gateway in gateways],
    }


@router.get("/system/collector/status")
def collector_status(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    collector = get_collector()
    sampling = _sampling(db)
    if collector is None:
        return {
            "thread_alive": False,
            "running": False,
            "last_error": None,
            "last_cycle": None,
            "sampling": sampling,
        }
    status = collector.status()
    status["sampling"] = sampling
    return status


@router.post("/system/collector/poll", response_model=PollResponse)
def trigger_poll(
    user: UserContext = Depends(get_current_user),
) -> PollResponse:
    result = request_manual_poll()
    message = "已加入召测队列，下一轮采集立即执行" if result == "queued" else "召测已启动"
    return PollResponse(accepted=True, message=message)
