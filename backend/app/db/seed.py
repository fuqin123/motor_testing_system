"""点表导入与演示数据生成。"""

import logging
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import as_utc, floor_bucket, local_zone, utcnow
from app.db.models import (
    Alarm,
    AuditLog,
    Gateway,
    Motor,
    NotificationLog,
    PollCycle,
    Reading,
    Sensor,
)
from app.db.session import SessionLocal
from app.services.baseline import clear_baseline_cache

logger = logging.getLogger(__name__)

DEMO_MOTORS = [
    {
        "code": "M-01",
        "name": "1#循环水泵电机",
        "location": "一车间 · 循环水泵房",
        "group_name": "泵组A",
        "rated_kw": 132,
        "rated_current_a": 240,
        "pilot": True,
        "node_code": "N-01",
        "vfd_model": "ABB ACS580",
        "install_date": "2019-03",
        "last_maintenance": "2026-10-28 润滑保养",
        "temp_limit_c": 85,
        "current_limit_a": 252,
        "base_temp": 58.4,
        "base_load": 0.71,
    },
    {
        "code": "M-02",
        "name": "2#循环水泵电机",
        "location": "一车间 · 循环水泵房",
        "group_name": "泵组A",
        "rated_kw": 132,
        "rated_current_a": 240,
        "pilot": True,
        "node_code": "N-01",
        "vfd_model": "ABB ACS580",
        "install_date": "2019-03",
        "last_maintenance": "2026-11-11 清理风道滤网",
        "temp_limit_c": 85,
        "current_limit_a": 252,
        "base_temp": 61.5,
        "base_load": 0.70,
    },
    {
        "code": "M-03",
        "name": "主排风机",
        "location": "二车间 · 排风机房",
        "group_name": "风机组",
        "rated_kw": 160,
        "rated_current_a": 290,
        "pilot": True,
        "node_code": "N-02",
        "vfd_model": "西门子 G120",
        "install_date": "2020-06",
        "last_maintenance": "2026-09-15 轴承补脂",
        "temp_limit_c": 85,
        "current_limit_a": 305,
        "base_temp": 72.6,
        "base_load": 0.65,
        "temp_anomaly": True,
    },
    {
        "code": "M-04",
        "name": "空压机主电机",
        "location": "空压站",
        "group_name": "空压站",
        "rated_kw": 110,
        "rated_current_a": 200,
        "pilot": False,
        "node_code": "N-02",
        "vfd_model": "汇川 MD500",
        "install_date": "2021-01",
        "last_maintenance": "2026-11-09 负载阀门检修",
        "temp_limit_c": 85,
        "current_limit_a": 210,
        "base_temp": 69.8,
        "base_load": 0.80,
    },
    {
        "code": "M-05",
        "name": "冷却塔风机",
        "location": "动力站 · 冷却塔",
        "group_name": "风机组",
        "rated_kw": 75,
        "rated_current_a": 140,
        "pilot": False,
        "node_code": "N-03",
        "vfd_model": "汇川 MD500",
        "install_date": "2021-11",
        "last_maintenance": "2026-10-30 皮带张紧",
        "temp_limit_c": 80,
        "current_limit_a": 147,
        "base_temp": 53.6,
        "base_load": 0.58,
        "current_anomaly": True,
    },
    {
        "code": "M-06",
        "name": "锅炉给水泵",
        "location": "锅炉房",
        "group_name": "泵组A",
        "rated_kw": 132,
        "rated_current_a": 240,
        "pilot": False,
        "node_code": "N-03",
        "vfd_model": "ABB ACS580",
        "install_date": "2018-08",
        "last_maintenance": "2026-10-12 联轴器检查",
        "temp_limit_c": 85,
        "current_limit_a": 252,
        "base_temp": 57.2,
        "base_load": 0.66,
    },
]


def _sensor_code(motor_code: str, kind: str) -> str:
    digits = "".join(char for char in motor_code if char.isdigit()) or "00"
    return f"{'T' if kind == 'temperature' else 'C'}-{digits}"


