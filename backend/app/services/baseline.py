"""历史正常基线与分时带计算。"""

import math
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import as_utc, local_zone, utcnow
from app.db.models import Motor, Reading


@dataclass
class Baseline:
    temp_median: float | None
    temp_p10: float | None
    temp_p90: float | None
    current_median: float | None
    current_p10: float | None
    current_p90: float | None
    sample_count: int
    temp_profile: dict[int, tuple[float, float]]

    def to_dict(self) -> dict:
        return {
            "temp_median": round(self.temp_median, 2) if self.temp_median is not None else None,
            "temp_p10": round(self.temp_p10, 2) if self.temp_p10 is not None else None,
            "temp_p90": round(self.temp_p90, 2) if self.temp_p90 is not None else None,
            "current_median": (
                round(self.current_median, 2) if self.current_median is not None else None
            ),
            "current_p10": round(self.current_p10, 2) if self.current_p10 is not None else None,
            "current_p90": round(self.current_p90, 2) if self.current_p90 is not None else None,
            "sample_count": self.sample_count,
        }


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def deviation_pct(value: float | None, baseline: float | None) -> float | None:
    if value is None or baseline is None or baseline == 0:
        return None
    return (value - baseline) / baseline * 100.0


_cache: dict[tuple[int, int], tuple[datetime, Baseline]] = {}
_cache_lock = threading.Lock()


def clear_baseline_cache() -> None:
    with _cache_lock:
        _cache.clear()


def compute_baseline(
    db: Session,
    motor: Motor,
    now: datetime | None = None,
    days: int | None = None,
    use_cache: bool = True,
) -> Baseline | None:
    now = as_utc(now or utcnow())
    assert now is not None
    cache_key = (motor.id, int(now.timestamp() // 3600))
    if use_cache:
        with _cache_lock:
            cached = _cache.get(cache_key)
            if cached and (now - cached[0]).total_seconds() < settings.baseline_cache_minutes * 60:
                return cached[1]

    since = now - timedelta(days=days or settings.baseline_days)
    rows = db.execute(
        select(Reading.ts, Reading.temperature_c, Reading.current_avg_a).where(
            Reading.motor_id == motor.id,
            Reading.ts >= since,
            Reading.ts <= now,
            Reading.quality != "error",
        )
    ).all()

    temps: list[float] = []
    currents: list[float] = []
    hourly: dict[int, list[float]] = {}
    zone = local_zone()
    for ts, temp, current in rows:
        local_ts = as_utc(ts)
        if temp is not None and temp < motor.temp_limit_c:
            temps.append(temp)
            assert local_ts is not None
            hour = local_ts.astimezone(zone).hour
            hourly.setdefault(hour // 2, []).append(temp)
        if current is not None and (motor.current_limit_a <= 0 or current < motor.current_limit_a):
            currents.append(current)

    if len(temps) < 10 and len(currents) < 10:
        return None

    temp_profile: dict[int, tuple[float, float]] = {}
    for bucket, values in hourly.items():
        if len(values) >= 5:
            lo = percentile(values, 0.10)
            hi = percentile(values, 0.90)
            if lo is not None and hi is not None:
                temp_profile[bucket] = (lo, hi)

    baseline = Baseline(
        temp_median=percentile(temps, 0.50),
        temp_p10=percentile(temps, 0.10),
        temp_p90=percentile(temps, 0.90),
        current_median=percentile(currents, 0.50),
        current_p10=percentile(currents, 0.10),
        current_p90=percentile(currents, 0.90),
        sample_count=max(len(temps), len(currents)),
        temp_profile=temp_profile,
    )
    if use_cache:
        with _cache_lock:
            _cache[cache_key] = (now, baseline)
    return baseline


def band_values(ts: datetime, baseline: Baseline) -> tuple[float | None, float | None]:
    local_ts = as_utc(ts)
    if local_ts is None or not baseline.temp_profile:
        return baseline.temp_p10, baseline.temp_p90
    bucket = local_ts.astimezone(local_zone()).hour // 2
    profile = baseline.temp_profile.get(bucket)
    if profile:
        return profile
    return baseline.temp_p10, baseline.temp_p90
