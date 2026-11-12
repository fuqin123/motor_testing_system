from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import DateView, get_current_user, get_date_view, get_db
from app.core.security import UserContext
from app.db.models import Motor
from app.services.analysis import (
    build_peer_analysis,
    build_quadrant,
    build_self_analysis,
    build_trend,
)

router = APIRouter(tags=["对比分析"])


def _motor(db: Session, code: str) -> Motor:
    motor = db.scalar(select(Motor).where(Motor.code == code))
    if motor is None:
        raise HTTPException(status_code=404, detail=f"电机 {code} 不存在")
    return motor


@router.get("/analysis/self")
def self_analysis(
    motor_id: str = Query(..., description="电机编码，如 M-01"),
    range_key: str = Query(default="30d", alias="range"),
    view: DateView = Depends(get_date_view),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    return build_self_analysis(db, _motor(db, motor_id), range_key, now=view.as_of)


@router.get("/analysis/peers")
def peer_analysis(
    group: str | None = Query(default=None),
    view: DateView = Depends(get_date_view),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    return build_peer_analysis(db, group, now=view.as_of)


@router.get("/analysis/quadrant")
def quadrant(
    view: DateView = Depends(get_date_view),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    return build_quadrant(db, now=view.as_of)


@router.get("/analysis/trend")
def trend(
    motor_id: str = Query(..., description="电机编码，如 M-03"),
    range_key: str = Query(default="7d", alias="range"),
    view: DateView = Depends(get_date_view),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    return build_trend(db, _motor(db, motor_id), range_key, now=view.as_of)
