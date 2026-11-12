"""API 输出序列化，集中维护前端契约。"""

from app.core.time import as_utc, iso, minutes_between, utcnow
from app.db.models import Alarm, Gateway, Motor, NotificationLog, Reading, Sensor
from app.services.analysis import motor_summary
from app.services.telemetry import gateway_online, is_online, load_pct, sensor_online

LEVEL_TEXT = {"crit": "严重", "warn": "警告", "info": "提示"}


def alarm_dict(alarm: Alarm) -> dict:
    timeline = []
    timeline.append(
        {
            "key": "triggered",
            "title": "触发告警",
            "detail": f"{alarm.title} · {alarm.description}",
            "ts": iso(alarm.triggered_at),
            "state": "hot",
        }
    )
    if alarm.notification_status in ("sent", "failed", "skipped"):
        timeline.append(
            {
                "key": "notification",
                "title": "飞书通知",
                "detail": f"{alarm.notification_to or '未配置'} · {alarm.notification_status}",
                "ts": iso(alarm.notified_at or alarm.triggered_at),
                "state": "done" if alarm.notification_status == "sent" else "",
            }
        )
    if alarm.status == "ack":
        timeline.append(
            {
                "key": "ack",
                "title": "签收处理",
                "detail": f"{alarm.owner} 已签收，开始现场排查",
                "ts": iso(alarm.last_seen_at),
                "state": "",
            }
        )
    if alarm.status == "closed":
        timeline.append(
            {
                "key": "closed",
                "title": "处理闭环",
                "detail": alarm.solution or "已处理",
                "ts": iso(alarm.closed_at),
                "state": "done",
            }
        )
    else:
        timeline.append(
            {
                "key": "waiting",
                "title": "等待人工处理",
                "detail": "平台只监测、只报警，由责任人现场检查后回写结果",
                "ts": None,
                "state": "",
            }
        )
    return {
        "id": alarm.id,
        "code": f"AL-{alarm.id:04d}",
        "level": alarm.level,
        "level_text": LEVEL_TEXT.get(alarm.level, alarm.level),
        "title": alarm.title,
        "description": alarm.description,
        "advice": alarm.advice,
        "motor_code": alarm.motor_code,
        "motor_name": alarm.motor_name,
        "device_code": alarm.device_code,
        "metric": alarm.metric,
        "value": alarm.value,
        "threshold": alarm.threshold,
        "unit": alarm.unit,
        "status": alarm.status,
        "owner": alarm.owner,
        "notification_status": alarm.notification_status,
        "notification_to": alarm.notification_to,
        "triggered_at": iso(alarm.triggered_at),
        "last_seen_at": iso(alarm.last_seen_at),
        "closed_at": iso(alarm.closed_at),
        "closed_by": alarm.closed_by,
        "solution": alarm.solution,
        "suppressed_until": iso(alarm.suppressed_until),
        "timeline": timeline,
    }


def notification_dict(log: NotificationLog) -> dict:
    return {
        "id": log.id,
        "channel": log.channel,
        "target": log.target,
        "status": log.status,
        "attempts": log.attempts,
        "response_code": log.response_code,
        "created_at": iso(log.created_at),
    }


def motor_card(
    motor: Motor,
    latest: Reading | None,
    status: str,
    temp_deviation_pct: float | None,
    spark_temp: list[float],
    spark_current: list[float],
    now=None,
) -> dict:
    return {
        **motor_summary(motor),
        "status": status,
        "online": is_online(latest, now),
        "temperature_c": latest.temperature_c if latest else None,
        "current_avg_a": latest.current_avg_a if latest else None,
        "current_a": latest.current_a if latest else None,
        "current_b": latest.current_b if latest else None,
        "current_c": latest.current_c if latest else None,
        "load_pct": load_pct(motor, latest),
        "temp_deviation_pct": (
            round(temp_deviation_pct, 2) if temp_deviation_pct is not None else None
        ),
        "last_seen_at": iso(latest.ts) if latest else None,
        "quality": latest.quality if latest else None,
        "spark_temp": spark_temp,
        "spark_current": spark_current,
    }


def gateway_dict(gateway: Gateway) -> dict:
    return {
        "id": gateway.id,
        "code": gateway.code,
        "name": gateway.name,
        "host": gateway.host,
        "port": gateway.port,
        "framer": gateway.framer,
        "enabled": gateway.enabled,
        "model": gateway.model,
        "firmware": gateway.firmware,
        "note": gateway.note,
        "online": gateway_online(gateway),
        "last_seen_at": iso(gateway.last_seen_at),
        "last_error": gateway.last_error,
        "consecutive_failures": gateway.consecutive_failures,
        "sensor_count": len(gateway.sensors),
    }


def sensor_dict(sensor: Sensor) -> dict:
    return {
        "id": sensor.id,
        "code": sensor.code,
        "kind": sensor.kind,
        "kind_text": "温度传感器" if sensor.kind == "temperature" else "电流传感器",
        "name": sensor.name,
        "motor_code": sensor.motor.code if sensor.motor else None,
        "motor_name": sensor.motor.name if sensor.motor else None,
        "gateway_code": sensor.gateway.code if sensor.gateway else None,
        "slave_id": sensor.slave_id,
        "register_address": sensor.register_address,
        "register_count": sensor.register_count,
        "scale": sensor.scale,
        "unit": sensor.unit,
        "enabled": sensor.enabled,
        "power_type": sensor.power_type,
        "firmware": sensor.firmware,
        "signal_dbm": sensor.signal_dbm,
        "snr_db": sensor.snr_db,
        "online": sensor_online(sensor),
        "last_read_at": iso(sensor.last_read_at),
        "last_error": sensor.last_error,
        "consecutive_failures": sensor.consecutive_failures,
    }


def pilot_info(start_date: str, days: int, scope: str) -> dict:
    from datetime import date

    try:
        start = date.fromisoformat(start_date)
        current_day = max(1, (utcnow().date() - start).days + 1)
    except ValueError:
        start = None
        current_day = 1
    progress = min(100, round(current_day / max(days, 1) * 100, 1))
    remaining = max(0, days - current_day)
    return {
        "start_date": start_date,
        "days": days,
        "current_day": current_day,
        "progress_pct": progress,
        "remaining_days": remaining,
        "scope": scope,
    }


def alarm_response_minutes(alarms: list[Alarm]) -> float | None:
    values = [
        minutes
        for alarm in alarms
        if (minutes := minutes_between(alarm.triggered_at, alarm.closed_at)) is not None
    ]
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def latest_notification(db, alarm_id: int) -> NotificationLog | None:
    from sqlalchemy import select

    return db.scalar(
        select(NotificationLog)
        .where(NotificationLog.alarm_id == alarm_id)
        .order_by(NotificationLog.created_at.desc())
        .limit(1)
    )


def utc_iso(value) -> str | None:
    return iso(as_utc(value))
