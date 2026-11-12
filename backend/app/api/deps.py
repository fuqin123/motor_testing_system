from fastapi import HTTPException, Query
from sqlalchemy.orm import Session

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
