"""读数查询与运行状态派生。"""

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import as_utc, utcnow
from app.db.models import Alarm, Gateway, Motor, PollCycle, Reading, Sensor

ONLINE_TOLERANCE_CYCLES = 2


def latest_readings(
    db: Session, motor_ids: list[int] | None = None, until: datetime | None = None
) -> dict[int, Reading]:
    rn = (
        func.row_number()
        .over(partition_by=Reading.motor_id, order_by=Reading.ts.desc())
        .label("rn")
    )
    inner = select(Reading.id, rn)
    if motor_ids is not None:
        inner = inner.where(Reading.motor_id.in_(motor_ids))
    if until is not None:
        inner = inner.where(Reading.ts <= until)
    subquery = inner.subquery()
    latest_ids = select(subquery.c.id).where(subquery.c.rn == 1)
    rows = db.scalars(select(Reading).where(Reading.id.in_(latest_ids))).all()
    return {row.motor_id: row for row in rows}


def recent_readings_map(
    db: Session,
    motor_ids: list[int] | None = None,
    limit: int = 26,
    until: datetime | None = None,
) -> dict[int, list[Reading]]:
    rn = (
        func.row_number()
        .over(partition_by=Reading.motor_id, order_by=Reading.ts.desc())
        .label("rn")
    )
    inner = select(Reading.id, Reading.motor_id, rn)
    if motor_ids is not None:
        inner = inner.where(Reading.motor_id.in_(motor_ids))
    if until is not None:
        inner = inner.where(Reading.ts <= until)
    subquery = inner.subquery()
    recent_ids = select(subquery.c.id).where(subquery.c.rn <= limit)
    rows = db.scalars(select(Reading).where(Reading.id.in_(recent_ids))).all()
    grouped: dict[int, list[Reading]] = {}
    for row in rows:
        grouped.setdefault(row.motor_id, []).append(row)
    for values in grouped.values():
        values.sort(key=lambda item: as_utc(item.ts) or utcnow())
    return grouped


def series_readings(
    db: Session,
    motor_id: int,
    since: datetime,
    until: datetime | None = None,
) -> list[Reading]:
    query = select(Reading).where(Reading.motor_id == motor_id, Reading.ts >= since)
    if until is not None:
        query = query.where(Reading.ts <= until)
    return list(db.scalars(query.order_by(Reading.ts.asc())).all())


def is_online(latest: Reading | None, now: datetime | None = None) -> bool:
    if latest is None or latest.quality == "error":
        return False
    latest_ts = as_utc(latest.ts)
    now = as_utc(now or utcnow())
    if latest_ts is None or now is None:
        return False
    tolerance = timedelta(minutes=settings.poll_interval_minutes * ONLINE_TOLERANCE_CYCLES)
    return now - latest_ts <= tolerance


def load_pct(motor: Motor, reading: Reading | None) -> float | None:
    if reading is None or reading.current_avg_a is None or motor.rated_current_a <= 0:
        return None
    return reading.current_avg_a / motor.rated_current_a * 100.0


def alarms_in_range(db: Session, start: datetime, end: datetime) -> list[Alarm]:
    return list(
        db.scalars(
            select(Alarm)
            .where(Alarm.triggered_at >= start, Alarm.triggered_at < end)
            .order_by(Alarm.triggered_at.desc())
        ).all()
    )


def alarms_by_motor_from_list(alarms: list[Alarm]) -> dict[str, list[Alarm]]:
    grouped: dict[str, list[Alarm]] = {}
    for alarm in alarms:
        if alarm.motor_code:
            grouped.setdefault(alarm.motor_code, []).append(alarm)
    return grouped


def active_alarms(db: Session) -> list[Alarm]:
    return list(
        db.scalars(
            select(Alarm)
            .where(Alarm.status.in_(("open", "ack")))
            .order_by(Alarm.triggered_at.desc())
        ).all()
    )


def active_alarms_by_motor(db: Session) -> dict[str, list[Alarm]]:
    grouped: dict[str, list[Alarm]] = {}
    for alarm in active_alarms(db):
        if alarm.motor_code:
            grouped.setdefault(alarm.motor_code, []).append(alarm)
    return grouped


def motor_status(
    motor: Motor,
    latest: Reading | None,
    alarms: list[Alarm],
    now: datetime | None = None,
) -> str:
    if any(alarm.level == "crit" for alarm in alarms):
        return "crit"
    if any(alarm.level == "warn" for alarm in alarms):
        return "warn"
    if not is_online(latest, now):
        return "unknown"
    if latest is not None and latest.temperature_c is not None:
        if latest.temperature_c >= motor.temp_limit_c:
            return "crit"
    if (
        latest is not None
        and latest.current_avg_a is not None
        and motor.current_limit_a > 0
        and latest.current_avg_a >= motor.current_limit_a
    ):
        return "crit"
    return "ok"


def today_poll_stats(db: Session, start: datetime, end: datetime) -> dict:
    row = db.execute(
        select(
            func.coalesce(func.sum(PollCycle.attempts), 0),
            func.coalesce(func.sum(PollCycle.successes), 0),
            func.coalesce(func.sum(PollCycle.failures), 0),
            func.coalesce(func.avg(PollCycle.duration_ms), 0),
        ).where(PollCycle.started_at >= start, PollCycle.started_at < end)
    ).one()
    attempts, successes, failures, avg_duration = row
    attempts = int(attempts or 0)
    successes = int(successes or 0)
    failures = int(failures or 0)
    loss = (failures / attempts * 100.0) if attempts else 0.0
    availability = (successes / attempts * 100.0) if attempts else 100.0
    return {
        "attempts": attempts,
        "successes": successes,
        "failures": failures,
        "packets_today": successes,
        "packet_loss_pct": round(loss, 2),
        "link_availability_pct": round(availability, 2),
        "avg_latency_ms": round(float(avg_duration or 0), 1),
    }


def gateway_online(gateway: Gateway, now: datetime | None = None) -> bool:
    if not gateway.enabled:
        return False
    last_seen = as_utc(gateway.last_seen_at)
    now = as_utc(now or utcnow())
    if last_seen is None or now is None:
        return False
    tolerance = timedelta(minutes=settings.poll_interval_minutes * ONLINE_TOLERANCE_CYCLES)
    return now - last_seen <= tolerance


def sensor_online(sensor: Sensor, now: datetime | None = None) -> bool:
    if not sensor.enabled:
        return False
    last_read = as_utc(sensor.last_read_at)
    now = as_utc(now or utcnow())
    if last_read is None or now is None:
        return False
    tolerance = timedelta(minutes=settings.poll_interval_minutes * ONLINE_TOLERANCE_CYCLES)
    return now - last_read <= tolerance