def _reset_all(db: Session) -> None:
    db.execute(delete(NotificationLog))
    db.execute(delete(Alarm))
    db.execute(delete(Reading))
    db.execute(delete(PollCycle))
    db.execute(delete(AuditLog))
    db.execute(delete(Sensor))
    db.execute(delete(Motor))
    db.execute(delete(Gateway))
    db.commit()


def seed_demo(reset: bool = False) -> bool:
    """生成 6 台演示电机、30 天读数和告警样例。"""
    now = as_utc(utcnow())
    assert now is not None
    with SessionLocal() as db:
        if reset:
            _reset_all(db)
        existing = db.scalar(select(Motor).limit(1))
        if existing is not None:
            logger.info("数据库已有电机数据，跳过演示数据生成（--reset 可重建）")
            return False

        gateway = Gateway(
            code="GW-01",
            name="一车间 LoRa 网关",
            host="10.112.66.231",
            port=10123,
            framer="rtu",
            enabled=True,
            model="LoRa 网关",
            firmware="v1.4.2",
            note="厂区网口上联 · 演示数据",
            last_seen_at=now,
        )
        db.add(gateway)
        db.flush()

        motors: list[Motor] = []
        for index, config in enumerate(DEMO_MOTORS, start=1):
            motor = Motor(
                code=config["code"],
                name=config["name"],
                location=config["location"],
                group_name=config["group_name"],
                rated_kw=config["rated_kw"],
                rated_current_a=config["rated_current_a"],
                pilot=config["pilot"],
                enabled=True,
                node_code=config["node_code"],
                vfd_model=config["vfd_model"],
                install_date=config["install_date"],
                last_maintenance=config["last_maintenance"],
                temp_limit_c=config["temp_limit_c"],
                current_limit_a=config["current_limit_a"],
                temp_deviation_pct=8.0,
                current_deviation_pct=10.0,
                phase_imbalance_pct=10.0,
                rise_rate_limit_c_per_day=1.0,
                notify_enabled=True,
            )
            db.add(motor)
            db.flush()
            for kind, slave_id in (("temperature", index * 2 - 1), ("current", index * 2)):
                sensor = Sensor(
                    code=_sensor_code(motor.code, kind),
                    motor_id=motor.id,
                    gateway_id=gateway.id,
                    kind=kind,
                    name="外壳温度" if kind == "temperature" else "三相电流",
                    slave_id=slave_id,
                    register_address=0,
                    register_count=1 if kind == "temperature" else 3,
                    scale=0.1 if kind == "temperature" else 0.01,
                    unit="℃" if kind == "temperature" else "A",
                    enabled=True,
                    power_type="市电供电",
                    firmware="—",
                    last_read_at=now,
                )
                db.add(sensor)
            motors.append(motor)
        db.commit()

        step = timedelta(minutes=settings.poll_interval_minutes)
        end = floor_bucket(now, settings.poll_interval_minutes)
        start = end - timedelta(days=30)
        timestamps = []
        current = start
        while current <= end:
            timestamps.append(current)
            current += step

        rows = []
        for motor, config in zip(motors, DEMO_MOTORS):
            for ts in timestamps:
                rng = random.Random(f"{motor.code}:{ts.isoformat()}")
                local = ts.astimezone(local_zone())
                hour = local.hour + local.minute / 60
                daily = math.sin((hour - 9) / 24 * math.tau) * 3.0
                temperature = config["base_temp"] + daily + (rng.random() - 0.5) * 1.8
                if config.get("temp_anomaly"):
                    anomaly_start = end - timedelta(days=7)
                    if ts >= anomaly_start:
                        progress = (ts - anomaly_start) / (end - anomaly_start)
                        target = motor.temp_limit_c + 2.4
                        temperature = (
                            config["base_temp"]
                            + daily
                            + progress * (target - (config["base_temp"] + daily))
                        )
                        if ts == end:
                            temperature = target
                load = config["base_load"] + 0.03 * math.sin((hour - 8) / 24 * math.tau)
                load += (rng.random() - 0.5) * 0.025
                if config.get("current_anomaly") and ts >= end - timedelta(days=1):
                    load *= 1.13
                current_avg = motor.rated_current_a * load
                phase_a = current_avg * (1 + (rng.random() - 0.5) * 0.012)
                phase_b = current_avg * (1 + (rng.random() - 0.5) * 0.012)
                phase_c = current_avg * (1 + (rng.random() - 0.5) * 0.012)
                rows.append(
                    {
                        "motor_id": motor.id,
                        "ts": ts,
                        "temperature_c": round(temperature, 2),
                        "current_a": round(phase_a, 2),
                        "current_b": round(phase_b, 2),
                        "current_c": round(phase_c, 2),
                        "current_avg_a": round((phase_a + phase_b + phase_c) / 3, 2),
                        "quality": "ok",
                        "raw": {},
                        "created_at": now,
                    }
                )
                if len(rows) >= 2000:
                    db.bulk_insert_mappings(Reading, rows)
                    db.commit()
                    rows = []
        if rows:
            db.bulk_insert_mappings(Reading, rows)
            db.commit()

        def add_alarm(
            *,
            level: str,
            rule_key: str,
            title: str,
            description: str,
            advice: str,
            motor: Motor | None,
            device_code: str,
            value: float | None,
            threshold: float | None,
            unit: str,
            triggered_at: datetime,
            closed_at: datetime | None = None,
            solution: str | None = None,
            owner: str,
        ) -> Alarm:
            alarm = Alarm(
                level=level,
                rule_key=rule_key,
                title=title,
                description=description,
                advice=advice,
                motor_code=motor.code if motor else None,
                motor_name=motor.name if motor else None,
                device_code=device_code,
                metric=rule_key,
                value=value,
                threshold=threshold,
                unit=unit,
                status="closed" if closed_at else "open",
                owner=owner,
                notification_status="sent",
                notification_to=f"设备运维告警群 · {owner}",
                notified_at=triggered_at + timedelta(seconds=2),
                triggered_at=triggered_at,
                last_seen_at=triggered_at + timedelta(minutes=5),
                closed_at=closed_at,
                closed_by=owner if closed_at else None,
                solution=solution,
                normal_count=0,
                dedup_key=f"{motor.code if motor else device_code}:{rule_key}",
            )
            db.add(alarm)
            db.flush()
            db.add(
                NotificationLog(
                    alarm_id=alarm.id,
                    channel="feishu",
                    target=alarm.notification_to,
                    status="sent",
                    attempts=1,
                    response_code=200,
                    response_body='{"code":0}',
                    created_at=alarm.notified_at,
                )
            )
            return alarm

        add_alarm(
            level="crit",
            rule_key="temp_high",
            title="外壳温度越限",
            description="温度 87.4°C 超过上限 85.0°C，已持续 42 分钟；电流正常，疑似散热 / 轴承 / 润滑问题。",
            advice="优先检查风道散热、轴承润滑与端盖温升，安排红外测温复核。",
            motor=motors[2],
            device_code="M-03",
            value=87.4,
            threshold=85.0,
            unit="°C",
            triggered_at=now - timedelta(minutes=42),
            owner="王工 · 设备科",
        )
        add_alarm(
            level="warn",
            rule_key="current_deviation",
            title="电流偏离自身基线",
            description="运行电流较自身正常基线偏高 12.4%，超过 ±10% 关注线；温度正常，疑似负载或电气侧波动。",
            advice="检查冷却塔液位与皮带张紧，观察变频器输出是否平衡。",
            motor=motors[4],
            device_code="M-05",
            value=12.4,
            threshold=10.0,
            unit="%",
            triggered_at=now - timedelta(minutes=68),
            owner="李工 · 电气",
        )
        add_alarm(
            level="warn",
            rule_key="temp_deviation",
            title="温度高于自身基线",
            description="外壳温度较过去 30 天正常基线偏高 8.2%，连续 2 天上升。",
            advice="对比同类电机，检查散热与环境温度。",
            motor=motors[1],
            device_code="M-02",
            value=8.2,
            threshold=8.0,
            unit="%",
            triggered_at=now - timedelta(hours=6),
            closed_at=now - timedelta(hours=5),
            solution="清理风道滤网，复测温度回落至基线区间。",
            owner="王工 · 设备科",
        )
        add_alarm(
            level="crit",
            rule_key="current_high",
            title="电流瞬时越限",
            description="运行电流 212 A 瞬时超上限 210 A，持续 3 分钟后回落。",
            advice="检查负载侧机械阻力与阀门开度。",
            motor=motors[3],
            device_code="M-04",
            value=212.0,
            threshold=210.0,
            unit="A",
            triggered_at=now - timedelta(hours=8),
            closed_at=now - timedelta(hours=7),
            solution="负载侧阀门卡涩，已检修处理，复测正常。",
            owner="王工 · 设备科",
        )
        add_alarm(
            level="warn",
            rule_key="temp_rise",
            title="温度持续上升",
            description="近 7 天温度单边上行，温升速率 +1.1°C/天，超过关注线 1.0°C/天。",
            advice="安排检查散热风道与轴承润滑。",
            motor=motors[5],
            device_code="M-06",
            value=1.1,
            threshold=1.0,
            unit="°C/天",
            triggered_at=now - timedelta(hours=4),
            closed_at=now - timedelta(hours=3),
            solution="补脂并清理散热片，温升恢复正常。",
            owner="李工 · 电气",
        )
        add_alarm(
            level="info",
            rule_key="sensor_error",
            title="采集传感器通信异常",
            description="T-03 连续 3 个周期读取失败，RS485 无响应。",
            advice="检查传感器供电、RS485 接线与从站地址。",
            motor=motors[2],
            device_code="T-03",
            value=None,
            threshold=None,
            unit="",
            triggered_at=now - timedelta(days=2),
            closed_at=now - timedelta(days=2) + timedelta(hours=1),
            solution="接线端子松动，紧固后通信恢复。",
            owner="李工 · 电气",
        )

        cycle_start = floor_bucket(now - timedelta(days=30), settings.poll_interval_minutes)
        cycle = cycle_start
        cycle_rows = []
        while cycle <= end:
            cycle_rows.append(
                {
                    "gateway_code": "GW-01",
                    "started_at": cycle,
                    "finished_at": cycle + timedelta(milliseconds=420),
                    "attempts": 12,
                    "successes": 12,
                    "failures": 0,
                    "duration_ms": 380 + int(random.Random(cycle.isoformat()).random() * 120),
                    "error": None,
                }
            )
            cycle += step
        db.bulk_insert_mappings(PollCycle, cycle_rows)
        db.commit()

    clear_baseline_cache()
    logger.info("演示数据生成完成：6 台电机 · 30 天读数 · 6 条告警")
    return True


