"""飞书应用机器人：图片上传、富文本卡片、卡片回调闭环。"""

import io
import json
import logging
from dataclasses import dataclass
from datetime import timedelta

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateImageRequest,
    CreateImageRequestBody,
    CreateMessageRequest,
    CreateMessageRequestBody,
)
from sqlalchemy import select

from app.core.config import settings
from app.core.time import as_utc, utcnow
from app.db.models import Alarm, AuditLog, Motor
from app.db.session import SessionLocal
from app.services.snapshot import render_alarm_snapshot
from app.services.telemetry import latest_readings, series_readings

logger = logging.getLogger(__name__)


@dataclass
class FeishuAppResult:
    status: str
    target: str
    attempts: int = 1
    response_code: int | None = None
    response_body: str | None = None
    image_key: str | None = None
    message_id: str | None = None


def _client(config: dict) -> lark.Client:
    return (
        lark.Client.builder()
        .app_id(str(config.get("app_id", "")))
        .app_secret(str(config.get("app_secret", "")))
        .build()
    )


def _send_card(client: lark.Client, chat_id: str, card: dict) -> FeishuAppResult:
    body = (
        CreateMessageRequestBody.builder()
        .receive_id(chat_id)
        .msg_type("interactive")
        .content(json.dumps(card, ensure_ascii=False))
        .build()
    )
    request = CreateMessageRequest.builder().receive_id_type("chat_id").request_body(body).build()
    response = client.im.v1.message.create(request)
    if response.success():
        return FeishuAppResult(
            status="sent",
            target=chat_id,
            response_code=response.code,
            response_body=response.msg,
            message_id=response.data.message_id if response.data else None,
        )
    return FeishuAppResult(
        status="failed",
        target=chat_id,
        response_code=response.code,
        response_body=response.msg,
    )


def _upload_image(client: lark.Client, png: bytes) -> str:
    body = CreateImageRequestBody.builder().image_type("message").image(io.BytesIO(png)).build()
    request = CreateImageRequest.builder().request_body(body).build()
    response = client.im.v1.image.create(request)
    if not response.success() or not response.data:
        raise RuntimeError(f"飞书图片上传失败: {response.code} {response.msg}")
    return response.data.image_key


def _level_template(level: str) -> str:
    return {"crit": "red", "warn": "orange"}.get(level, "blue")


def build_alarm_card(alarm: Alarm, image_key: str | None) -> dict:
    level_text = {"crit": "严重", "warn": "警告", "info": "提示"}.get(alarm.level, alarm.level)
    subject = f"{alarm.motor_code} {alarm.motor_name}" if alarm.motor_code else alarm.device_code
    value_text = f"{alarm.value:.2f} {alarm.unit}".strip() if alarm.value is not None else "—"
    threshold_text = (
        f"{alarm.threshold:.2f} {alarm.unit}".strip() if alarm.threshold is not None else "—"
    )
    elements: list[dict] = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    f"**异常对象**：{subject}\n"
                    f"**触发值**：{value_text}     **阈值**：{threshold_text}\n"
                    f"**发生时间**：{alarm.triggered_at:%Y-%m-%d %H:%M:%S}\n"
                    f"**异常说明**：{alarm.description or '请现场检查确认'}\n"
                    f"**处理建议**：{alarm.advice or '请现场检查确认'}"
                ),
            },
        }
    ]
    if image_key:
        elements.append(
            {
                "tag": "img",
                "img_key": image_key,
                "alt": {"tag": "plain_text", "content": "电机异常时刻监测快照"},
                "mode": "fit_horizontal",
            }
        )
    elements.append(
        {
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "已解决"},
                    "type": "primary",
                    "value": {"alarm_id": alarm.id, "resolution": "resolved"},
                },
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "未解决"},
                    "type": "danger",
                    "value": {"alarm_id": alarm.id, "resolution": "unresolved"},
                },
            ],
        }
    )
    elements.append(
        {
            "tag": "note",
            "elements": [
                {
                    "tag": "plain_text",
                    "content": "请责任人在现场检查后点击按钮回传处理结果；平台只监测、只报警，不控制电机。",
                }
            ],
        }
    )
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": _level_template(alarm.level),
            "title": {
                "tag": "plain_text",
                "content": f"【{level_text}】{subject} · {alarm.title}",
            },
        },
        "elements": elements,
    }


def _load_snapshot(alarm: Alarm) -> bytes | None:
    if not alarm.motor_code:
        return None
    with SessionLocal() as db:
        motor = db.scalar(select(Motor).where(Motor.code == alarm.motor_code))
        if motor is None:
            return None
        at = as_utc(alarm.triggered_at) or utcnow()
        latest = latest_readings(db, [motor.id], until=at).get(motor.id)
        history = series_readings(db, motor.id, at - timedelta(hours=24), at)
        try:
            return render_alarm_snapshot(motor, latest, history, at)
        except Exception:
            logger.exception("生成飞书告警快照失败 alarm=%s", alarm.id)
            return None


def send_alarm_app(alarm: Alarm, config: dict) -> FeishuAppResult:
    client = _client(config)
    image_key = None
    png = _load_snapshot(alarm)
    if png:
        try:
            image_key = _upload_image(client, png)
        except Exception as exc:
            logger.warning("飞书图片上传失败，将发送纯文本卡片 alarm=%s err=%s", alarm.id, exc)
    card = build_alarm_card(alarm, image_key)
    try:
        result = _send_card(client, str(config.get("chat_id", "")), card)
    except Exception as exc:
        logger.exception("飞书应用卡片发送失败 alarm=%s", alarm.id)
        result = FeishuAppResult(
            status="failed",
            target=str(config.get("chat_id", "")),
            response_body=str(exc)[:2000],
        )
    result.image_key = image_key
    return result


def send_test_app(config: dict) -> FeishuAppResult:
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "green",
            "title": {"tag": "plain_text", "content": "【测试】MotorPulse 通知链路正常"},
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"飞书应用机器人已配置。\n"
                        f"**App ID**：{config.get('app_id', '')}\n"
                        f"**Chat ID**：{config.get('chat_id', '')}\n"
                        f"**时间**：{utcnow():%Y-%m-%d %H:%M:%S} UTC"
                    ),
                },
            },
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": "这是测试消息，收到后请在通知页面确认长连接和卡片回调配置。",
                    }
                ],
            },
        ],
    }
    try:
        return _send_card(_client(config), str(config.get("chat_id", "")), card)
    except Exception as exc:
        return FeishuAppResult(
            status="failed",
            target=str(config.get("chat_id", "")),
            response_body=str(exc)[:2000],
        )


def apply_card_action(alarm_id: int, resolution: str, operator: str) -> str:
    with SessionLocal() as db:
        alarm = db.get(Alarm, alarm_id)
        if alarm is None:
            return "告警不存在"
        now = utcnow()
        actor = f"飞书:{operator or 'unknown'}"
        if resolution == "resolved":
            if alarm.status != "closed":
                alarm.status = "closed"
                alarm.closed_at = now
                alarm.closed_by = actor
                alarm.solution = "飞书卡片回传：现场确认已解决。"
                alarm.suppressed_until = now + timedelta(minutes=settings.alarm_suppression_minutes)
            message = "已记录：异常已解决，告警已闭环"
        else:
            if alarm.status != "closed":
                alarm.status = "ack"
                alarm.last_seen_at = now
            message = "已记录：异常未解决，请继续处理"
        db.add(
            AuditLog(
                actor=actor,
                action=f"feishu_card_{resolution}",
                target=f"AL-{alarm.id:04d}",
                detail={"resolution": resolution},
            )
        )
        db.commit()
    return message
