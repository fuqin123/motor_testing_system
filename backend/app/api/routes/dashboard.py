from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import DateView, get_current_user, get_date_view, get_db
from app.api.serializers import alarm_dict, alarm_response_minutes, pilot_info
from app.core.config import settings
from app.core.security import UserContext
from app.core.time import as_utc, iso, next_poll_time, utcnow
from app.db.models import Alarm, Gateway, Motor, NotificationLog, PollCycle, Reading, Sensor
from app.services.analysis import (
    RANGE_CONFIG,
    bucket_readings,
    build_series,
    motor_summary,
    normalize_range,
)
from app.services.baseline import compute_baseline, deviation_pct
from app.services.collector import get_collector
from app.services.telemetry import (
    active_alarms,
    active_alarms_by_motor,
    alarms_by_motor_from_list,
    alarms_in_range,
    gateway_online,
    is_online,
    latest_readings,
    load_pct,
    motor_status,
    recent_readings_map,
    today_poll_stats,
)

router = APIRouter(tags=["监测总览"])

LEVEL_ORDER = {"crit": 0, "warn": 1, "info": 2}


def _sort_alarms(alarms: list[Alarm]) -> list[Alarm]:
    return sorted(
        alarms,
        key=lambda item: (
            LEVEL_ORDER.get(item.level, 3),
            -((as_utc(item.triggered_at) or utcnow()).timestamp()),
        ),
    )


