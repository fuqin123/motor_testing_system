"""飞书官方 SDK WebSocket 长连接，订阅卡片回传交互。"""

import asyncio
import hashlib
import json
import logging
import threading

import lark_oapi as lark
from lark_oapi.event.callback.model.p2_card_action_trigger import (
    P2CardActionTrigger,
    P2CardActionTriggerResponse,
)
from lark_oapi.ws import client as ws_client_module

from app.db.session import SessionLocal
from app.services.feishu_app import apply_card_action
from app.services.settings import get_feishu_app_config

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_connection: "FeishuLongConnection | None" = None


class FeishuLongConnection(threading.Thread):
    def __init__(self, config: dict) -> None:
        super().__init__(name="feishu-long-connection", daemon=True)
        self.config = dict(config)
        self._signature = self._config_signature(config)
        self._status = {
            "running": False,
            "app_id": config.get("app_id", ""),
            "last_event_at": None,
            "last_error": None,
            "restart_required": False,
        }
        self._handler = None
        self._client = None

    @staticmethod
    def _config_signature(config: dict) -> str:
        raw = f"{config.get('app_id', '')}:{config.get('app_secret', '')}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def matches(self, config: dict) -> bool:
        return self._signature == self._config_signature(config)

    def _card_action(self, data: P2CardActionTrigger) -> P2CardActionTriggerResponse:
        from app.core.time import iso, utcnow

        message = "已收到回传"
        try:
            with SessionLocal() as db:
                current = get_feishu_app_config(db)
            if not current.get("enabled") or current.get("app_id") != self.config.get("app_id"):
                return P2CardActionTriggerResponse(
                    {"toast": {"type": "error", "content": "飞书应用已停用或已更换，请重启后台"}}
                )
            event = data.event
            value = event.action.value if event and event.action else {}
            if isinstance(value, str):
                value = json.loads(value)
            value = value or {}
            alarm_id = int(value.get("alarm_id"))
            resolution = str(value.get("resolution", "unresolved"))
            operator = ""
            if event and event.operator:
                operator = event.operator.open_id or event.operator.user_id or ""
            message = apply_card_action(alarm_id, resolution, operator)
            self._status["last_event_at"] = iso(utcnow())
            logger.info(
                "收到飞书卡片回调 alarm=%s resolution=%s operator=%s",
                alarm_id,
                resolution,
                operator,
            )
        except Exception as exc:
            logger.exception("处理飞书卡片回调失败")
            self._status["last_error"] = str(exc)[:255]
            message = "处理失败，请查看后台日志"
        return P2CardActionTriggerResponse(
            {"toast": {"type": "success" if "失败" not in message else "error", "content": message}}
        )

    def run(self) -> None:
        self._status["running"] = True
        self._status["last_error"] = None
        # lark-oapi ws.Client 使用模块级事件循环；在 API 进程内会拿到 uvicorn
        # 正在运行的循环。必须给长连接线程单独创建循环，否则 start() 直接报
        # "This event loop is already running"。
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        ws_client_module.loop = loop
        try:
            dispatcher = (
                lark.EventDispatcherHandler.builder("", "")
                .register_p2_card_action_trigger(self._card_action)
                .build()
            )
            self._client = lark.ws.Client(
                str(self.config.get("app_id", "")),
                str(self.config.get("app_secret", "")),
                event_handler=dispatcher,
                log_level=lark.LogLevel.INFO,
            )
            self._client.start()
        except Exception as exc:
            logger.exception("飞书长连接异常")
            self._status["last_error"] = str(exc)[:255]
        finally:
            self._status["running"] = False
            try:
                loop.close()
            except Exception:
                pass

    def status(self) -> dict:
        return dict(self._status)


def ensure_connection(config: dict) -> dict:
    global _connection
    enabled = bool(config.get("enabled"))
    app_id = str(config.get("app_id", ""))
    secret = str(config.get("app_secret", ""))
    chat_id = str(config.get("chat_id", ""))
    if not (enabled and app_id and secret and chat_id):
        with _lock:
            if _connection and _connection.is_alive():
                status = _connection.status()
                status["restart_required"] = True
                status["last_error"] = "飞书应用已停用，请重启 backend 断开长连接"
                return status
        return {
            "running": False,
            "app_id": app_id,
            "last_event_at": None,
            "last_error": "飞书应用未启用或凭据不完整",
            "restart_required": False,
        }
    with _lock:
        if _connection and _connection.is_alive():
            status = _connection.status()
            if status.get("app_id") == app_id and _connection.matches(config):
                return status
            status["restart_required"] = True
            status["last_error"] = "飞书应用凭据已变更，请重启 backend 以重建长连接"
            return status
        _connection = FeishuLongConnection(config)
        _connection.start()
        return _connection.status()


def connection_status() -> dict:
    if _connection and _connection.is_alive():
        return _connection.status()
    return {
        "running": False,
        "app_id": _connection.config.get("app_id", "") if _connection else "",
        "last_event_at": _connection.status().get("last_event_at") if _connection else None,
        "last_error": _connection.status().get("last_error") if _connection else None,
        "restart_required": False,
    }


def ensure_connection_from_db() -> dict:
    with SessionLocal() as db:
        config = get_feishu_app_config(db)
    return ensure_connection(config)
