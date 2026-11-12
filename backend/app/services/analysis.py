"""趋势、基线对比、同类对比与四象限分析。"""

from datetime import datetime, timedelta
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import as_utc, floor_bucket, iso, local_zone, utcnow
from app.db.models import Alarm, Motor, Reading
from app.services.baseline import Baseline, band_values, compute_baseline, deviation_pct
from app.services.telemetry import latest_readings, load_pct, motor_status, series_readings

RANGE_CONFIG = {
    "24h": {"hours": 24, "bucket_minutes": 15, "days": 1},
    "7d": {"hours": 24 * 7, "bucket_minutes": 60, "days": 7},
    "30d": {"hours": 24 * 30, "bucket_minutes": 360, "days": 30},
}


def normalize_range(value: str | None) -> str:
    return value if value in RANGE_CONFIG else "24h"


def bucket_readings(readings: list[Reading], bucket_minutes: int) -> list[dict]:
    groups: dict[datetime, list[Reading]] = {}
    for reading in readings:
        ts = as_utc(reading.ts)
        if ts is None:
            continue
        groups.setdefault(floor_bucket(ts, bucket_minutes), []).append(reading)
    points: list[dict] = []
    for ts in sorted(groups):
        items = groups[ts]
        temps = [item.temperature_c for item in items if item.temperature_c is not None]
        currents = [item.current_avg_a for item in items if item.current_avg_a is not None]
        phase_a = [item.current_a for item in items if item.current_a is not None]
        phase_b = [item.current_b for item in items if item.current_b is not None]
        phase_c = [item.current_c for item in items if item.current_c is not None]
        if not temps and not currents:
            continue
        points.append(
            {
                "ts": iso(ts),
                "temperature_c": round(mean(temps), 2) if temps else None,
                "current_avg_a": round(mean(currents), 2) if currents else None,
                "current_a": round(mean(phase_a), 2) if phase_a else None,
                "current_b": round(mean(phase_b), 2) if phase_b else None,
                "current_c": round(mean(phase_c), 2) if phase_c else None,
            }
        )
    return points


def build_series(
    db: Session, motor: Motor, range_key: str, now: datetime | None = None
) -> list[dict]:
    config = RANGE_CONFIG[range_key]
    now = as_utc(now or utcnow())
    assert now is not None
    readings = series_readings(db, motor.id, now - timedelta(hours=config["hours"]), now)
    return bucket_readings(readings, config["bucket_minutes"])