@router.get("/dashboard/trend")
def dashboard_trend(
    range_key: str = Query(default="24h", alias="range"),
    motor_id: str | None = Query(default=None, description="电机编码，不传则返回全部均值"),
    view: DateView = Depends(get_date_view),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    normalized = normalize_range(range_key)
    config = RANGE_CONFIG[normalized]
    end = view.as_of
    since = end - timedelta(hours=config["hours"])
    response_meta = {
        "range": normalized,
        "bucket_minutes": config["bucket_minutes"],
        "date": view.date_text,
        "is_today": view.is_today,
    }

    if motor_id:
        motor = db.scalar(select(Motor).where(Motor.code == motor_id))
        if motor is None:
            raise HTTPException(status_code=404, detail=f"电机 {motor_id} 不存在")
        points = build_series(db, motor, normalized, end)
        return {"motor_code": motor.code, **response_meta, "points": points}

    motors = list(
        db.scalars(select(Motor).where(Motor.enabled.is_(True)).order_by(Motor.code)).all()
    )
    if not motors:
        return {"motor_code": None, **response_meta, "points": []}

    rows = db.scalars(
        select(Reading).where(
            Reading.motor_id.in_([motor.id for motor in motors]),
            Reading.ts >= since,
            Reading.ts <= end,
            Reading.quality != "error",
        )
    ).all()
    grouped: dict[int, list[Reading]] = {}
    for reading in rows:
        grouped.setdefault(reading.motor_id, []).append(reading)
    aggregated: dict[str, dict[str, list[float]]] = {}
    for readings in grouped.values():
        for point in bucket_readings(readings, config["bucket_minutes"]):
            target = aggregated.setdefault(
                str(point["ts"]),
                {"temp": [], "avg": [], "a": [], "b": [], "c": []},
            )
            for key, source in (
                ("temp", "temperature_c"),
                ("avg", "current_avg_a"),
                ("a", "current_a"),
                ("b", "current_b"),
                ("c", "current_c"),
            ):
                value = point[source]
                if value is not None:
                    target[key].append(float(value))
    points = []
    for ts in sorted(aggregated):
        values = aggregated[ts]
        points.append(
            {
                "ts": ts,
                "temperature_c": (
                    round(sum(values["temp"]) / len(values["temp"]), 2) if values["temp"] else None
                ),
                "current_avg_a": (
                    round(sum(values["avg"]) / len(values["avg"]), 2) if values["avg"] else None
                ),
                "current_a": round(sum(values["a"]) / len(values["a"]), 2) if values["a"] else None,
                "current_b": round(sum(values["b"]) / len(values["b"]), 2) if values["b"] else None,
                "current_c": round(sum(values["c"]) / len(values["c"]), 2) if values["c"] else None,
            }
        )
    return {"motor_code": None, **response_meta, "points": points}


@router.get("/dashboard/overview")
def overview(
    view: DateView = Depends(get_date_view),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    now = view.as_of
    motors = list(
        db.scalars(select(Motor).where(Motor.enabled.is_(True)).order_by(Motor.code)).all()
    )
    motor_ids = [motor.id for motor in motors]
    latest_map = latest_readings(db, motor_ids, until=now)
    recent_map = recent_readings_map(db, motor_ids, limit=26, until=now)
    if view.is_today:
        alarm_list = active_alarms(db)
        alarm_map = active_alarms_by_motor(db)
    else:
        alarm_list = alarms_in_range(db, view.day_start, view.day_end)
        alarm_map = alarms_by_motor_from_list(alarm_list)

    cards = []
    for motor in motors:
        latest = latest_map.get(motor.id)
        baseline = compute_baseline(db, motor, now=now)
        temp_dev = (
            deviation_pct(latest.temperature_c, baseline.temp_median)
            if latest and baseline
            else None
        )
        recent = recent_map.get(motor.id, [])
        spark_temp = [
            round(item.temperature_c, 2) for item in recent if item.temperature_c is not None
        ][-24:]
        spark_current = [
            round(item.current_avg_a, 2) for item in recent if item.current_avg_a is not None
        ][-24:]
        cards.append(
            {
                **motor_summary(motor),
                "status": motor_status(motor, latest, alarm_map.get(motor.code, []), now),
                "online": is_online(latest, now),
                "temperature_c": latest.temperature_c if latest else None,
                "current_avg_a": latest.current_avg_a if latest else None,
                "load_pct": load_pct(motor, latest),
                "temp_deviation_pct": round(temp_dev, 2) if temp_dev is not None else None,
                "last_seen_at": iso(latest.ts) if latest else None,
                "quality": latest.quality if latest else None,
                "spark_temp": spark_temp,
                "spark_current": spark_current,
            }
        )

    critical = [alarm for alarm in alarm_list if alarm.level == "crit"]
    warnings = [alarm for alarm in alarm_list if alarm.level == "warn"]
    online_motors = sum(1 for motor in motors if is_online(latest_map.get(motor.id), now))
    temperatures = [
        latest.temperature_c for latest in latest_map.values() if latest.temperature_c is not None
    ]
    loads = [
        load_pct(motor, latest_map.get(motor.id))
        for motor in motors
        if load_pct(motor, latest_map.get(motor.id)) is not None
    ]

    day_start, day_end = view.day_start, view.day_end
    poll_stats = today_poll_stats(db, day_start, day_end)
    gateways = list(db.scalars(select(Gateway).where(Gateway.enabled.is_(True))).all())
    if view.is_today:
        gateway_online_count = sum(1 for gateway in gateways if gateway_online(gateway, now))
    else:
        gateway_online_count = (
            db.scalar(
                select(func.count(func.distinct(PollCycle.gateway_code))).where(
                    PollCycle.started_at >= day_start,
                    PollCycle.started_at < day_end,
                    PollCycle.successes > 0,
                )
            )
            or 0
        )

    node_codes = {motor.node_code for motor in motors}
    online_node_codes = {
        motor.node_code for motor in motors if is_online(latest_map.get(motor.id), now)
    }
    avg_rssi = db.scalar(select(func.avg(Sensor.signal_dbm)).where(Sensor.signal_dbm.is_not(None)))

    notifications_today = (
        db.scalar(
            select(func.count(NotificationLog.id)).where(
                NotificationLog.created_at >= day_start,
                NotificationLog.created_at < day_end,
                NotificationLog.status == "sent",
            )
        )
        or 0
    )
    closed_today_rows = list(
        db.scalars(
            select(Alarm)
            .where(Alarm.closed_at >= day_start, Alarm.closed_at < day_end)
            .order_by(Alarm.closed_at.desc())
        ).all()
    )
    response_minutes = alarm_response_minutes(closed_today_rows)

    cycle_query = select(PollCycle).order_by(PollCycle.started_at.desc())
    if not view.is_today:
        cycle_query = cycle_query.where(
            PollCycle.started_at >= day_start, PollCycle.started_at < day_end
        )
    last_cycle = db.scalar(cycle_query.limit(1))
    collector = get_collector()
    collector_status = collector.status() if collector else None
    next_run = None
    if view.is_today:
        next_run = (
            collector_status.get("next_run_at")
            if collector_status and collector_status.get("next_run_at")
            else iso(next_poll_time(now, settings.poll_interval_minutes))
        )
    sampling = {
        "interval_minutes": settings.poll_interval_minutes,
        "last_poll_at": (
            iso(last_cycle.finished_at or last_cycle.started_at) if last_cycle else None
        ),
        "next_poll_at": next_run,
        "collector_mode": settings.collector_mode,
        "collector_running": bool(collector_status and collector_status.get("thread_alive")),
    }

    active_sorted = _sort_alarms(alarm_list)[:5]
    pilot = pilot_info(settings.pilot_start_date, settings.pilot_days, settings.pilot_scope)

    return {
        "generated_at": iso(now),
        "date": view.date_text,
        "is_today": view.is_today,
        "user": {"name": user.name, "role": user.role},
        "sampling": sampling,
        "pilot": pilot,
        "kpis": {
            "online_motors": online_motors,
            "total_motors": len(motors),
            "active_alarms": len(alarm_list),
            "critical_alarms": len(critical),
            "warning_alarms": len(warnings),
            "avg_temperature_c": (
                round(sum(temperatures) / len(temperatures), 2) if temperatures else None
            ),
            "avg_load_pct": round(sum(loads) / len(loads), 2) if loads else None,
            "link_availability_pct": poll_stats["link_availability_pct"],
            "packets_today": poll_stats["packets_today"],
            "packet_loss_pct": poll_stats["packet_loss_pct"],
            "avg_latency_ms": poll_stats["avg_latency_ms"],
        },
        "motors": cards,
        "active_alarms": [alarm_dict(alarm) for alarm in active_sorted],
        "link": {
            "gateways_online": gateway_online_count,
            "gateways_total": len(gateways),
            "nodes_online": len(online_node_codes),
            "nodes_total": len(node_codes),
            "avg_rssi_dbm": round(float(avg_rssi), 1) if avg_rssi is not None else None,
            "packets_today": poll_stats["packets_today"],
            "packet_loss_pct": poll_stats["packet_loss_pct"],
            "avg_latency_ms": poll_stats["avg_latency_ms"],
        },
        "loop": {
            "notifications_today": int(notifications_today),
            "closed_today": len(closed_today_rows),
            "avg_response_min": response_minutes,
            "items": [
                {
                    "text": f"{alarm.motor_code or alarm.device_code} {alarm.title} · {alarm.solution or '已闭环'}",
                    "who": alarm.closed_by or alarm.owner,
                    "ts": iso(alarm.closed_at),
                }
                for alarm in closed_today_rows[:5]
            ],
        },
    }
