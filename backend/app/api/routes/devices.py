from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.serializers import gateway_dict, sensor_dict
from app.core.security import UserContext
from app.core.time import as_utc, iso, utcnow
from app.db.models import Alarm, Gateway, PollCycle, Sensor
from app.schemas import PollResponse
from app.services.collector import request_manual_poll
from app.services.telemetry import gateway_online, sensor_online

router = APIRouter(tags=["设备与链路"])

STATUS_TEXT = {"open": "未处理", "ack": "处理中", "closed": "已闭环"}


@router.get("/devices")
def list_devices(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    gateways = list(db.scalars(select(Gateway).order_by(Gateway.code)).all())
    sensors = list(db.scalars(select(Sensor).order_by(Sensor.code)).all())
    alarms = list(db.scalars(select(Alarm).order_by(Alarm.triggered_at.desc()).limit(12)).all())
    cycles = list(
        db.scalars(select(PollCycle).order_by(PollCycle.started_at.desc()).limit(12)).all()
    )

    events: list[tuple] = []
    for alarm in alarms:
        events.append(
            (
                as_utc(alarm.triggered_at) or utcnow(),
                {
                    "ts": iso(alarm.triggered_at),
                    "level": alarm.level,
                    "text": (
                        f"{alarm.motor_code or alarm.device_code} {alarm.title} · "
                        f"{STATUS_TEXT.get(alarm.status, alarm.status)}"
                    ),
                },
            )
        )
    for cycle in cycles:
        events.append(
            (
                as_utc(cycle.started_at) or utcnow(),
                {
                    "ts": iso(cycle.started_at),
                    "level": "ok" if not cycle.failures else "warn",
                    "text": (
                        f"{cycle.gateway_code} 采集完成：成功 {cycle.successes}/{cycle.attempts}，"
                        f"耗时 {cycle.duration_ms}ms"
                    ),
                },
            )
        )
    events.sort(key=lambda item: item[0], reverse=True)

    return {
        "summary": {
            "gateways_online": sum(1 for gateway in gateways if gateway_online(gateway)),
            "gateways_total": len(gateways),
            "sensors_total": len([sensor for sensor in sensors if sensor.enabled]),
            "sensors_online": sum(
                1 for sensor in sensors if sensor.enabled and sensor_online(sensor)
            ),
        },
        "gateways": [gateway_dict(gateway) for gateway in gateways],
        "sensors": [sensor_dict(sensor) for sensor in sensors],
        "events": [item[1] for item in events[:20]],
    }


@router.post("/devices/gateways/{code}/poll", response_model=PollResponse)
def poll_gateway(
    code: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> PollResponse:
    gateway = db.scalar(select(Gateway).where(Gateway.code == code))
    if gateway is None:
        raise HTTPException(status_code=404, detail=f"网关 {code} 不存在")
    if not gateway.enabled:
        raise HTTPException(status_code=409, detail=f"网关 {code} 已停用")
    result = request_manual_poll()
    message = "已加入召测队列，下一轮采集立即执行" if result == "queued" else "召测已启动"
    return PollResponse(accepted=True, message=message)
