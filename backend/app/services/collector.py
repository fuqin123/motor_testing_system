"""采集调度器：单线程顺序采集，支持多网关与模拟模式。"""

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select

from app.core.config import settings
from app.core.time import as_utc, floor_bucket, iso, next_poll_time, utcnow
from app.db.models import (
    AlarmStreak,
    Gateway,
    Motor,
    PacketLoss,
    PacketLossAttempt,
    PollCycle,
    Reading,
    Sensor,
)
from app.db.session import SessionLocal
from app.services.alarms import (
    CONFIRM_RULE_KEYS,
    apply_reading_alarms,
    evaluate_rules,
    handle_gateway_result,
    handle_sensor_result,
)
from app.services.baseline import compute_baseline
from app.services.feishu import notify_alarm
from app.services.modbus import GatewayPlan, GatewayReadResult, SensorPlan, read_gateway
from app.services.settings import get_notification_config, get_sampling_config
from app.services.simulator import simulate_gateway
from app.services.telemetry import classify_operating_state, latest_readings

logger = logging.getLogger(__name__)


@dataclass
class CycleSummary:
    started_at: datetime
    finished_at: datetime
    gateways: int
    attempts: int
    successes: int
    failures: int
    new_alarms: int
    duration_ms: int

    def to_dict(self) -> dict:
        return {
            "started_at": iso(self.started_at),
            "finished_at": iso(self.finished_at),
            "gateways": self.gateways,
            "attempts": self.attempts,
            "successes": self.successes,
            "failures": self.failures,
            "new_alarms": self.new_alarms,
            "duration_ms": self.duration_ms,
        }


def load_gateway_plans(db, motor_ids: set[int] | None = None) -> list[GatewayPlan]:
    gateways = list(
        db.scalars(select(Gateway).where(Gateway.enabled.is_(True)).order_by(Gateway.code)).all()
    )
    if not gateways:
        return []
    plans = {
        gateway.id: GatewayPlan(
            id=gateway.id,
            code=gateway.code,
            host=gateway.host,
            port=gateway.port,
            framer=gateway.framer,
        )
        for gateway in gateways
    }
    rows = db.execute(
        select(Sensor, Motor)
        .join(Motor, Sensor.motor_id == Motor.id)
        .where(
            Sensor.enabled.is_(True),
            Sensor.gateway_id.in_(list(plans)),
            Motor.enabled.is_(True),
        )
        .where(Sensor.motor_id.in_(motor_ids) if motor_ids is not None else True)
        .order_by(Sensor.id)
    ).all()
    latest_map = latest_readings(db, list({motor.id for _, motor in rows}))
    for sensor, motor in rows:
        latest = latest_map.get(motor.id)
        plans[sensor.gateway_id].sensors.append(
            SensorPlan(
                id=sensor.id,
                code=sensor.code,
                motor_id=motor.id,
                motor_code=motor.code,
                motor_name=motor.name,
                gateway_id=sensor.gateway_id,
                gateway_code=plans[sensor.gateway_id].code,
                kind=sensor.kind,
                slave_id=sensor.slave_id,
                register_address=sensor.register_address,
                register_count=sensor.register_count,
                scale=sensor.scale,
                unit=sensor.unit,
                rated_current_a=motor.rated_current_a,
                temp_limit_c=motor.temp_limit_c,
                last_temperature_c=latest.temperature_c if latest else None,
                last_current_avg_a=latest.current_avg_a if latest else None,
            )
        )
    return list(plans.values())


def _poll_plans(plans: list[GatewayPlan], ts: datetime) -> list[GatewayReadResult]:
    if settings.collector_mode == "simulator":
        return [simulate_gateway(plan, ts) for plan in plans]
    results = []
    for plan in plans:
        logger.info("开始采集网关 %s (%s:%s)", plan.code, plan.host, plan.port)
        results.append(read_gateway(plan))
    return results


