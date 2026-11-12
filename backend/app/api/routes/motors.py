from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import audit, get_current_user, get_db
from app.api.serializers import alarm_dict, motor_card, sensor_dict
from app.core.security import UserContext
from app.core.time import utcnow
from app.db.models import Alarm, Motor
from app.schemas import ThresholdUpdate
from app.services.analysis import RANGE_CONFIG, build_series, normalize_range
from app.services.baseline import compute_baseline, deviation_pct
from app.services.telemetry import (
    active_alarms_by_motor,
    latest_readings,
    motor_status,
    recent_readings_map,
)

router = APIRouter(tags=["电机"])


def _get_motor(db: Session, code: str) -> Motor:
    motor = db.scalar(select(Motor).where(Motor.code == code))
    if motor is None:
        raise HTTPException(status_code=404, detail=f"电机 {code} 不存在")
    return motor


@router.get("/motors")
def list_motors(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    now = utcnow()
    motors = list(
        db.scalars(select(Motor).where(Motor.enabled.is_(True)).order_by(Motor.code)).all()
    )
    latest_map = latest_readings(db, [motor.id for motor in motors])
    recent_map = recent_readings_map(db, [motor.id for motor in motors], limit=26)
    alarm_map = active_alarms_by_motor(db)
    items = []
    for motor in motors:
        latest = latest_map.get(motor.id)
        baseline = compute_baseline(db, motor, now=now)
        temp_dev = (
            deviation_pct(latest.temperature_c, baseline.temp_median)
            if latest and baseline
            else None
        )
        recent = recent_map.get(motor.id, [])
        items.append(
            motor_card(
                motor,
                latest,
                motor_status(motor, latest, alarm_map.get(motor.code, []), now),
                temp_dev,
                [round(item.temperature_c, 2) for item in recent if item.temperature_c is not None],
                [round(item.current_avg_a, 2) for item in recent if item.current_avg_a is not None],
                now,
            )
        )
    return {"items": items, "total": len(items)}


@router.get("/motors/{code}")
def get_motor(
    code: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    now = utcnow()
    motor = _get_motor(db, code)
    latest_map = latest_readings(db, [motor.id])
    recent_map = recent_readings_map(db, [motor.id], limit=26)
    alarm_map = active_alarms_by_motor(db)
    latest = latest_map.get(motor.id)
    baseline = compute_baseline(db, motor, now=now)
    temp_dev = (
        deviation_pct(latest.temperature_c, baseline.temp_median) if latest and baseline else None
    )
    recent = recent_map.get(motor.id, [])
    recent_alarms = db.scalars(
        select(Alarm).where(Alarm.motor_code == code).order_by(Alarm.triggered_at.desc()).limit(10)
    ).all()
    return {
        "motor": motor_card(
            motor,
            latest,
            motor_status(motor, latest, alarm_map.get(motor.code, []), now),
            temp_dev,
            [round(item.temperature_c, 2) for item in recent if item.temperature_c is not None],
            [round(item.current_avg_a, 2) for item in recent if item.current_avg_a is not None],
            now,
        ),
        "sensors": [sensor_dict(sensor) for sensor in motor.sensors],
        "baseline": baseline.to_dict() if baseline else None,
        "recent_alarms": [alarm_dict(alarm) for alarm in recent_alarms],
    }


@router.get("/motors/{code}/series")
def motor_series(
    code: str,
    range_key: str = Query(default="24h", alias="range"),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    motor = _get_motor(db, code)
    normalized = normalize_range(range_key)
    points = build_series(db, motor, normalized)
    return {
        "motor_code": motor.code,
        "range": normalized,
        "bucket_minutes": RANGE_CONFIG[normalized]["bucket_minutes"],
        "points": points,
    }


@router.patch("/motors/{code}/thresholds")
def update_thresholds(
    code: str,
    payload: ThresholdUpdate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    motor = _get_motor(db, code)
    changes = payload.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(status_code=422, detail="没有需要更新的字段")
    for field, value in changes.items():
        setattr(motor, field, value)
    audit(db, user, "update_thresholds", code, changes)
    db.commit()
    return {
        "code": motor.code,
        "temp_limit_c": motor.temp_limit_c,
        "current_limit_a": motor.current_limit_a,
        "temp_deviation_pct": motor.temp_deviation_pct,
        "current_deviation_pct": motor.current_deviation_pct,
        "rise_rate_limit_c_per_day": motor.rise_rate_limit_c_per_day,
        "notify_enabled": motor.notify_enabled,
        "pilot": motor.pilot,
    }
