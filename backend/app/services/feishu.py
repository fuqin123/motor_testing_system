"""飞书机器人通知（交互卡片 + 重试 + 落库）。"""

import base64
import hashlib
import hmac
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from datetime import time as dt_time

import httpx

from app.core.config import settings
from app.core.time import local_now, utcnow
from app.db.models import Alarm, NotificationLog
from app.db.session import SessionLocal
from app.services.settings import (
    get_feishu_app_config,
    get_notification_config,
    level_switch_enabled,
)

logger = logging.getLogger(__name__)

LEVEL_TEXT = {"crit": "严重", "warn": "警告", "info": "提示"}
LEVEL_TEMPLATE = {"crit": "red", "warn": "orange", "info": "blue"}


@dataclass
class NotificationResult:
    status: str
    target: str
    attempts: int = 0
    response_code: int | None = None
    response_body: str | None = None


def _parse_clock(value: str) -> dt_time:
    hour, minute = value.split(":")
    return dt_time(int(hour), int(minute))


def in_quiet_hours(config: dict, now: datetime | None = None) -> bool:
    if not config.get("quiet_hours_enabled", False):
        return False
    current = (now or local_now()).time()
    start = _parse_clock(str(config.get("quiet_start", "22:00")))
    end = _parse_clock(str(config.get("quiet_end", "06:00")))
    if start <= end:
        return start <= current < end
    return current >= start or current < end


def _sign(secret: str) -> tuple[str, str]:
    timestamp = str(int(time.time()))
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return timestamp, base64.b64encode(digest).decode("utf-8")


def build_alarm_card(alarm: Alarm, group_name: str) -> dict:
    level_text = LEVEL_TEXT.get(alarm.level, alarm.level)
    subject = f"{alarm.motor_code} {alarm.motor_name}" if alarm.motor_code else alarm.device_code
    value_text = "—"
    if alarm.value is not None:
        value_text = f"{alarm.value:.2f} {alarm.unit}".strip()
    threshold_text = "—"
    if alarm.threshold is not None:
        threshold_text = f"{alarm.threshold:.2f} {alarm.unit}".strip()
    fields = [
        {"is_short": True, "text": {"tag": "lark_md", "content": f"**监测对象**\n{subject}"}},
        {
            "is_short": True,
            "text": {"tag": "lark_md", "content": f"**当前状态**\n{alarm.status}"},
        },
        {
            "is_short": True,
            "text": {"tag": "lark_md", "content": f"**触发值**\n{value_text}"},
        },
        {
            "is_short": True,
            "text": {"tag": "lark_md", "content": f"**阈值**\n{threshold_text}"},
        },
        {
            "is_short": True,
            "text": {"tag": "lark_md", "content": f"**责任人**\n{alarm.owner}"},
        },
        {
            "is_short": True,
            "text": {"tag": "lark_md", "content": f"**时间**\n{alarm.triggered_at:%Y-%m-%d %H:%M}"},
        },
    ]
    elements: list[dict] = [
        {"tag": "div", "fields": fields},
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**异常说明**\n{alarm.description or '请现场检查确认'}",
            },
        },
    ]
    if alarm.advice:
        elements.append(
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**处理建议**\n{alarm.advice}"}}
        )
    elements.append(
        {
            "tag": "note",
            "elements": [
                {
                    "tag": "plain_text",
                    "content": f"{group_name} · 请 @{alarm.owner} 及时处理；平台只监测、只报警，不下发控制指令。",
                }
            ],
        }
    )
    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": LEVEL_TEMPLATE.get(alarm.level, "blue"),
                "title": {
                    "tag": "plain_text",
                    "content": f"【{level_text}】{subject} · {alarm.title}",
                },
            },
            "elements": elements,
        },
    }


def build_test_card(actor: str) -> dict:
    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "green",
                "title": {"tag": "plain_text", "content": "【测试】MotorPulse 通知链路正常"},
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": "**平台**\n大电机风险监测 · 试点",
                            },
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": "**链路**\nLoRa 网关 → 后台 → 飞书机器人",
                            },
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**操作人**\n{actor}",
                            },
                        },
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**时间**\n{local_now():%Y-%m-%d %H:%M:%S}",
                            },
                        },
                    ],
                }
            ],
        },
    }