def _upsert_reading(
    db,
    motor: Motor,
    ts: datetime,
    temperature: float | None,
    current_a: float | None,
    current_b: float | None,
    current_c: float | None,
    current_avg: float | None,
    vibration_x: float | None,
    vibration_y: float | None,
    vibration_z: float | None,
    vibration_total: float | None,
    operating_state: str,
    quality: str,
    raw: dict,
) -> Reading:
    reading = db.scalar(select(Reading).where(Reading.motor_id == motor.id, Reading.ts == ts))
    if reading is None:
        reading = Reading(motor_id=motor.id, ts=ts)
        db.add(reading)
    reading.temperature_c = temperature
    reading.current_a = current_a
    reading.current_b = current_b
    reading.current_c = current_c
    reading.current_avg_a = current_avg
    reading.vibration_x = vibration_x
    reading.vibration_y = vibration_y
    reading.vibration_z = vibration_z
    reading.vibration_total_mm_s = vibration_total
    reading.operating_state = operating_state
    reading.quality = quality
    reading.raw = raw
    db.flush()
    return reading


def _packet_key(ts: datetime, gateway_id: int, sensor_id: int | None) -> str:
    return f"{ts.isoformat()}:{gateway_id}:{sensor_id or 0}"


def _log_packet_attempt(
    db,
    row: PacketLoss,
    *,
    attempt_no: int,
    success: bool,
    error: str | None,
    at: datetime,
) -> None:
    """写入一次采集/补采尝试明细，便于前端逐次查看失败原因。"""
    db.add(
        PacketLossAttempt(
            packet_loss_id=row.id,
            attempt_no=attempt_no,
            attempted_at=at,
            success=success,
            error=None if success else (error or "未知采集错误")[:2000],
        )
    )


def _upsert_packet_loss(
    db,
    *,
    ts: datetime,
    gateway_id: int,
    gateway_code: str,
    sensor_id: int | None,
    sensor_code: str | None,
    motor_id: int | None,
    motor_code: str | None,
    error: str,
    max_attempts: int,
    now: datetime,
) -> PacketLoss:
    key = _packet_key(ts, gateway_id, sensor_id)
    row = db.scalar(select(PacketLoss).where(PacketLoss.key == key))
    created = row is None
    if created:
        row = PacketLoss(
            key=key,
            cycle_ts=ts,
            gateway_id=gateway_id,
            gateway_code=gateway_code,
            sensor_id=sensor_id,
            sensor_code=sensor_code,
            motor_id=motor_id,
            motor_code=motor_code,
        )
        db.add(row)
    row.error = (error or "未知采集错误")[:2000]
    row.max_attempts = max_attempts
    row.attempts = 0
    row.last_attempt_at = None
    row.recovered_at = None
    if max_attempts <= 0:
        row.status = "failed"
        row.next_attempt_at = None
    else:
        row.status = "pending"
        row.next_attempt_at = now + timedelta(minutes=settings.packet_retry_delay_minutes)
    if created:
        db.flush()
        _log_packet_attempt(db, row, attempt_no=0, success=False, error=row.error, at=now)
    return row


def _mark_packet_recovered(
    db, *, ts: datetime, gateway_id: int, sensor_id: int | None, now: datetime
) -> None:
    key = _packet_key(ts, gateway_id, sensor_id)
    row = db.scalar(select(PacketLoss).where(PacketLoss.key == key))
    if row is not None and row.status != "recovered":
        row.attempts += 1
        row.status = "recovered"
        row.recovered_at = now
        row.next_attempt_at = None
        _log_packet_attempt(db, row, attempt_no=row.attempts, success=True, error=None, at=now)


def _record_packet_losses(
    db,
    plan: GatewayPlan,
    result: GatewayReadResult,
    ts: datetime,
    max_attempts: int,
    now: datetime,
) -> None:
    if not result.connected:
        _upsert_packet_loss(
            db,
            ts=ts,
            gateway_id=plan.id,
            gateway_code=plan.code,
            sensor_id=None,
            sensor_code=None,
            motor_id=None,
            motor_code=None,
            error=result.error or "网关连接失败",
            max_attempts=max_attempts,
            now=now,
        )
        return
    for sensor_plan in plan.sensors:
        sensor_result = result.sensor_results.get(sensor_plan.code)
        if sensor_result and sensor_result.success:
            _mark_packet_recovered(
                db, ts=ts, gateway_id=plan.id, sensor_id=sensor_plan.id, now=now
            )
            continue
        _upsert_packet_loss(
            db,
            ts=ts,
            gateway_id=plan.id,
            gateway_code=plan.code,
            sensor_id=sensor_plan.id,
            sensor_code=sensor_plan.code,
            motor_id=sensor_plan.motor_id,
            motor_code=sensor_plan.motor_code,
            error=(sensor_result.error if sensor_result else None) or "未返回读取结果",
            max_attempts=max_attempts,
            now=now,
        )


