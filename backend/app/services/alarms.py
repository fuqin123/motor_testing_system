"""告警判定、去重与自动闭环。"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import as_utc, utcnow
from app.db.models import Alarm, Motor, Reading, Sensor
from app.services.baseline import Baseline, deviation_pct
from app.services.settings import choose_owner

ACTIVE_STATUSES = ("open", "ack")


@dataclass
class AlarmCandidate:
    level: str
    rule_key: str
    title: str
    description: str
    metric: str
    value: float
    threshold: float
    unit: str
    advice: str


def evaluate_rules(
    motor: Motor,
    temperature_c: float | None,
    current_avg_a: float | None,
    baseline: Baseline | None,
    rise_rate_c_per_day: float | None,
) -> list[AlarmCandidate]:
    candidates: list[AlarmCandidate] = []

    if temperature_c is not None:
        if temperature_c >= motor.temp_limit_c:
            candidates.append(
                AlarmCandidate(
                    level="crit",
                    rule_key="temp_high",
                    title="外壳温度越限",
                    description=(
                        f"温度 {temperature_c:.1f}°C 超过上限 {motor.temp_limit_c:.1f}°C，"
                        "请立即核查散热、负载与轴承状态。"
                    ),
                    metric="temperature_c",
                    value=temperature_c,
                    threshold=motor.temp_limit_c,
                    unit="°C",
                    advice="优先检查风道散热、轴承润滑与端盖温升，安排红外测温复核。",
                )
            )
        elif baseline and baseline.temp_median:
            temp_dev = deviation_pct(temperature_c, baseline.temp_median)
            if temp_dev is not None and temp_dev >= motor.temp_deviation_pct:
                candidates.append(
                    AlarmCandidate(
                        level="warn",
                        rule_key="temp_deviation",
                        title="温度高于自身基线",
                        description=(
                            f"外壳温度较 {motor.code} 近 30 天正常基线偏高 {temp_dev:.1f}%，"
                            f"当前 {temperature_c:.1f}°C，基线 {baseline.temp_median:.1f}°C。"
                        ),
                        metric="temp_deviation_pct",
                        value=temp_dev,
                        threshold=motor.temp_deviation_pct,
                        unit="%",
                        advice="对比同类电机与环境温度，检查散热风道、滤网及润滑状态。",
                    )
                )

    if current_avg_a is not None and motor.current_limit_a > 0:
        if current_avg_a >= motor.current_limit_a:
            candidates.append(
                AlarmCandidate(
                    level="crit",
                    rule_key="current_high",
                    title="运行电流越限",
                    description=(
                        f"运行电流 {current_avg_a:.1f} A 超过上限 {motor.current_limit_a:.1f} A，"
                        "可能存在过载或电气异常。"
                    ),
                    metric="current_avg_a",
                    value=current_avg_a,
                    threshold=motor.current_limit_a,
                    unit="A",
                    advice="检查负载侧机械阻力、阀门开度与变频器输出平衡。",
                )
            )
        elif baseline and baseline.current_median:
            current_dev = deviation_pct(current_avg_a, baseline.current_median)
            if current_dev is not None and abs(current_dev) >= motor.current_deviation_pct:
                direction = "偏高" if current_dev > 0 else "偏低"
                candidates.append(
                    AlarmCandidate(
                        level="warn",
                        rule_key="current_deviation",
                        title="电流偏离自身基线",
                        description=(
                            f"运行电流较正常基线{direction} {abs(current_dev):.1f}%，"
                            f"当前 {current_avg_a:.1f} A，基线 {baseline.current_median:.1f} A。"
                        ),
                        metric="current_deviation_pct",
                        value=current_dev,
                        threshold=motor.current_deviation_pct,
                        unit="%",
                        advice="检查负载变化、变频器输出与三相电流平衡。",
                    )
                )

    if (
        rise_rate_c_per_day is not None
        and rise_rate_c_per_day >= motor.rise_rate_limit_c_per_day
        and motor.rise_rate_limit_c_per_day > 0
    ):
        candidates.append(
            AlarmCandidate(
                level="warn",
                rule_key="temp_rise",
                title="温度持续上升",
                description=(
                    f"近 {settings.rise_rate_days} 天温度呈单边上行，温升速率 {rise_rate_c_per_day:+.2f} °C/天，"
                    f"超过关注线 {motor.rise_rate_limit_c_per_day:.2f} °C/天。"
                ),
                metric="rise_rate_c_per_day",
                value=rise_rate_c_per_day,
                threshold=motor.rise_rate_limit_c_per_day,
                unit="°C/天",
                advice="持续温升多与机械或散热侧劣化相关，建议一周内安排检查。",
            )
        )

    return candidates


def _find_active_motor_alarm(db: Session, motor_code: str, rule_key: str) -> Alarm | None:
    return db.scalar(
        select(Alarm).where(
            Alarm.motor_code == motor_code,
            Alarm.rule_key == rule_key,
            Alarm.status.in_(ACTIVE_STATUSES),
        )
    )


def apply_reading_alarms(
    db: Session,
    motor: Motor,
    reading: Reading,
    candidates: list[AlarmCandidate],
    config: dict,
    now: datetime | None = None,
) -> list[Alarm]:
    now = as_utc(now or reading.ts or utcnow())
    assert now is not None
    active = db.scalars(
        select(Alarm).where(Alarm.motor_code == motor.code, Alarm.status.in_(ACTIVE_STATUSES))
    ).all()
    active_by_key = {alarm.rule_key: alarm for alarm in active}
    candidate_keys = {candidate.rule_key for candidate in candidates}
    new_alarms: list[Alarm] = []

    for candidate in candidates:
        existing = active_by_key.get(candidate.rule_key)
        if existing:
            existing.value = candidate.value
            existing.description = candidate.description
            existing.last_seen_at = now
            existing.normal_count = 0
            continue
        suppressed = db.scalar(
            select(Alarm)
            .where(
                Alarm.dedup_key == f"{motor.code}:{candidate.rule_key}",
                Alarm.suppressed_until.is_not(None),
                Alarm.suppressed_until > now,
            )
            .limit(1)
        )
        if suppressed:
            continue
        alarm = Alarm(
            level=candidate.level,
            rule_key=candidate.rule_key,
            title=candidate.title,
            description=candidate.description,
            advice=candidate.advice,
            motor_code=motor.code,
            motor_name=motor.name,
            device_code=motor.code,
            metric=candidate.metric,
            value=candidate.value,
            threshold=candidate.threshold,
            unit=candidate.unit,
            status="open",
            owner=choose_owner(candidate.rule_key, config),
            notification_status="pending" if motor.notify_enabled else "skipped",
            triggered_at=now,
            last_seen_at=now,
            normal_count=0,
            dedup_key=f"{motor.code}:{candidate.rule_key}",
        )
        db.add(alarm)
        db.flush()
        new_alarms.append(alarm)

    for rule_key, alarm in active_by_key.items():
        if rule_key in candidate_keys or alarm.level == "crit":
            continue
        alarm.normal_count += 1
        if alarm.normal_count >= 2:
            alarm.status = "closed"
            alarm.closed_at = now
            alarm.closed_by = "system"
            alarm.solution = "指标连续 2 个采集周期恢复正常，系统自动闭环。"

    return new_alarms


def ensure_device_alarm(
    db: Session,
    *,
    level: str,
    rule_key: str,
    title: str,
    description: str,
    device_code: str,
    motor: Motor | None,
    config: dict,
    advice: str = "",
    now: datetime | None = None,
) -> Alarm | None:
    now = as_utc(now or utcnow())
    assert now is not None
    existing = db.scalar(
        select(Alarm).where(
            Alarm.device_code == device_code,
            Alarm.rule_key == rule_key,
            Alarm.status.in_(ACTIVE_STATUSES),
        )
    )
    if existing:
        existing.description = description
        existing.last_seen_at = now
        return None
    suppressed = db.scalar(
        select(Alarm)
        .where(
            Alarm.dedup_key == f"{device_code}:{rule_key}",
            Alarm.suppressed_until.is_not(None),
            Alarm.suppressed_until > now,
        )
        .limit(1)
    )
    if suppressed:
        return None
    alarm = Alarm(
        level=level,
        rule_key=rule_key,
        title=title,
        description=description,
        advice=advice,
        motor_code=motor.code if motor else None,
        motor_name=motor.name if motor else None,
        device_code=device_code,
        metric="link",
        status="open",
        owner=choose_owner(rule_key, config),
        notification_status="pending",
        triggered_at=now,
        last_seen_at=now,
        normal_count=0,
        dedup_key=f"{device_code}:{rule_key}",
    )
    db.add(alarm)
    db.flush()
    return alarm


def resolve_device_alarm(
    db: Session,
    device_code: str,
    rule_key: str,
    solution: str,
    now: datetime | None = None,
) -> None:
    now = as_utc(now or utcnow())
    alarm = db.scalar(
        select(Alarm).where(
            Alarm.device_code == device_code,
            Alarm.rule_key == rule_key,
            Alarm.status.in_(ACTIVE_STATUSES),
        )
    )
    if alarm:
        alarm.status = "closed"
        alarm.closed_at = now
        alarm.closed_by = "system"
        alarm.solution = solution


def handle_sensor_result(
    db: Session,
    sensor: Sensor,
    success: bool,
    error: str | None,
    config: dict,
    now: datetime | None = None,
) -> Alarm | None:
    now = as_utc(now or utcnow())
    assert now is not None
    if success:
        sensor.last_read_at = now
        sensor.last_error = None
        sensor.consecutive_failures = 0
        resolve_device_alarm(db, sensor.code, "sensor_error", "通信恢复，系统自动闭环。", now=now)
        return None
    sensor.consecutive_failures += 1
    sensor.last_error = (error or "读取失败")[:255]
    if sensor.consecutive_failures >= 3:
        return ensure_device_alarm(
            db,
            level="warn",
            rule_key="sensor_error",
            title="采集传感器通信异常",
            description=(
                f"{sensor.code}（{sensor.name}）已连续 {sensor.consecutive_failures} 个周期读取失败："
                f"{sensor.last_error}"
            ),
            device_code=sensor.code,
            motor=sensor.motor,
            config=config,
            advice="检查传感器供电、RS485 接线与从站地址，确认网关透传配置。",
            now=now,
        )
    return None


def handle_gateway_result(
    db: Session,
    gateway,
    success: bool,
    error: str | None,
    config: dict,
    now: datetime | None = None,
) -> Alarm | None:
    now = as_utc(now or utcnow())
    assert now is not None
    if success:
        gateway.last_seen_at = now
        gateway.last_error = None
        gateway.consecutive_failures = 0
        resolve_device_alarm(
            db, gateway.code, "gateway_offline", "网关通信恢复，系统自动闭环。", now=now
        )
        return None
    gateway.consecutive_failures += 1
    gateway.last_error = (error or "连接失败")[:255]
    if gateway.consecutive_failures >= 2:
        return ensure_device_alarm(
            db,
            level="warn",
            rule_key="gateway_offline",
            title="LoRa 网关离线",
            description=(
                f"{gateway.code} 已连续 {gateway.consecutive_failures} 个周期连接失败："
                f"{gateway.last_error}"
            ),
            device_code=gateway.code,
            motor=None,
            config=config,
            advice="检查网关供电、网口上联与 Modbus TCP 端口，确认现场网络可达。",
            now=now,
        )
    return None
