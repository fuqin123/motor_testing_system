"""演示/验收用数据模拟器，不连接真实网关。"""

import math
import random
from dataclasses import dataclass
from datetime import datetime

from app.core.time import as_utc, local_zone
from app.services.modbus import GatewayPlan, GatewayReadResult, SensorReadResult


@dataclass
class SimulatedValues:
    temperature_c: float | None = None
    current_a: float | None = None
    current_b: float | None = None
    current_c: float | None = None
    current_avg_a: float | None = None


def _code_index(code: str) -> int:
    digits = "".join(char for char in code if char.isdigit())
    return int(digits) if digits else 0


def simulate_motor(
    motor_code: str,
    rated_current_a: float,
    temp_limit_c: float,
    ts: datetime,
    last_temperature_c: float | None = None,
    last_current_avg_a: float | None = None,
) -> SimulatedValues:
    ts = as_utc(ts)
    assert ts is not None
    hour = ts.astimezone(local_zone()).hour + ts.minute / 60
    seed = f"{motor_code}:{ts.strftime('%Y%m%d%H%M')}"
    rng = random.Random(seed)
    index = _code_index(motor_code)

    if last_temperature_c is not None:
        temperature = last_temperature_c + (rng.random() - 0.5) * 0.35
    else:
        base_temp = temp_limit_c - 24 + index * 1.4
        daily = math.sin((hour - 9) / 24 * math.tau) * 3.0
        temperature = base_temp + daily + (rng.random() - 0.5) * 1.8
        if motor_code.endswith("03"):
            temperature = max(temperature, temp_limit_c + 2.2)
        if motor_code.endswith("06"):
            temperature -= 2.0

    if last_current_avg_a is not None:
        current_avg = max(0.0, last_current_avg_a * (1 + (rng.random() - 0.5) * 0.008))
    else:
        load = 0.68 + 0.05 * math.sin((hour - 8) / 24 * math.tau)
        load += (rng.random() - 0.5) * 0.03
        if motor_code.endswith("05"):
            load *= 1.12
        current_avg = max(0.0, rated_current_a * load)

    phase_a = current_avg * (1 + (rng.random() - 0.5) * 0.012)
    phase_b = current_avg * (1 + (rng.random() - 0.5) * 0.012)
    phase_c = current_avg * (1 + (rng.random() - 0.5) * 0.012)
    return SimulatedValues(
        temperature_c=round(temperature, 2),
        current_a=round(phase_a, 2),
        current_b=round(phase_b, 2),
        current_c=round(phase_c, 2),
        current_avg_a=round((phase_a + phase_b + phase_c) / 3, 2),
    )


def simulate_gateway(plan: GatewayPlan, ts: datetime) -> GatewayReadResult:
    results: dict[str, SensorReadResult] = {}
    for sensor in plan.sensors:
        values = simulate_motor(
            sensor.motor_code,
            rated_current_a=sensor.rated_current_a,
            temp_limit_c=sensor.temp_limit_c,
            ts=ts,
            last_temperature_c=sensor.last_temperature_c,
            last_current_avg_a=sensor.last_current_avg_a,
        )
        if sensor.kind == "temperature":
            results[sensor.code] = SensorReadResult(
                sensor_code=sensor.code,
                success=True,
                values={"temperature_c": values.temperature_c},
                raw=[int((values.temperature_c or 0) * 10)],
            )
            continue
        current = values.current_avg_a
        results[sensor.code] = SensorReadResult(
            sensor_code=sensor.code,
            success=True,
            values={
                "current_a": values.current_a or current,
                "current_b": values.current_b or current,
                "current_c": values.current_c or current,
                "current_avg_a": current,
            },
            raw=[
                int((value or 0) * 100)
                for value in (values.current_a, values.current_b, values.current_c)
            ],
        )
    return GatewayReadResult(
        gateway_code=plan.code,
        connected=True,
        duration_ms=35,
        sensor_results=results,
    )