def persist_cycle(
    plans: list[GatewayPlan],
    results: list[GatewayReadResult],
    ts: datetime,
    track_losses: bool = True,
) -> CycleSummary:
    started = utcnow()
    attempts = 0
    successes = 0
    failures = 0
    new_alarm_ids: list[int] = []
    result_by_code = {result.gateway_code: result for result in results}

    with SessionLocal() as db:
        config = get_notification_config(db)
        sampling = get_sampling_config(db)
        retry_max_attempts = int(sampling.get("packet_retry_max_attempts", 3))
        for plan in plans:
            result = result_by_code.get(plan.code)
            if result is None:
                continue
            gateway = db.get(Gateway, plan.id)
            if gateway is not None:
                alarm = handle_gateway_result(
                    db, gateway, result.connected, result.error, config, now=ts
                )
                if alarm:
                    new_alarm_ids.append(alarm.id)
            if track_losses:
                _record_packet_losses(
                    db,
                    plan,
                    result,
                    ts,
                    retry_max_attempts,
                    utcnow(),
                )

            motor_payload: dict[int, dict] = {}
            for sensor_plan in plan.sensors:
                sensor = db.get(Sensor, sensor_plan.id)
                sensor_result = result.sensor_results.get(sensor_plan.code)
                success = bool(sensor_result and sensor_result.success)
                error = sensor_result.error if sensor_result else "未返回读取结果"
                if sensor is not None:
                    alarm = handle_sensor_result(db, sensor, success, error, config, now=ts)
                    if alarm:
                        new_alarm_ids.append(alarm.id)
                attempts += 1
                if success:
                    successes += 1
                else:
                    failures += 1

                payload = motor_payload.setdefault(
                    sensor_plan.motor_id,
                    {
                        "expected": 0,
                        "success": 0,
                        "temperature": None,
                        "current_a": None,
                        "current_b": None,
                        "current_c": None,
                        "current_avg": None,
                        "vibration_x": None,
                        "vibration_y": None,
                        "vibration_z": None,
                        "vibration_total": None,
                        "raw": {},
                    },
                )
                payload["expected"] += 1
                if success and sensor_result:
                    payload["success"] += 1
                    payload["raw"][sensor_plan.code] = sensor_result.raw
                    for key, value in sensor_result.values.items():
                        if key == "temperature_c":
                            payload["temperature"] = value
                        elif key == "current_avg_a":
                            payload["current_avg"] = value
                        elif key == "current_a":
                            payload["current_a"] = value
                        elif key == "current_b":
                            payload["current_b"] = value
                        elif key == "current_c":
                            payload["current_c"] = value
                        elif key == "vibration_x":
                            payload["vibration_x"] = value
                        elif key == "vibration_y":
                            payload["vibration_y"] = value
                        elif key == "vibration_z":
                            payload["vibration_z"] = value
                        elif key == "vibration_total_mm_s":
                            payload["vibration_total"] = value

            for motor_id, payload in motor_payload.items():
                motor = db.get(Motor, motor_id)
                if motor is None:
                    continue
                if payload["success"] == payload["expected"]:
                    quality = "ok"
                elif payload["success"] > 0:
                    quality = "partial"
                else:
                    quality = "error"
                previous = db.scalar(
                    select(Reading)
                    .where(Reading.motor_id == motor.id, Reading.ts < ts)
                    .order_by(Reading.ts.desc())
                    .limit(1)
                )
                previous_state = previous.operating_state if previous else None
                operating_state = classify_operating_state(motor, payload["current_avg"])
                if operating_state == "unknown" and previous_state:
                    operating_state = previous_state
                reading = _upsert_reading(
                    db,
                    motor,
                    ts,
                    payload["temperature"],
                    payload["current_a"],
                    payload["current_b"],
                    payload["current_c"],
                    payload["current_avg"],
                    payload["vibration_x"],
                    payload["vibration_y"],
                    payload["vibration_z"],
                    payload["vibration_total"],
                    operating_state,
                    quality,
                    payload["raw"],
                )
                if quality == "error":
                    continue
                baseline = compute_baseline(db, motor, now=ts)
                candidates = evaluate_rules(
                    motor,
                    payload["temperature"],
                    payload["current_avg"],
                    baseline,
                    None,
                    current_a=payload["current_a"],
                    current_b=payload["current_b"],
                    current_c=payload["current_c"],
                    vibration_total_mm_s=payload["vibration_total"],
                    vibration_x=payload["vibration_x"],
                    vibration_y=payload["vibration_y"],
                    vibration_z=payload["vibration_z"],
                    operating_state=operating_state,
                    previous_state=previous_state,
                )
                alarms = apply_reading_alarms(db, motor, reading, candidates, config, now=ts)
                new_alarm_ids.extend(alarm.id for alarm in alarms)

            db.add(
                PollCycle(
                    gateway_code=plan.code,
                    started_at=started,
                    finished_at=utcnow(),
                    attempts=len(plan.sensors),
                    successes=sum(1 for item in result.sensor_results.values() if item.success),
                    failures=sum(1 for item in result.sensor_results.values() if not item.success),
                    duration_ms=result.duration_ms,
                    error=result.error,
                )
            )
            db.commit()

    unique_alarm_ids = list(dict.fromkeys(new_alarm_ids))
    for alarm_id in unique_alarm_ids:
        try:
            notify_alarm(alarm_id)
        except Exception as exc:
            logger.exception("告警通知失败 alarm=%s err=%s", alarm_id, exc)

    finished = utcnow()
    return CycleSummary(
        started_at=started,
        finished_at=finished,
        gateways=len(plans),
        attempts=attempts,
        successes=successes,
        failures=failures,
        new_alarms=len(unique_alarm_ids),
        duration_ms=int((finished - started).total_seconds() * 1000),
    )


