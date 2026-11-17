"""告警判定、去重与自动闭环。"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import as_utc, utcnow
from app.db.models import Alarm, AlarmStreak, Motor, Reading, Sensor
from app.services.baseline import Baseline, deviation_pct
from app.services.settings import choose_owner
from app.services.telemetry import OPERATING_STATE_TEXT, classify_operating_state

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
    current_a: float | None = None,
    current_b: float | None = None,
    current_c: float | None = None,
    vibration_total_mm_s: float | None = None,
    vibration_x: float | None = None,
    vibration_y: float | None = None,
    vibration_z: float | None = None,
    operating_state: str | None = None,
    previous_state: str | None = None,
) -> list[AlarmCandidate]:
    candidates: list[AlarmCandidate] = []
    state = operating_state or classify_operating_state(motor, current_avg_a)
    state_text = OPERATING_STATE_TEXT.get(state, "未知")
    state_changed = bool(
        previous_state
        and previous_state != "unknown"
        and state != "unknown"
        and previous_state != state
    )

    def state_ref(metric: str) -> float | None:
        value = float(getattr(motor, f"state_{state}_{metric}", 0.0) or 0.0)
        return value if value > 0 else None

    def ref_or_baseline(metric: str, baseline_value: float | None) -> float | None:
        ref = state_ref(metric)
        if ref is not None:
            return ref
        return baseline_value if state in ("running", "unknown") else None

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
        elif not state_changed:
            notify_base = float(getattr(motor, "temp_notify_base_c", 0.0) or 0.0)
            if notify_base > 0 and temperature_c < notify_base:
                temp_ref = None
            else:
                temp_ref = ref_or_baseline("temp_c", baseline.temp_median if baseline else None)
            temp_dev = deviation_pct(temperature_c, temp_ref)
            if temp_dev is not None and temp_dev >= motor.temp_deviation_pct:
                ref_label = (
                    f"{state_text}状态正常值"
                    if state_ref("temp_c") is not None
                    else "近 30 天正常基线"
                )
                candidates.append(
                    AlarmCandidate(
                        level="warn",
                        rule_key="temp_deviation",
                        title=f"温度高于{state_text}状态基准",
                        description=(
                            f"外壳温度较 {motor.code} {ref_label}偏高 {temp_dev:.1f}%，"
                            f"当前 {temperature_c:.1f}°C，基准 {temp_ref:.1f}°C。"
                        ),
                        metric="temp_deviation_pct",
                        value=temp_dev,
                        threshold=motor.temp_deviation_pct,
                        unit="%",
                        advice="对比同类电机与环境温度，检查散热风道、滤网及润滑状态。",
                    )
                )

    phases = [value for value in (current_a, current_b, current_c) if value is not None]
    peak_current = max(phases) if phases else current_avg_a
    if peak_current is not None and motor.current_limit_a > 0:
        if peak_current >= motor.current_limit_a:
            if not state_changed:
                if len(phases) == 3:
                    phase_text = (
                        f"三相电流 A/B/C = {current_a:.1f} / {current_b:.1f} / {current_c:.1f} A"
                    )
                    title = "三相电流越限"
                else:
                    phase_text = f"运行电流 {peak_current:.1f} A"
                    title = "运行电流越限"
                candidates.append(
                    AlarmCandidate(
                        level="crit",
                        rule_key="current_high",
                        title=title,
                        description=(
                            f"{phase_text}，最高相超过上限 {motor.current_limit_a:.1f} A，"
                            "可能存在过载或单相电气异常。"
                        ),
                        metric="current_phase_max_a" if len(phases) == 3 else "current_avg_a",
                        value=peak_current,
                        threshold=motor.current_limit_a,
                        unit="A",
                        advice="检查三相负载平衡、接线端子、变频器输出与机械阻力。",
                    )
                )
        elif not state_changed and current_avg_a is not None:
            current_ref = ref_or_baseline(
                "current_a", baseline.current_median if baseline else None
            )
            current_dev = deviation_pct(current_avg_a, current_ref)
            if current_dev is not None and abs(current_dev) >= motor.current_deviation_pct:
                direction = "偏高" if current_dev > 0 else "偏低"
                ref_label = (
                    f"{state_text}状态正常值"
                    if state_ref("current_a") is not None
                    else "近 30 天正常基线"
                )
                candidates.append(
                    AlarmCandidate(
                        level="warn",
                        rule_key="current_deviation",
                        title=f"电流偏离{state_text}状态基准",
                        description=(
                            f"运行电流较 {motor.code} {ref_label}{direction} "
                            f"{abs(current_dev):.1f}%，当前 {current_avg_a:.1f} A，"
                            f"基准 {current_ref:.1f} A。"
                        ),
                        metric="current_deviation_pct",
                        value=current_dev,
                        threshold=motor.current_deviation_pct,
                        unit="%",
                        advice="检查负载变化、变频器输出与三相电流平衡。",
                    )
                )

    if (
        len(phases) == 3
        and motor.phase_imbalance_pct > 0
        and state == "running"
        and not state_changed
    ):
        phase_mean = sum(phases) / 3
        if phase_mean > 0:
            imbalance = (max(phases) - min(phases)) / phase_mean * 100
            if imbalance >= motor.phase_imbalance_pct:
                level = "crit" if imbalance >= motor.phase_imbalance_pct * 2 else "warn"
                candidates.append(
                    AlarmCandidate(
                        level=level,
                        rule_key="current_imbalance",
                        title="三相电流不平衡",
                        description=(
                            f"三相电流 A/B/C = {current_a:.1f} / {current_b:.1f} / {current_c:.1f} A，"
                            f"不平衡度 {imbalance:.1f}% 超过阈值 {motor.phase_imbalance_pct:.1f}%。"
                        ),
                        metric="current_imbalance_pct",
                        value=imbalance,
                        threshold=motor.phase_imbalance_pct,
                        unit="%",
                        advice="检查三相接线、接触器触点、负载分配与变频器输出平衡。",
                    )
                )

    if (
        vibration_total_mm_s is not None
        and motor.vibration_limit_mm_s > 0
        and vibration_total_mm_s >= motor.vibration_limit_mm_s
        and not state_changed
    ):
        axis_text = ""
        if vibration_x is not None and vibration_y is not None and vibration_z is not None:
            axis_text = (
                f"（X/Y/Z = {vibration_x:.2f} / {vibration_y:.2f} / {vibration_z:.2f} mm/s）"
            )
        candidates.append(
            AlarmCandidate(
                level="crit",
                rule_key="vibration_high",
                title="振动速度越限",
                description=(
                    f"振动速度总值 {vibration_total_mm_s:.2f} mm/s 超过上限 "
                    f"{motor.vibration_limit_mm_s:.2f} mm/s{axis_text}，"
                    "可能存在轴承磨损、不平衡或联轴器问题。"
                ),
                metric="vibration_total_mm_s",
                value=vibration_total_mm_s,
                threshold=motor.vibration_limit_mm_s,
                unit="mm/s",
                advice="检查轴承、联轴器、地脚螺栓与转子平衡，建议安排振动复测。",
            )
        )

    vibe_ref = state_ref("vibration_mm_s")
    if vibration_total_mm_s is not None and vibe_ref is not None and not state_changed:
        vibe_dev = deviation_pct(vibration_total_mm_s, vibe_ref)
        if vibe_dev is not None and vibe_dev >= motor.vibration_deviation_pct:
            candidates.append(
                AlarmCandidate(
                    level="warn",
                    rule_key="vibration_deviation",
                    title=f"振动高于{state_text}状态基准",
                    description=(
                        f"振动速度总值 {vibration_total_mm_s:.2f} mm/s，较 {motor.code} "
                        f"{state_text}状态正常值 {vibe_ref:.2f} mm/s 偏高 {vibe_dev:.1f}%。"
                    ),
                    metric="vibration_deviation_pct",
                    value=vibe_dev,
                    threshold=motor.vibration_deviation_pct,
                    unit="%",
                    advice="结合运行状态复核轴承、联轴器与转子平衡，排除状态切换瞬间波动。",
                )
            )

    return candidates


def _required_confirm_count(motor: Motor, rule_key: str) -> int:
    if rule_key in ("temp_high", "temp_deviation"):
        return max(1, int(getattr(motor, "temp_confirm_count", 1) or 1))
    if rule_key in ("current_high", "current_deviation", "current_imbalance"):
        return max(1, int(getattr(motor, "current_confirm_count", 1) or 1))
    return 1


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
    streaks = {
        row.rule_key: row
        for row in db.scalars(
            select(AlarmStreak).where(AlarmStreak.motor_id == motor.id)
        ).all()
    }
    for rule_key, streak in list(streaks.items()):
        if rule_key not in candidate_keys:
            db.delete(streak)
            streaks.pop(rule_key, None)

    for candidate in candidates:
        existing = active_by_key.get(candidate.rule_key)
        if existing:
            existing.value = candidate.value
            existing.description = candidate.description
            existing.last_seen_at = now
            existing.normal_count = 0
            streak = streaks.pop(candidate.rule_key, None)
            if streak is not None:
                db.delete(streak)
            continue

        required = _required_confirm_count(motor, candidate.rule_key)
        streak = streaks.get(candidate.rule_key)
        if required > 1:
            if streak is None:
                streak = AlarmStreak(
                    motor_id=motor.id, rule_key=candidate.rule_key, count=0
                )
                db.add(streak)
                streaks[candidate.rule_key] = streak
            last_ts = as_utc(streak.last_ts)
            if last_ts is None:
                streak.count = 1
            elif last_ts < now:
                interval_seconds = max(60, settings.poll_interval_minutes * 60)
                if now - last_ts > timedelta(seconds=interval_seconds * 1.5):
                    streak.count = 1
                else:
                    streak.count += 1
            streak.last_ts = now
            if streak.count < required:
                db.flush()
                continue
            db.delete(streak)
            streaks.pop(candidate.rule_key, None)
        elif streak is not None:
            db.delete(streak)
            streaks.pop(candidate.rule_key, None)

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