def import_points(path: str) -> dict:
    """从 YAML 点表导入网关、电机与传感器。"""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"点表文件不存在: {path}")
    data = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    gateways = data.get("gateways") or []
    motors = data.get("motors") or []
    stats = {"gateways": 0, "motors": 0, "sensors": 0}
    with SessionLocal() as db:
        gateway_map: dict[str, Gateway] = {}
        for item in gateways:
            code = str(item["code"]).strip()
            gateway = db.scalar(select(Gateway).where(Gateway.code == code))
            if gateway is None:
                gateway = Gateway(code=code, name=item.get("name", code), host=item["host"])
                db.add(gateway)
            gateway.name = item.get("name", gateway.name)
            gateway.host = str(item.get("host", gateway.host))
            gateway.port = int(item.get("port", gateway.port or 502))
            framer = str(item.get("framer", gateway.framer or "rtu")).lower()
            if framer not in ("rtu", "tcp"):
                raise ValueError(f"网关 {code} framer 必须为 rtu 或 tcp")
            gateway.framer = framer
            gateway.enabled = bool(item.get("enabled", True))
            gateway.model = str(item.get("model", gateway.model or "LoRa 网关"))
            gateway.firmware = str(item.get("firmware", gateway.firmware or "—"))
            gateway.note = str(item.get("note", gateway.note or ""))
            db.flush()
            gateway_map[code] = gateway
            stats["gateways"] += 1

        for item in motors:
            code = str(item["code"]).strip()
            motor = db.scalar(select(Motor).where(Motor.code == code))
            if motor is None:
                motor = Motor(code=code, name=item.get("name", code))
                db.add(motor)
            motor.name = item.get("name", motor.name)
            motor.location = item.get("location", motor.location or "")
            motor.group_name = item.get("group", motor.group_name or "未分组")
            motor.rated_kw = float(item.get("rated_kw", motor.rated_kw or 0))
            motor.rated_current_a = float(item.get("rated_current_a", motor.rated_current_a or 0))
            motor.pilot = bool(item.get("pilot", motor.pilot))
            motor.enabled = bool(item.get("enabled", True))
            motor.node_code = str(item.get("node_code", motor.node_code or "N-01"))
            motor.vfd_model = str(item.get("vfd_model", motor.vfd_model or ""))
            motor.install_date = str(item.get("install_date", motor.install_date or ""))
            motor.last_maintenance = str(item.get("last_maintenance", motor.last_maintenance or ""))
            motor.temp_limit_c = float(item.get("temp_limit_c", motor.temp_limit_c or 85))
            motor.current_limit_a = float(
                item.get(
                    "current_limit_a",
                    motor.current_limit_a or motor.rated_current_a * 1.05,
                )
            )
            motor.temp_deviation_pct = float(
                item.get("temp_deviation_pct", motor.temp_deviation_pct or 8)
            )
            motor.current_deviation_pct = float(
                item.get("current_deviation_pct", motor.current_deviation_pct or 10)
            )
            motor.phase_imbalance_pct = float(
                item.get("phase_imbalance_pct", motor.phase_imbalance_pct or 10)
            )
            motor.rise_rate_limit_c_per_day = float(
                item.get("rise_rate_limit_c_per_day", motor.rise_rate_limit_c_per_day or 1)
            )
            motor.notify_enabled = bool(item.get("notify_enabled", True))
            db.flush()
            stats["motors"] += 1

            for sensor_item in item.get("sensors") or []:
                kind = str(sensor_item.get("kind", "")).strip()
                if kind not in ("temperature", "current"):
                    raise ValueError(f"{code} 的传感器 kind 必须为 temperature 或 current")
                gateway_code = str(sensor_item.get("gateway", "")).strip()
                gateway = gateway_map.get(gateway_code)
                if gateway is None:
                    raise ValueError(f"{code} 引用了不存在的网关: {gateway_code}")
                sensor = db.scalar(
                    select(Sensor).where(Sensor.motor_id == motor.id, Sensor.kind == kind)
                )
                if sensor is None:
                    sensor = Sensor(
                        code=_sensor_code(code, kind),
                        motor_id=motor.id,
                        gateway_id=gateway.id,
                        kind=kind,
                    )
                    db.add(sensor)
                sensor.code = _sensor_code(code, kind)
                sensor.gateway_id = gateway.id
                sensor.name = sensor_item.get(
                    "name", "外壳温度" if kind == "temperature" else "三相电流"
                )
                sensor.slave_id = int(sensor_item.get("slave_id", sensor.slave_id or 1))
                sensor.register_address = int(
                    sensor_item.get("register_address", sensor.register_address or 0)
                )
                default_count = 1 if kind == "temperature" else 3
                sensor.register_count = int(
                    sensor_item.get("register_count", sensor.register_count or default_count)
                )
                default_scale = 0.1 if kind == "temperature" else 0.01
                sensor.scale = float(sensor_item.get("scale", sensor.scale or default_scale))
                sensor.unit = str(sensor_item.get("unit", "℃" if kind == "temperature" else "A"))
                sensor.enabled = bool(sensor_item.get("enabled", True))
                sensor.power_type = str(sensor_item.get("power_type", "市电供电"))
                sensor.firmware = str(sensor_item.get("firmware", "—"))
                stats["sensors"] += 1
        db.commit()
    clear_baseline_cache()
    logger.info("点表导入完成 %s", stats)
    return stats
