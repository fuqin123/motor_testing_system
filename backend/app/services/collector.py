"""采集调度器：单线程顺序采集，支持多网关与模拟模式。"""

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select

from app.core.config import settings
from app.core.time import as_utc, floor_bucket, iso, next_poll_time, utcnow
from app.db.models import Gateway, Motor, PollCycle, Reading, Sensor
from app.db.session import SessionLocal
from app.services.alarms import (
    apply_reading_alarms,
    evaluate_rules,
    handle_gateway_result,
    handle_sensor_result,
)
from app.services.analysis import daily_slope
from app.services.baseline import compute_baseline
from app.services.feishu import notify_alarm
from app.services.modbus import GatewayPlan, GatewayReadResult, SensorPlan, read_gateway
from app.services.settings import get_notification_config
from app.services.simulator import simulate_gateway
from app.services.telemetry import latest_readings, series_readings

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


def load_gateway_plans(db) -> list[GatewayPlan]:
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
    reading.quality = quality
    reading.raw = raw
    db.flush()
    return reading


def persist_cycle(
    plans: list[GatewayPlan],
    results: list[GatewayReadResult],
    ts: datetime,
) -> CycleSummary:
    started = utcnow()
    attempts = 0
    successes = 0
    failures = 0
    new_alarm_ids: list[int] = []
    result_by_code = {result.gateway_code: result for result in results}

    with SessionLocal() as db:
        config = get_notification_config(db)
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
                reading = _upsert_reading(
                    db,
                    motor,
                    ts,
                    payload["temperature"],
                    payload["current_a"],
                    payload["current_b"],
                    payload["current_c"],
                    payload["current_avg"],
                    quality,
                    payload["raw"],
                )
                if quality == "error":
                    continue
                baseline = compute_baseline(db, motor, now=ts)
                rise_readings = series_readings(
                    db, motor.id, ts - timedelta(days=settings.rise_rate_days), ts
                )
                slope, _ = daily_slope(rise_readings, min_days=3)
                candidates = evaluate_rules(
                    motor,
                    payload["temperature"],
                    payload["current_avg"],
                    baseline,
                    slope,
                    current_a=payload["current_a"],
                    current_b=payload["current_b"],
                    current_c=payload["current_c"],
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


def run_poll_cycle(ts: datetime | None = None) -> CycleSummary:
    cycle_ts = floor_bucket(as_utc(ts or utcnow()) or utcnow(), settings.poll_interval_minutes)
    with SessionLocal() as db:
        plans = load_gateway_plans(db)
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


def cleanup_old_data() -> None:
    cutoff = utcnow() - timedelta(days=settings.retention_days)
    poll_cutoff = utcnow() - timedelta(days=max(30, settings.retention_days))
    with SessionLocal() as db:
        readings = db.execute(delete(Reading).where(Reading.ts < cutoff)).rowcount
        cycles = db.execute(delete(PollCycle).where(PollCycle.started_at < poll_cutoff)).rowcount
        db.commit()
    logger.info("历史数据清理完成 readings=%s poll_cycles=%s", readings, cycles)


class CollectorService(threading.Thread):
    def __init__(self) -> None:
        super().__init__(name="motor-collector", daemon=True)
        self._stop_event = threading.Event()
        self._force_event = threading.Event()
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

    def _update(self, **values) -> None:
        with self._status_lock:
            self._status.update(values)

    def status(self) -> dict:
        with self._status_lock:
            return dict(self._status)

    def trigger(self) -> None:
        self._force_event.set()

    def stop(self) -> None:
        self._stop_event.set()
        self._force_event.set()

    def _run_once(self) -> None:
        started = utcnow()
        self._update(running=True, last_started_at=iso(started), last_error=None)
        try:
            summary = run_poll_cycle()
            self._update(last_cycle=summary.to_dict(), running=False)
            if self._last_cleanup is None or (started - self._last_cleanup) > timedelta(hours=24):
                cleanup_old_data()
                self._last_cleanup = started
        except Exception as exc:
            logger.exception("采集周期异常")
            self._update(running=False, last_error=str(exc)[:255])
        finally:
            self._update(last_finished_at=iso(utcnow()))

    def run(self) -> None:
        self._update(thread_alive=True)
        try:
            if settings.poll_on_start:
                self._run_once()
            while not self._stop_event.is_set():
                next_run = next_poll_time(utcnow(), settings.poll_interval_minutes)
                self._update(next_run_at=iso(next_run))
                while not self._stop_event.is_set():
                    remaining = (next_run - utcnow()).total_seconds()
                    if remaining <= 0 or self._force_event.is_set():
                        break
                    self._stop_event.wait(min(1.0, remaining))
                if self._stop_event.is_set():
                    break
                if self._force_event.is_set():
                    self._force_event.clear()
                    logger.info("收到手动召测请求")
                self._run_once()
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
