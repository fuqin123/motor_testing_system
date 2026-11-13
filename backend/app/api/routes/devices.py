from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import audit, get_current_user, get_db
from app.api.serializers import gateway_dict, sensor_dict
from app.core.security import UserContext
from app.core.time import as_utc, iso, utcnow
from app.db.models import Alarm, Gateway, Motor, PollCycle, Sensor
from app.schemas import GatewayUpsert, PollResponse, SensorUpsert
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


def _auto_sensor_code(motor_code: str, kind: str) -> str:
    digits = "".join(char for char in motor_code if char.isdigit())
    suffix = (
        digits.zfill(2)
        if digits
        else "".join(char for char in motor_code if char.isalnum()) or "00"
    )
    prefix = {"temperature": "T", "current": "C", "vibration": "V"}.get(kind, "S")
    return f"{prefix}-{suffix}"[:32]


@router.post("/devices/gateways")
def upsert_gateway(
    payload: GatewayUpsert,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    gateway = db.scalar(select(Gateway).where(Gateway.code == payload.code))
    created = gateway is None
    if gateway is None:
        gateway = Gateway(code=payload.code, name=payload.name, host=payload.host)
        db.add(gateway)
    for field, value in payload.model_dump().items():
        setattr(gateway, field, value)
    audit(
        db,
        user,
        "create_gateway" if created else "update_gateway",
        payload.code,
        payload.model_dump(),
    )
    db.commit()
    return {"created": created, "gateway": gateway_dict(gateway)}


@router.delete("/devices/gateways/{code}")
def delete_gateway(
    code: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    gateway = db.scalar(select(Gateway).where(Gateway.code == code))
    if gateway is None:
        raise HTTPException(status_code=404, detail=f"网关 {code} 不存在")
    sensor_count = (
        db.scalar(select(func.count(Sensor.id)).where(Sensor.gateway_id == gateway.id)) or 0
    )
    if sensor_count:
        raise HTTPException(
            status_code=409,
            detail=f"网关 {code} 仍绑定 {sensor_count} 个采集点，请先解绑或删除采集点",
        )
    audit(db, user, "delete_gateway", code, {})
    db.delete(gateway)
    db.commit()
    return {"deleted": True, "code": code}


@router.post("/devices/sensors")
def upsert_sensor(
    payload: SensorUpsert,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    motor = db.scalar(select(Motor).where(Motor.code == payload.motor_code))
    if motor is None:
        raise HTTPException(status_code=404, detail=f"电机 {payload.motor_code} 不存在")
    gateway = db.scalar(select(Gateway).where(Gateway.code == payload.gateway_code))
    if gateway is None:
        raise HTTPException(status_code=404, detail=f"网关 {payload.gateway_code} 不存在")

    sensor = db.get(Sensor, payload.id) if payload.id else None
    if payload.id and sensor is None:
        raise HTTPException(status_code=404, detail="采集点不存在")

    if sensor is None and payload.code:
        sensor = db.scalar(select(Sensor).where(Sensor.code == payload.code))
    if sensor is None:
        sensor = db.scalar(
            select(Sensor).where(
                Sensor.motor_id == motor.id,
                Sensor.kind == payload.kind,
            )
        )

    code = payload.code or (sensor.code if sensor else _auto_sensor_code(motor.code, payload.kind))
    sensor_id = sensor.id if sensor else -1
    code_conflict = db.scalar(select(Sensor).where(Sensor.code == code, Sensor.id != sensor_id))
    if code_conflict:
        raise HTTPException(status_code=409, detail=f"采集点编码 {code} 已被使用")
    kind_conflict = db.scalar(
        select(Sensor).where(
            Sensor.motor_id == motor.id,
            Sensor.kind == payload.kind,
            Sensor.id != sensor_id,
        )
    )
    if kind_conflict:
        raise HTTPException(
            status_code=409,
            detail=f"电机 {motor.code} 已存在{payload.kind}采集点",
        )

    created = sensor is None
    if sensor is None:
        sensor = Sensor(code=code, motor_id=motor.id, gateway_id=gateway.id, kind=payload.kind)
        db.add(sensor)

    changed_source = (
        sensor.slave_id != payload.slave_id
        or sensor.register_address != payload.register_address
        or sensor.register_count != payload.register_count
        or sensor.scale != payload.scale
        or sensor.gateway_id != gateway.id
    )
    sensor.code = code
    sensor.motor_id = motor.id
    sensor.gateway_id = gateway.id
    sensor.kind = payload.kind
    sensor.name = payload.name or ("外壳温度" if payload.kind == "temperature" else "三相电流")
    sensor.slave_id = payload.slave_id
    sensor.register_address = payload.register_address
    sensor.register_count = payload.register_count
    sensor.scale = payload.scale
    sensor.unit = payload.unit
    sensor.enabled = payload.enabled
    sensor.power_type = payload.power_type
    sensor.firmware = payload.firmware
    if changed_source:
        sensor.last_read_at = None
        sensor.last_error = None
        sensor.consecutive_failures = 0
    audit(
        db,
        user,
        "create_sensor" if created else "update_sensor",
        sensor.code,
        payload.model_dump(),
    )
    db.commit()
    return {"created": created, "sensor": sensor_dict(sensor)}


@router.delete("/devices/sensors/{sensor_id}")
def delete_sensor(
    sensor_id: int,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    sensor = db.get(Sensor, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="采集点不存在")
    audit(db, user, "delete_sensor", sensor.code, {})
    db.delete(sensor)
    db.commit()
    return {"deleted": True, "id": sensor_id}
