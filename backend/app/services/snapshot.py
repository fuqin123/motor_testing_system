"""生成飞书告警卡片使用的电机监测快照（PNG）。"""

import io
import os
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.db.models import Motor, Reading

WIDTH = 1200
HEIGHT = 675
BG = "#0B1220"
PANEL = "#111B30"
LINE = "#253452"
TEXT = "#E9EFFC"
MUTED = "#8E9BB8"
CYAN = "#2DD4EE"
AMBER = "#FFB224"
VIOLET = "#9D7CFF"
RED = "#FF4D6D"

_FONT_PATH = Path(__file__).resolve().parent.parent / "assets" / "NotoSansSC-MotorPulse.ttf"
_SYSTEM_FONTS = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "C:/Windows/Fonts/NotoSansSC-VF.ttf",
    "C:/Windows/Fonts/msyh.ttc",
)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [os.environ.get("MP_SNAPSHOT_FONT_PATH", ""), str(_FONT_PATH), *_SYSTEM_FONTS]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _text(draw: ImageDraw.ImageDraw, x: int, y: int, value: str, size: int, color: str) -> None:
    draw.text((x, y), value, font=_font(size), fill=color)


def _trend(
    points: list[float], x: int, y: int, width: int, height: int
) -> list[tuple[float, float]]:
    values = [value for value in points if value is not None]
    if len(values) < 2:
        return []
    low, high = min(values), max(values)
    span = high - low or 1.0
    return [
        (
            x + width * index / (len(values) - 1),
            y + height * (1 - (value - low) / span),
        )
        for index, value in enumerate(values)
    ]


def render_alarm_snapshot(
    motor: Motor, reading: Reading | None, history: list[Reading], alarm_time: datetime
) -> bytes:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, WIDTH, 8), fill=CYAN)
    _text(draw, 44, 34, "MotorPulse  |  电机监测快照", 28, TEXT)
    name = motor.name[:26]
    _text(draw, 44, 76, f"{motor.code}  ·  {name}  ·  {alarm_time:%Y-%m-%d %H:%M:%S}", 18, MUTED)
    _text(draw, WIDTH - 170, 40, "告警快照", 22, RED)

    temp = reading.temperature_c if reading else None
    current = reading.current_avg_a if reading else None
    vibration = reading.vibration_total_mm_s if reading else None
    cards = [
        (
            "外壳温度",
            f"{temp:.1f} °C" if temp is not None else "—",
            f"上限 {motor.temp_limit_c:.1f} °C",
            AMBER,
        ),
        (
            "平均电流",
            f"{current:.1f} A" if current is not None else "—",
            f"上限 {motor.current_limit_a:.1f} A",
            CYAN,
        ),
        (
            "振动总值",
            f"{vibration:.2f} mm/s" if vibration is not None else "—",
            f"上限 {motor.vibration_limit_mm_s:.2f} mm/s",
            VIOLET,
        ),
    ]
    for index, (label, value, limit, color) in enumerate(cards):
        left = 44 + index * 372
        draw.rounded_rectangle(
            (left, 132, left + 348, 262), radius=16, fill=PANEL, outline=LINE, width=1
        )
        draw.rectangle((left, 132, left + 5, 262), fill=color)
        _text(draw, left + 24, 152, label, 15, MUTED)
        _text(draw, left + 24, 180, value, 30, color)
        _text(draw, left + 24, 228, limit, 14, MUTED)

    phase_text = "—"
    if reading and reading.current_a is not None:
        phase_text = (
            f"A {reading.current_a:.1f} / B {reading.current_b or 0:.1f} / "
            f"C {reading.current_c or 0:.1f} A"
        )
    _text(draw, 44, 292, f"三相电流：{phase_text}", 16, MUTED)
    axis_text = "—"
    if reading and reading.vibration_x is not None:
        axis_text = (
            f"X {reading.vibration_x:.2f} / Y {reading.vibration_y or 0:.2f} / "
            f"Z {reading.vibration_z or 0:.2f} mm/s"
        )
    _text(draw, 44, 322, f"三轴振动：{axis_text}", 16, MUTED)

    draw.rounded_rectangle((44, 370, WIDTH - 44, 590), radius=16, fill=PANEL, outline=LINE, width=1)
    _text(draw, 66, 390, "24 小时趋势  ·  温度与平均电流", 14, MUTED)
    temps = [item.temperature_c for item in history if item.temperature_c is not None]
    currents = [item.current_avg_a for item in history if item.current_avg_a is not None]
    temp_points = _trend(temps, 80, 425, WIDTH - 160, 135)
    current_points = _trend(currents, 80, 425, WIDTH - 160, 135)
    if len(temp_points) > 1:
        draw.line(temp_points, fill=AMBER, width=3, joint="curve")
        _text(draw, 66, 560, f"温度最低 {min(temps):.1f}  最高 {max(temps):.1f} °C", 12, AMBER)
    if len(current_points) > 1:
        draw.line(current_points, fill=CYAN, width=2, joint="curve")
        _text(draw, 66, 578, f"电流最低 {min(currents):.1f}  最高 {max(currents):.1f} A", 12, CYAN)
    if len(temp_points) <= 1 and len(current_points) <= 1:
        _text(draw, 80, 500, "历史样本不足", 16, MUTED)

    _text(draw, 44, 620, "MotorPulse · 只监测、只报警，不控制电机", 14, MUTED)
    _text(draw, WIDTH - 180, 620, "飞书告警快照", 14, MUTED)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