def _pending_recheck_motor_ids(db) -> set[int]:
    return set(
        db.scalars(
            select(AlarmStreak.motor_id)
            .where(
                AlarmStreak.count > 0,
                AlarmStreak.rule_key.in_(CONFIRM_RULE_KEYS),
            )
            .distinct()
        ).all()
    )


def pending_recheck_at() -> datetime | None:
    with SessionLocal() as db:
        last_ts = db.scalar(
            select(func.min(AlarmStreak.last_ts)).where(
                AlarmStreak.count > 0,
                AlarmStreak.rule_key.in_(CONFIRM_RULE_KEYS),
            )
        )
    last = as_utc(last_ts)
    if last is None:
        return None
    return last + timedelta(minutes=settings.alarm_recheck_interval_minutes)


def run_poll_cycle(
    ts: datetime | None = None,
    bucket_minutes: int | None = None,
    recheck: bool = False,
) -> CycleSummary:
    interval = bucket_minutes or settings.poll_interval_minutes
    cycle_ts = floor_bucket(as_utc(ts or utcnow()) or utcnow(), interval)
    with SessionLocal() as db:
        motor_ids = _pending_recheck_motor_ids(db) if recheck else None
        plans = load_gateway_plans(db, motor_ids=motor_ids)
    if not plans:
        now = utcnow()
        logger.warning("没有启用的网关或采集点，跳过本轮采集")
        return CycleSummary(
            started_at=now,
            finished_at=now,
            gateways=0,
            attempts=0,
            successes=0,
            failures=0,
            new_alarms=0,
            duration_ms=0,
        )
    results = _poll_plans(plans, cycle_ts)
    summary = persist_cycle(plans, results, cycle_ts)
    logger.info("采集完成 %s", summary.to_dict())
    return summary


def _apply_packet_retry_result(
    rows: list[PacketLoss], result: GatewayReadResult, now: datetime, db=None
) -> None:
    for row in rows:
        row.attempts += 1
        row.last_attempt_at = now
        if row.sensor_id is None:
            success = result.connected
            error = result.error
        else:
            sensor_result = result.sensor_results.get(row.sensor_code or "")
            success = bool(sensor_result and sensor_result.success)
            error = sensor_result.error if sensor_result else "未返回读取结果"
        if db is not None:
            _log_packet_attempt(
                db, row, attempt_no=row.attempts, success=success, error=error, at=now
            )
        if success:
            row.status = "recovered"
            row.recovered_at = now
            row.next_attempt_at = None
            continue
        row.error = (error or "未知采集错误")[:2000]
        if row.attempts >= row.max_attempts:
            row.status = "failed"
            row.next_attempt_at = None
        else:
            row.status = "pending"
            row.next_attempt_at = now + timedelta(minutes=settings.packet_retry_delay_minutes)


