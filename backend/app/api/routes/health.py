from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import iso, utcnow
from app.db.session import get_db

router = APIRouter(tags=["健康检查"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "service": "motor-monitor-api",
        "version": settings.app_version,
        "time": iso(utcnow()),
    }