def daily_slope(readings: list[Reading], min_days: int = 2) -> tuple[float | None, int]:
    daily: dict[str, list[float]] = {}
    zone = local_zone()
    for reading in readings:
        if reading.temperature_c is None or reading.quality == "error":
            continue
        ts = as_utc(reading.ts)
        if ts is None:
            continue
        key = ts.astimezone(zone).date().isoformat()
        daily.setdefault(key, []).append(reading.temperature_c)
    if len(daily) < min_days:
        return None, len(daily)
    points = [
        (index, mean(values)) for index, values in enumerate((daily[key] for key in sorted(daily)))
    ]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    x_mean = mean(xs)
    y_mean = mean(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator == 0:
        return 0.0, len(daily)
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denominator
    return slope, len(daily)


def latest_reading(readings: list[Reading]) -> Reading | None:
    valid = [
        item
        for item in readings
        if item.temperature_c is not None or item.current_avg_a is not None
    ]
    if not valid:
        return None
    return max(valid, key=lambda item: as_utc(item.ts) or utcnow())


def motor_summary(motor: Motor) -> dict:
    sensor_text = " / ".join(
        f"{sensor.code} {sensor.name}".strip() for sensor in motor.sensors if sensor.enabled
    )
    return {
        "code": motor.code,
        "name": motor.name,
        "location": motor.location,
        "group": motor.group_name,
        "rated_kw": motor.rated_kw,
        "rated_current_a": motor.rated_current_a,
        "temp_limit_c": motor.temp_limit_c,
        "current_limit_a": motor.current_limit_a,
        "pilot": motor.pilot,
        "enabled": motor.enabled,
        "node_code": motor.node_code,
        "vfd_model": motor.vfd_model,
        "install_date": motor.install_date,
        "last_maintenance": motor.last_maintenance,
        "sensors": sensor_text,
    }


def reading_payload(motor: Motor, reading: Reading | None) -> dict:
    if reading is None:
        return {
            "temperature_c": None,
            "current_avg_a": None,
            "current_a": None,
            "current_b": None,
            "current_c": None,
            "load_pct": None,
            "quality": None,
            "ts": None,
        }
    return {
        "temperature_c": reading.temperature_c,
        "current_avg_a": reading.current_avg_a,
        "current_a": reading.current_a,
        "current_b": reading.current_b,
        "current_c": reading.current_c,
        "load_pct": load_pct(motor, reading),
        "quality": reading.quality,
        "ts": iso(reading.ts),
    }


def verdict_payload(
    temp_deviation: float | None,
    current_deviation: float | None,
    motor: Motor,
) -> dict:
    temp_hit = temp_deviation is not None and temp_deviation >= motor.temp_deviation_pct
    current_hit = (
        current_deviation is not None and abs(current_deviation) >= motor.current_deviation_pct
    )
    if temp_hit and current_hit:
        return {
            "key": "both",
            "text": "双高 · 过载或综合劣化",
            "advice": "温度电流同时偏高：立即核查负载与机械状态，必要时降载运行并安排停机检查。",
        }
    if temp_hit:
        return {
            "key": "temp",
            "text": "温度高 / 电流正常 · 散热、轴承或润滑方向",
            "advice": "电流正常但温度升高：优先检查风道散热、轴承润滑与端盖温升，建议红外测温复核。",
        }
    if current_hit:
        direction = "偏高" if (current_deviation or 0) > 0 else "偏低"
        return {
            "key": "current",
            "text": f"温度正常 / 电流{direction} · 负载或电气方向",
            "advice": "温度正常但电流异常：检查负载侧阻力、阀门开度、变频器输出与三相平衡。",
        }
    return {
        "key": "ok",
        "text": "双正常 · 运行健康",
        "advice": "各项指标在正常基线内，保持 15 分钟采集与例行巡检即可。",
    }


def build_self_analysis(
    db: Session, motor: Motor, range_key: str = "30d", now: datetime | None = None
) -> dict:
    range_key = normalize_range(range_key)
    if range_key == "24h":
        range_key = "30d"
    now = as_utc(now or utcnow())
    assert now is not None
    series = build_series(db, motor, range_key, now)
    readings = series_readings(
        db, motor.id, now - timedelta(days=RANGE_CONFIG[range_key]["days"]), now
    )
    latest = latest_reading(readings)
    baseline = compute_baseline(db, motor, now=now)
    temp_dev = (
        deviation_pct(latest.temperature_c, baseline.temp_median) if latest and baseline else None
    )
    current_dev = (
        deviation_pct(latest.current_avg_a, baseline.current_median)
        if latest and baseline
        else None
    )
    band: list[dict] = []
    if baseline:
        for point in series:
            ts = datetime.fromisoformat(str(point["ts"]).replace("Z", "+00:00"))
            lo, hi = band_values(ts, baseline)
            band.append(
                {
                    "ts": point["ts"],
                    "lo": round(lo, 2) if lo is not None else None,
                    "hi": round(hi, 2) if hi is not None else None,
                }
            )
    rise_readings = series_readings(db, motor.id, now - timedelta(days=7), now)
    slope, slope_days = daily_slope(rise_readings, min_days=3)
    rules = [
        {
            "key": "temp_deviation",
            "label": f"高于自身基线 {motor.temp_deviation_pct:.1f}%",
            "hit": temp_dev is not None and temp_dev >= motor.temp_deviation_pct,
            "detail": (
                f"当前偏离 {temp_dev:+.1f}%" if temp_dev is not None else "正常基线样本不足"
            ),
        },
        {
            "key": "temp_high",
            "label": f"超过温度上限 {motor.temp_limit_c:.0f}°C",
            "hit": latest is not None
            and latest.temperature_c is not None
            and latest.temperature_c >= motor.temp_limit_c,
            "detail": (
                f"{latest.temperature_c:.1f}°C / 上限 {motor.temp_limit_c:.1f}°C"
                if latest and latest.temperature_c is not None
                else "暂无温度读数"
            ),
        },
        {
            "key": "temp_rise",
            "label": f"温升速率超过 {motor.rise_rate_limit_c_per_day:.1f}°C/天",
            "hit": slope is not None and slope >= motor.rise_rate_limit_c_per_day,
            "detail": (
                f"近 7 天 {slope:+.2f}°C/天 · {slope_days} 天样本"
                if slope is not None
                else f"有效样本仅 {slope_days} 天"
            ),
        },
        {
            "key": "current_deviation",
            "label": f"电流偏离基线 {motor.current_deviation_pct:.1f}%",
            "hit": current_dev is not None and abs(current_dev) >= motor.current_deviation_pct,
            "detail": (
                f"当前偏离 {current_dev:+.1f}%" if current_dev is not None else "正常基线样本不足"
            ),
        },
    ]
    verdict = verdict_payload(temp_dev, current_dev, motor)
    return {
        "motor": motor_summary(motor),
        "range": range_key,
        "series": series,
        "band": band,
        "baseline": baseline.to_dict() if baseline else None,
        "latest": reading_payload(motor, latest),
        "deviation": {
            "temp_pct": round(temp_dev, 2) if temp_dev is not None else None,
            "current_pct": round(current_dev, 2) if current_dev is not None else None,
        },
        "rise_rate_c_per_day": round(slope, 3) if slope is not None else None,
        "rules": rules,
        "verdict": verdict,
    }


def _motor_metric(
    db: Session, motor: Motor, latest: Reading | None, baseline: Baseline | None
) -> dict:
    temp_dev = (
        deviation_pct(latest.temperature_c, baseline.temp_median) if latest and baseline else None
    )
    current_dev = (
        deviation_pct(latest.current_avg_a, baseline.current_median)
        if latest and baseline
        else None
    )
    status = "unknown"
    if latest is not None:
        status = "ok"
        if latest.temperature_c is not None and latest.temperature_c >= motor.temp_limit_c:
            status = "crit"
        elif (
            latest.current_avg_a is not None
            and motor.current_limit_a > 0
            and latest.current_avg_a >= motor.current_limit_a
        ):
            status = "crit"
        elif temp_dev is not None and temp_dev >= motor.temp_deviation_pct:
            status = "warn"
        elif current_dev is not None and abs(current_dev) >= motor.current_deviation_pct:
            status = "warn"
    return {
        "code": motor.code,
        "name": motor.name,
        "status": status,
        "temperature_c": latest.temperature_c if latest else None,
        "current_avg_a": latest.current_avg_a if latest else None,
        "load_pct": load_pct(motor, latest),
        "temp_deviation_pct": round(temp_dev, 2) if temp_dev is not None else None,
        "current_deviation_pct": round(current_dev, 2) if current_dev is not None else None,
        "score": round(max(0.0, temp_dev or 0.0) * 0.6 + max(0.0, current_dev or 0.0) * 0.4, 2),
    }


def build_peer_analysis(db: Session, group: str | None = None, now: datetime | None = None) -> dict:
    motors = list(
        db.scalars(select(Motor).where(Motor.enabled.is_(True)).order_by(Motor.code)).all()
    )
    groups = sorted({motor.group_name for motor in motors})
    selected_group = group if group in groups else (groups[0] if groups else "")
    selected = [motor for motor in motors if motor.group_name == selected_group]
    latest_map = latest_readings(db, [motor.id for motor in selected], until=now)
    items = []
    for motor in selected:
        baseline = compute_baseline(db, motor, now=now)
        items.append(_motor_metric(db, motor, latest_map.get(motor.id), baseline))
    ranking = sorted(items, key=lambda item: item["score"], reverse=True)
    for index, item in enumerate(ranking, start=1):
        item["rank"] = index
    worst = ranking[0] if ranking else None
    if worst and worst["score"] > 8:
        insight = (
            f"{worst['code']} {worst['name']} 在同类组中偏离最明显（得分 {worst['score']:.1f}），"
            "显著高于同功率同工况电机，建议优先排查。"
        )
    elif worst:
        insight = f"组内电机指标接近，无明显离群电机，{worst['code']} 略高但在正常波动范围内。"
    else:
        insight = "当前分组暂无可用读数，请检查采集链路或点表配置。"
    return {
        "group": selected_group,
        "groups": groups,
        "motors": items,
        "ranking": ranking,
        "insight": insight,
    }


def build_quadrant(db: Session, now: datetime | None = None) -> dict:
    motors = list(
        db.scalars(select(Motor).where(Motor.enabled.is_(True)).order_by(Motor.code)).all()
    )
    latest_map = latest_readings(db, [motor.id for motor in motors], until=now)
    points = []
    for motor in motors:
        latest = latest_map.get(motor.id)
        if latest is None:
            continue
        baseline = compute_baseline(db, motor, now=now)
        if baseline is None:
            continue
        temp_dev = deviation_pct(latest.temperature_c, baseline.temp_median)
        current_dev = deviation_pct(latest.current_avg_a, baseline.current_median)
        if temp_dev is None or current_dev is None:
            continue
        metric = _motor_metric(db, motor, latest, baseline)
        points.append(
            {
                "code": motor.code,
                "name": motor.name,
                "temp_deviation_pct": round(temp_dev, 2),
                "current_deviation_pct": round(current_dev, 2),
                "status": metric["status"],
            }
        )
    return {
        "points": points,
        "thresholds": {"temp_pct": 8.0, "current_pct": 10.0},
    }


def build_trend(
    db: Session, motor: Motor, range_key: str = "7d", now: datetime | None = None
) -> dict:
    range_key = normalize_range(range_key)
    now = as_utc(now or utcnow())
    assert now is not None
    series = build_series(db, motor, range_key, now)
    readings = series_readings(
        db, motor.id, now - timedelta(days=RANGE_CONFIG[range_key]["days"]), now
    )
    temps = [item.temperature_c for item in readings if item.temperature_c is not None]
    slope, slope_days = daily_slope(readings, min_days=3)
    stats = {
        "max_temp_c": round(max(temps), 2) if temps else None,
        "min_temp_c": round(min(temps), 2) if temps else None,
        "avg_temp_c": round(mean(temps), 2) if temps else None,
        "slope_c_per_day": round(slope, 3) if slope is not None else None,
        "sample_days": slope_days,
    }
    if slope is None or not temps:
        verdict = {
            "bad": False,
            "tag": "数据不足",
            "text": f"{motor.code} 有效历史样本不足 3 天，暂时无法判断趋势，请保持连续采集。",
        }
    elif slope >= motor.rise_rate_limit_c_per_day:
        verdict = {
            "bad": True,
            "tag": "持续恶化",
            "text": (
                f"{motor.code} 近 {RANGE_CONFIG[range_key]['days']} 天温度单边上行"
                f"（{slope:+.2f}°C/天），非偶发波动，建议本周内安排检查。"
            ),
        }
    elif slope > motor.rise_rate_limit_c_per_day * 0.5:
        verdict = {
            "bad": False,
            "tag": "缓慢上升 · 需关注",
            "text": (
                f"{motor.code} 温升速率 {slope:+.2f}°C/天，处于缓慢上升区间，建议持续观察一周。"
            ),
        }
    else:
        verdict = {
            "bad": False,
            "tag": "走势平稳 · 偶发波动",
            "text": f"{motor.code} 温升速率 {slope:+.2f}°C/天，属于正常工况波动，无需干预。",
        }
    alarm_rows = db.scalars(
        select(Alarm)
        .where(
            Alarm.motor_code == motor.code,
            Alarm.triggered_at >= now - timedelta(days=RANGE_CONFIG[range_key]["days"]),
            Alarm.triggered_at <= now,
        )
        .order_by(Alarm.triggered_at.asc())
    ).all()
    events = [
        {
            "id": f"AL-{alarm.id:04d}",
            "level": alarm.level,
            "title": alarm.title,
            "ts": iso(alarm.triggered_at),
            "status": alarm.status,
        }
        for alarm in alarm_rows
    ]
    return {
        "motor": motor_summary(motor),
        "range": range_key,
        "series": series,
        "stats": stats,
        "verdict": verdict,
        "events": events,
    }


def build_motor_status_map(
    db: Session, motors: list[Motor], now: datetime | None = None
) -> dict[int, str]:
    latest_map = latest_readings(db, [motor.id for motor in motors], until=now)
    from app.services.telemetry import active_alarms_by_motor

    alarm_map = active_alarms_by_motor(db)
    return {
        motor.id: motor_status(motor, latest_map.get(motor.id), alarm_map.get(motor.code, []), now)
        for motor in motors
    }