def retry_due_packet_losses() -> int:
    now = utcnow()
    with SessionLocal() as db:
        due = list(
            db.scalars(
                select(PacketLoss)
                .where(
                    PacketLoss.status == "pending",
                    PacketLoss.next_attempt_at.is_not(None),
                    PacketLoss.next_attempt_at <= now,
                )
                .order_by(PacketLoss.next_attempt_at)
                .limit(30)
            ).all()
        )
        groups: dict[tuple[int, datetime], list[int]] = {}
        for row in due:
            groups.setdefault((row.gateway_id, as_utc(row.cycle_ts) or now), []).append(row.id)

    for (gateway_id, cycle_ts), ids in groups.items():
        with SessionLocal() as db:
            plans = load_gateway_plans(db)
            plan = next((item for item in plans if item.id == gateway_id), None)
            rows = list(db.scalars(select(PacketLoss).where(PacketLoss.id.in_(ids))).all())
            if plan is None:
                attempted = utcnow()
                for row in rows:
                    row.attempts += 1
                    row.last_attempt_at = attempted
                    row.status = "failed"
                    row.error = "网关或采集点已停用，无法补采"
                    row.next_attempt_at = None
                    _log_packet_attempt(
                        db,
                        row,
                        attempt_no=row.attempts,
                        success=False,
                        error=row.error,
                        at=attempted,
                    )
                db.commit()
                continue
        try:
            result = read_gateway(plan)
            persist_cycle([plan], [result], cycle_ts, track_losses=False)
        except Exception as exc:
            logger.exception("丢包补采异常 gateway=%s ts=%s", plan.code, cycle_ts)
            attempted = utcnow()
            with SessionLocal() as db:
                for row in db.scalars(select(PacketLoss).where(PacketLoss.id.in_(ids))).all():
                    row.attempts += 1
                    row.last_attempt_at = attempted
                    row.error = str(exc)[:2000]
                    if row.attempts >= row.max_attempts:
                        row.status = "failed"
                        row.next_attempt_at = None
                    else:
                        row.status = "pending"
                        row.next_attempt_at = attempted + timedelta(
                            minutes=settings.packet_retry_delay_minutes
                        )
                    _log_packet_attempt(
                        db,
                        row,
                        attempt_no=row.attempts,
                        success=False,
                        error=row.error,
                        at=attempted,
                    )
                db.commit()
            continue
        with SessionLocal() as db:
            _apply_packet_retry_result(
                list(db.scalars(select(PacketLoss).where(PacketLoss.id.in_(ids))).all()),
                result,
                utcnow(),
                db=db,
            )
            db.commit()
    return len(groups)


class PacketRetryService(threading.Thread):
    def __init__(self) -> None:
        super().__init__(name="packet-retry", daemon=True)
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                count = retry_due_packet_losses()
                if count:
                    logger.info("执行丢包补采 %s 组", count)
            except Exception:
                logger.exception("丢包补采调度异常")
            self._stop_event.wait(2.0)


def cleanup_old_data() -> None:
    cutoff = utcnow() - timedelta(days=settings.retention_days)
    poll_cutoff = utcnow() - timedelta(days=max(30, settings.retention_days))
    with SessionLocal() as db:
        readings = db.execute(delete(Reading).where(Reading.ts < cutoff)).rowcount
        cycles = db.execute(delete(PollCycle).where(PollCycle.started_at < poll_cutoff)).rowcount
        old_loss_ids = select(PacketLoss.id).where(PacketLoss.cycle_ts < cutoff)
        attempts = db.execute(
            delete(PacketLossAttempt).where(PacketLossAttempt.packet_loss_id.in_(old_loss_ids))
        ).rowcount
        losses = db.execute(delete(PacketLoss).where(PacketLoss.cycle_ts < cutoff)).rowcount
        db.commit()
    logger.info(
        "历史数据清理完成 readings=%s poll_cycles=%s packet_losses=%s packet_attempts=%s",
        readings,
        cycles,
        losses,
        attempts,
    )


