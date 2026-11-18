from datetime import datetime

from fastapi import HTTPException, Query
from sqlalchemy.orm import Session

from app.core.time import as_utc

from app.core.security import UserContext, get_current_user
from app.db.models import AuditLog
from app.db.session import get_db
from app.services.date_view import DateView, resolve_date_view

__all__ = [
    "AuditLog",
    "DateView",
    "Session",
    "UserContext",
    "audit",
    "get_current_user",
    "get_date_view",
    "get_at_time",
    "get_db",
]


def get_date_view(
    date: str | None = Query(
        default=None,
        description="历史日期 YYYY-MM-DD；省略时查看今天/实时",
    )
) -> DateView:
    try:
        return resolve_date_view(date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def get_at_time(
    at: str | None = Query(
        default=None,
        description="精确时刻 ISO 8601，用于点击趋势点查看该时刻详情",
    )
) -> datetime | None:
    if not at:
        return None
    try:
        value = datetime.fromisoformat(at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="at 时间格式应为 ISO 8601") from exc
    result = as_utc(value)
    if result is None:
        raise HTTPException(status_code=422, detail="at 时间格式应为 ISO 8601")
    return result


def audit(
    db: Session,
    actor: UserContext | str,
    action: str,
    target: str,
    detail: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            actor=actor.name if isinstance(actor, UserContext) else actor,
            action=action,
            target=target,
            detail=detail or {},
        )
    )
