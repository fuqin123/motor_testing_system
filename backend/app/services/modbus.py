"""Modbus RTU over TCP / Modbus TCP 读取。"""

import logging
import time
from dataclasses import dataclass, field

from pymodbus import FramerType
from pymodbus.client import ModbusTcpClient

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SensorPlan:
    id: int
    code: str
    motor_id: int
    motor_code: str
    motor_name: str
    gateway_id: int
    gateway_code: str
    kind: str
    slave_id: int
    register_address: int
    register_count: int
    scale: float
    unit: str
    rated_current_a: float = 0.0
    temp_limit_c: float = 85.0
    last_temperature_c: float | None = None
    last_current_avg_a: float | None = None


@dataclass
class GatewayPlan:
    id: int
    code: str
    host: str
    port: int
    framer: str
    sensors: list[SensorPlan] = field(default_factory=list)


@dataclass
class SensorReadResult:
    sensor_code: str
    success: bool
    values: dict[str, float] = field(default_factory=dict)
    raw: list[int] = field(default_factory=list)
    error: str | None = None


@dataclass
class GatewayReadResult:
    gateway_code: str
    connected: bool
    duration_ms: int
    sensor_results: dict[str, SensorReadResult] = field(default_factory=dict)
    error: str | None = None


def _to_int16(value: int) -> int:
    return value - 0x10000 if value >= 0x8000 else value


def _parse(sensor: SensorPlan, registers: list[int]) -> dict[str, float]:
    raw_values = [_to_int16(value) * sensor.scale for value in registers]
    if sensor.kind == "temperature":
        return {"temperature_c": round(raw_values[0], 3)}
    if sensor.kind == "current":
        phases = [round(value, 3) for value in raw_values]
        values = {
            "current_a": phases[0] if len(phases) > 0 else None,
            "current_b": phases[1] if len(phases) > 1 else None,
            "current_c": phases[2] if len(phases) > 2 else None,
        }
        available = [value for value in phases if value is not None]
        values["current_avg_a"] = round(sum(available) / len(available), 3) if available else None
        return values
    raise ValueError(f"未知传感器类型: {sensor.kind}")


def read_gateway(plan: GatewayPlan) -> GatewayReadResult:
    started = time.perf_counter()
    results: dict[str, SensorReadResult] = {}
    if not plan.sensors:
        return GatewayReadResult(
            gateway_code=plan.code,
            connected=True,
            duration_ms=0,
            sensor_results=results,
        )

    kwargs: dict = {"timeout": settings.modbus_timeout_seconds}
    if plan.framer == "rtu":
        kwargs["framer"] = FramerType.RTU
    client = ModbusTcpClient(plan.host, port=plan.port, **kwargs)
    try:
        if not client.connect():
            error = f"连接网关失败: {plan.host}:{plan.port}"
            for sensor in plan.sensors:
                results[sensor.code] = SensorReadResult(
                    sensor_code=sensor.code, success=False, error=error
                )
            return GatewayReadResult(
                gateway_code=plan.code,
                connected=False,
                duration_ms=int((time.perf_counter() - started) * 1000),
                sensor_results=results,
                error=error,
            )

        for sensor in plan.sensors:
            last_error = None
            for attempt in range(settings.modbus_retries + 1):
                try:
                    response = client.read_holding_registers(
                        address=sensor.register_address,
                        count=sensor.register_count,
                        device_id=sensor.slave_id,
                    )
                    if response.isError():
                        last_error = f"Modbus 异常响应: {response}"
                    else:
                        values = _parse(sensor, list(response.registers))
                        results[sensor.code] = SensorReadResult(
                            sensor_code=sensor.code,
                            success=True,
                            values=values,
                            raw=list(response.registers),
                        )
                        last_error = None
                        break
                except Exception as exc:  # pymodbus 可能抛出多种链路异常
                    last_error = str(exc)[:255]
                    logger.warning(
                        "读取失败 gateway=%s sensor=%s attempt=%s err=%s",
                        plan.code,
                        sensor.code,
                        attempt + 1,
                        exc,
                    )
                time.sleep(0.2 * (attempt + 1))
            if last_error is not None:
                results[sensor.code] = SensorReadResult(
                    sensor_code=sensor.code, success=False, error=last_error
                )
            time.sleep(settings.modbus_register_gap_seconds)

        return GatewayReadResult(
            gateway_code=plan.code,
            connected=True,
            duration_ms=int((time.perf_counter() - started) * 1000),
            sensor_results=results,
        )
    finally:
        client.close()
