from sqlalchemy.orm import Session

from app.core.security import UserContext, get_current_user
from app.db.models import AuditLog
from app.db.session import get_db

__all__ = ["AuditLog", "Session", "UserContext", "audit", "get_current_user", "get_db"]


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