class CollectorService(threading.Thread):
    def __init__(self) -> None:
        super().__init__(name="motor-collector", daemon=True)
        self._stop_event = threading.Event()
        self._force_event = threading.Event()
        self._reschedule_event = threading.Event()
        self._status_lock = threading.Lock()
        self._status: dict = {
            "running": False,
            "last_started_at": None,
            "last_finished_at": None,
            "last_error": None,
            "next_run_at": None,
            "last_cycle": None,
            "mode": settings.collector_mode,
        }
        self._last_cleanup: datetime | None = None
        self._next_recheck_at: datetime | None = None

    def _update(self, **values) -> None:
        with self._status_lock:
            self._status.update(values)

    def status(self) -> dict:
        with self._status_lock:
            return dict(self._status)

    def trigger(self) -> None:
        self._force_event.set()

    def reschedule(self) -> None:
        self._reschedule_event.set()

    def stop(self) -> None:
        self._stop_event.set()
        self._force_event.set()

    def _run_once(self, recheck: bool = False) -> None:
        started = utcnow()
        self._update(
            running=True, last_started_at=iso(started), last_error=None, rechecking=recheck
        )
        try:
            summary = run_poll_cycle(
                bucket_minutes=settings.alarm_recheck_interval_minutes if recheck else None,
                recheck=recheck,
            )
            self._update(last_cycle=summary.to_dict(), running=False, rechecking=False)
            if self._last_cleanup is None or (started - self._last_cleanup) > timedelta(hours=24):
                cleanup_old_data()
                self._last_cleanup = started
        except Exception as exc:
            logger.exception("采集周期异常")
            self._update(running=False, rechecking=False, last_error=str(exc)[:255])
        finally:
            self._update(last_finished_at=iso(utcnow()))

    def _refresh_recheck(self) -> None:
        self._next_recheck_at = pending_recheck_at()
        self._update(next_recheck_at=iso(self._next_recheck_at) if self._next_recheck_at else None)

    def run(self) -> None:
        self._update(thread_alive=True)
        try:
            if settings.poll_on_start:
                self._run_once()
            self._refresh_recheck()
            while not self._stop_event.is_set():
                normal_next = next_poll_time(utcnow(), settings.poll_interval_minutes)
                recheck = bool(self._next_recheck_at and self._next_recheck_at < normal_next)
                next_run = self._next_recheck_at if recheck else normal_next
                self._update(next_run_at=iso(next_run))
                rescheduled = False
                while not self._stop_event.is_set():
                    if self._reschedule_event.is_set():
                        self._reschedule_event.clear()
                        rescheduled = True
                        break
                    remaining = (next_run - utcnow()).total_seconds()
                    if remaining <= 0 or self._force_event.is_set():
                        break
                    self._stop_event.wait(min(1.0, remaining))
                if self._stop_event.is_set():
                    break
                if rescheduled:
                    continue
                if self._force_event.is_set():
                    self._force_event.clear()
                    logger.info("收到手动召测请求")
                    recheck = False
                self._run_once(recheck=recheck)
                self._refresh_recheck()
        finally:
            self._update(thread_alive=False, running=False)


_collector: CollectorService | None = None
_manual_lock = threading.Lock()


def start_collector() -> CollectorService:
    global _collector
    _collector = CollectorService()
    _collector.start()
    return _collector


def get_collector() -> CollectorService | None:
    return _collector


def request_manual_poll() -> str:
    collector = get_collector()
    if collector and collector.is_alive():
        collector.trigger()
        return "queued"

    def _run_background():
        with _manual_lock:
            run_poll_cycle()

    threading.Thread(target=_run_background, name="manual-poll", daemon=True).start()
    return "started"


_packet_retry: PacketRetryService | None = None


def start_packet_retry() -> PacketRetryService:
    global _packet_retry
    _packet_retry = PacketRetryService()
    _packet_retry.start()
    return _packet_retry


def stop_packet_retry() -> None:
    global _packet_retry
    if _packet_retry is not None:
        _packet_retry.stop()
        _packet_retry = None