def _post_card(payload: dict) -> NotificationResult:
    if not settings.feishu_configured:
        return NotificationResult(status="skipped", target="未配置飞书 Webhook")
    url = settings.feishu_webhook_url
    body = dict(payload)
    target = str(body.pop("target", ""))
    if settings.feishu_webhook_secret:
        timestamp, sign = _sign(settings.feishu_webhook_secret)
        body["timestamp"] = timestamp
        body["sign"] = sign

    last_code: int | None = None
    last_body = ""
    attempts = 0
    for attempt in range(1, settings.feishu_max_attempts + 1):
        attempts = attempt
        try:
            response = httpx.post(url, json=body, timeout=settings.feishu_timeout_seconds)
            last_code = response.status_code
            last_body = response.text[:2000]
            if response.status_code == 200:
                data = response.json()
                code = data.get("code", data.get("StatusCode", 0))
                if code == 0:
                    return NotificationResult(
                        status="sent",
                        target=target,
                        attempts=attempts,
                        response_code=last_code,
                        response_body=last_body,
                    )
            logger.warning(
                "飞书通知失败 attempt=%s status=%s body=%s", attempt, last_code, last_body
            )
        except (httpx.HTTPError, ValueError) as exc:
            last_body = str(exc)[:2000]
            logger.warning("飞书通知异常 attempt=%s err=%s", attempt, exc)
        time.sleep(min(2.0, 0.5 * attempt))
    return NotificationResult(
        status="failed",
        target=target,
        attempts=attempts,
        response_code=last_code,
        response_body=last_body,
    )


def _record_result(
    db, alarm: Alarm, result: NotificationResult, config: dict, reason: str = ""
) -> None:
    alarm.notification_status = result.status
    alarm.notification_to = result.target
    if result.status == "sent":
        alarm.notified_at = utcnow()
    db.add(
        NotificationLog(
            alarm_id=alarm.id,
            channel="feishu",
            target=result.target,
            status=result.status,
            attempts=result.attempts,
            response_code=result.response_code,
            response_body=(
                (result.response_body or reason)[:2000]
                if (result.response_body or reason)
                else None
            ),
        )
    )


def notify_alarm(alarm_id: int) -> None:
    """发送单个告警的飞书通知；网络调用在数据库事务之外完成。"""
    with SessionLocal() as db:
        alarm = db.get(Alarm, alarm_id)
        if alarm is None:
            return
        config = get_notification_config(db)
        group_name = str(config.get("group_name", "设备运维告警群"))
        alarm.notification_to = f"{group_name} · {alarm.owner}"
        app_config = get_feishu_app_config(db)
        app_ready = bool(
            app_config.get("enabled")
            and app_config.get("app_id")
            and app_config.get("app_secret")
            and app_config.get("chat_id")
        )
        if alarm.notification_status == "skipped":
            _record_result(
                db,
                alarm,
                NotificationResult(status="skipped", target=alarm.notification_to),
                config,
                reason="电机通知开关关闭",
            )
            db.commit()
            return
        if not level_switch_enabled(alarm.level, config):
            _record_result(
                db,
                alarm,
                NotificationResult(status="skipped", target=alarm.notification_to),
                config,
                reason="该级别通知开关关闭",
            )
            db.commit()
            return
        if alarm.level != "crit" and in_quiet_hours(config):
            _record_result(
                db,
                alarm,
                NotificationResult(status="skipped", target=alarm.notification_to),
                config,
                reason="夜间静默时段，严重告警不受限制",
            )
            db.commit()
            return
        if app_ready:
            from app.services.feishu_app import send_alarm_app

            result = send_alarm_app(alarm, app_config)
            if result.status != "sent" and settings.feishu_configured:
                payload = build_alarm_card(alarm, group_name)
                payload["target"] = alarm.notification_to
                fallback = _post_card(payload)
                if fallback.status == "sent":
                    logger.info("飞书应用发送失败，Webhook 回退成功 alarm=%s", alarm.id)
                    result.status = fallback.status
                    result.response_code = fallback.response_code
                    result.response_body = fallback.response_body
                    result.attempts += fallback.attempts
            _record_result(
                db,
                alarm,
                NotificationResult(
                    status=result.status,
                    target=alarm.notification_to,
                    attempts=result.attempts,
                    response_code=result.response_code,
                    response_body=result.response_body,
                ),
                config,
            )
            db.commit()
            logger.info(
                "飞书应用通知 alarm=%s status=%s image_key=%s",
                alarm.id,
                result.status,
                result.image_key,
            )
            return
        if not settings.feishu_configured:
            _record_result(
                db,
                alarm,
                NotificationResult(status="skipped", target=alarm.notification_to),
                config,
                reason="未配置飞书应用机器人或 Webhook",
            )
            db.commit()
            return
        payload = build_alarm_card(alarm, group_name)
        payload["target"] = alarm.notification_to
        result = _post_card(payload)
        _record_result(db, alarm, result, config)
        db.commit()
        logger.info(
            "告警通知 alarm=%s status=%s attempts=%s",
            alarm.id,
            result.status,
            result.attempts,
        )


def send_test_message(actor: str) -> dict:
    payload = build_test_card(actor)
    payload["target"] = "测试消息"
    result = _post_card(payload)
    with SessionLocal() as db:
        db.add(
            NotificationLog(
                alarm_id=None,
                channel="feishu",
                target="测试消息",
                status=result.status,
                attempts=result.attempts,
                response_code=result.response_code,
                response_body=result.response_body,
            )
        )
        db.commit()
    return {
        "status": result.status,
        "attempts": result.attempts,
        "response_code": result.response_code,
        "detail": "测试消息已发送" if result.status == "sent" else "测试消息未发送，请检查飞书配置",
    }
