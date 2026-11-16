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


def _friendly_error(exc: Exception) -> str:
    text = str(exc)
    if "app_id is invalid" in text:
        return "飞书应用 ID 或密钥无效，请检查应用凭据"
    if "event loop" in text.lower():
        return "长连接事件循环异常，请重启后端服务"
    return text[:255]


class FeishuLongConnection(threading.Thread):
    def __init__(self, config: dict, last_event_at: str | None = None) -> None:
        super().__init__(name="feishu-long-connection", daemon=True)
        self.config = dict(config)
        self._signature = self._config_signature(config)
        self._status = {
            "running": False,
            "app_id": config.get("app_id", ""),
            "last_event_at": last_event_at,
            "last_error": None,
            "restart_required": False,
        }
        self._handler = None
        self._client = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()
        self._stopping = threading.Event()

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
                    {"toast": {"type": "error", "content": "飞书应用已停用或已更换，请在后端重新保存配置"}}
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
        self._loop = loop
        self._ready.set()
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
            if not self._stopping.is_set():
                logger.exception("飞书长连接异常")
                self._status["last_error"] = _friendly_error(exc)
        finally:
            self._status["running"] = False
            self._loop = None
            self._ready.set()
            try:
                loop.close()
            except Exception:
                pass

    def stop(self, timeout: float = 6.0) -> bool:
        """主动断开并结束长连接线程，用于前端切换应用配置。"""
        self._stopping.set()
        if not self._ready.wait(timeout=2.0):
            logger.warning("飞书长连接尚未启动，跳过事件循环停止")
        loop = self._loop
        client = self._client
        try:
            if loop is not None and not loop.is_closed() and loop.is_running():
                disconnect = getattr(client, "_disconnect", None)
                if disconnect is not None:
                    try:
                        future = asyncio.run_coroutine_threadsafe(disconnect(), loop)
                        future.result(timeout=3.0)
                    except Exception as exc:
                        logger.warning("飞书长连接断开异常: %s", exc)

                def cancel_and_stop() -> None:
                    for task in asyncio.all_tasks(loop):
                        task.cancel()
                    loop.stop()

                loop.call_soon_threadsafe(cancel_and_stop)
        except RuntimeError as exc:
            logger.warning("飞书长连接事件循环已关闭: %s", exc)
        self.join(timeout=timeout)
        if self.is_alive():
            logger.warning("飞书长连接线程未在超时内退出")
            return False
        self._status["running"] = False
        return True

    def status(self) -> dict:
        return dict(self._status)


def ensure_connection(config: dict) -> dict:
    global _connection
    enabled = bool(config.get("enabled"))
    app_id = str(config.get("app_id", ""))
    secret = str(config.get("app_secret", ""))
    chat_id = str(config.get("chat_id", ""))
    ready = bool(enabled and app_id and secret and chat_id)
    with _lock:
        previous = _connection.status() if _connection else {}
        if _connection is not None:
            if ready and _connection.is_alive() and _connection.matches(config):
                return _connection.status()
            if _connection.is_alive():
                logger.info("飞书应用配置变更，正在重建长连接")
                if not _connection.stop():
                    status = _connection.status()
                    status["restart_required"] = True
                    status["last_error"] = "旧长连接未能停止，请重启后端服务"
                    return status
        _connection = None
        if not ready:
            return {
                "running": False,
                "app_id": app_id,
                "last_event_at": previous.get("last_event_at"),
                "last_error": "飞书应用未启用或凭据不完整",
                "restart_required": False,
            }
        _connection = FeishuLongConnection(config, last_event_at=previous.get("last_event_at"))
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
