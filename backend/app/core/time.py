"""统一时间工具：数据库存 UTC，展示按配置时区。"""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def iso(value: datetime | None) -> str | None:
    value = as_utc(value)
    if value is None:
        return None
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def local_zone() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


def local_now() -> datetime:
    return utcnow().astimezone(local_zone())


def local_day_bounds_utc(day: date | None = None) -> tuple[datetime, datetime]:
    zone = local_zone()
    local_day = day or local_now().date()
    start = datetime.combine(local_day, time.min, tzinfo=zone)
    end = start + timedelta(days=1)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def floor_minute(value: datetime) -> datetime:
    return value.replace(second=0, microsecond=0)


def floor_bucket(value: datetime, minutes: int) -> datetime:
    value = as_utc(value)
    assert value is not None
    epoch_minutes = int(value.timestamp() // 60)
    return datetime.fromtimestamp((epoch_minutes // minutes) * minutes * 60, tz=timezone.utc)


def next_poll_time(now: datetime, interval_minutes: int) -> datetime:
    now = as_utc(now)
    assert now is not None
    epoch = int(now.timestamp())
    step = interval_minutes * 60
    return datetime.fromtimestamp(((epoch // step) + 1) * step, tz=timezone.utc)


def minutes_between(start: datetime | None, end: datetime | None) -> float | None:
    start = as_utc(start)
    end = as_utc(end)
    if start is None or end is None:
        return None
    return max(0.0, (end - start).total_seconds() / 60)
