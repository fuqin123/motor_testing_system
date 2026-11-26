import csv
import io
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import audit, get_current_user, get_db
from app.api.serializers import (
    alarm_dict,
    alarm_response_minutes,
    latest_notification,
    notification_dict,
)
from app.core.config import settings
from app.core.security import UserContext
from app.core.time import as_utc, iso, local_day_bounds_utc, utcnow
from app.db.models import Alarm, PacketLoss, PacketLossAttempt
from app.schemas import BulkCloseRequest, CloseAlarmRequest

router = APIRouter(tags=["告警"])


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"时间格式不正确: {value}") from exc
    return as_utc(parsed)


def _filtered_query(
    level: str,
    status: str,
    q: str,
    from_time: datetime | None,
    to_time: datetime | None,
):
    query = select(Alarm)
    if level in ("crit", "warn", "info"):
        query = query.where(Alarm.level == level)
    if status in ("open", "ack", "closed"):
        query = query.where(Alarm.status == status)
    elif status == "active":
        query = query.where(Alarm.status.in_(("open", "ack")))
    if from_time:
        query = query.where(Alarm.triggered_at >= from_time)
    if to_time:
        query = query.where(Alarm.triggered_at <= to_time)
    if q.strip():
        term = q.strip()
        conditions = [
            Alarm.title.ilike(f"%{term}%"),
            Alarm.description.ilike(f"%{term}%"),
            Alarm.motor_code.ilike(f"%{term}%"),
            Alarm.motor_name.ilike(f"%{term}%"),
            Alarm.device_code.ilike(f"%{term}%"),
            Alarm.owner.ilike(f"%{term}%"),
        ]
        if term.upper().startswith("AL-") and term[3:].isdigit():
            conditions.append(Alarm.id == int(term[3:]))
        query = query.where(or_(*conditions))
    return query


@router.get("/alarms")
def list_alarms(
    level: str = Query(default="all"),
    status: str = Query(default="all"),
    q: str = Query(default=""),
    from_time: str | None = Query(default=None, alias="from"),
    to_time: str | None = Query(default=None, alias="to"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    query = _filtered_query(level, status, q, _parse_datetime(from_time), _parse_datetime(to_time))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(Alarm.triggered_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    day_start, day_end = local_day_bounds_utc()
    open_count = db.scalar(select(func.count(Alarm.id)).where(Alarm.status == "open")) or 0
    today_count = (
        db.scalar(
            select(func.count(Alarm.id)).where(
                Alarm.triggered_at >= day_start, Alarm.triggered_at < day_end
            )
        )
        or 0
    )
    closed_rows = list(
        db.scalars(
            select(Alarm).where(Alarm.status == "closed", Alarm.closed_at.is_not(None))
        ).all()
    )
    avg_response = alarm_response_minutes(closed_rows)

    return {
        "items": [alarm_dict(alarm) for alarm in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "stats": {
            "open": int(open_count),
            "today": int(today_count),
            "closed": len(closed_rows),
            "avg_response_min": avg_response,
        },
    }


@router.get("/alarms/export.csv")
def export_alarms(
    level: str = Query(default="all"),
    status: str = Query(default="all"),
    q: str = Query(default=""),
    from_time: str | None = Query(default=None, alias="from"),
    to_time: str | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> StreamingResponse:
    query = _filtered_query(level, status, q, _parse_datetime(from_time), _parse_datetime(to_time))
    rows = db.scalars(query.order_by(Alarm.triggered_at.desc())).all()
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(
        [
            "告警编号",
            "级别",
            "内容",
            "电机/设备",
            "触发值",
            "阈值",
            "触发时间",
            "飞书通知",
            "状态",
            "责任人",
            "处理结果",
        ]
    )

    def safe(value) -> str:
        text = "" if value is None else str(value)
        if text[:1] in ("=", "+", "-", "@", "\t"):
            return "'" + text
        return text

    for alarm in rows:
        writer.writerow(
            [
                f"AL-{alarm.id:04d}",
                alarm.level,
                safe(alarm.title),
                safe(
                    f"{alarm.motor_code or ''} {alarm.motor_name or alarm.device_code or ''}".strip()
                ),
                safe(f"{alarm.value:.2f} {alarm.unit}" if alarm.value is not None else ""),
                safe(f"{alarm.threshold:.2f} {alarm.unit}" if alarm.threshold is not None else ""),
                alarm.triggered_at,
                safe(f"{alarm.notification_status} {alarm.notification_to}"),
                alarm.status,
                safe(alarm.owner),
                safe(alarm.solution),
            ]
        )
    content = output.getvalue()
    filename = f"alarms_{utcnow():%Y%m%d_%H%M}.csv"
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/alarms/packet-losses")
def list_packet_losses(
    status: str = Query(default="all"),
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    query = select(PacketLoss)
    if status in ("pending", "failed", "recovered"):
        query = query.where(PacketLoss.status == status)
    term = q.strip()
    if term:
        pattern = f"%{term}%"
        query = query.where(
            or_(
                PacketLoss.gateway_code.ilike(pattern),
                PacketLoss.sensor_code.ilike(pattern),
                PacketLoss.motor_code.ilike(pattern),
                PacketLoss.error.ilike(pattern),
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = list(
        db.scalars(
            query.order_by(PacketLoss.created_at.desc(), PacketLoss.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    attempts_map = _packet_attempts(db, [row.id for row in rows])
    stats = {
        "pending": db.scalar(
            select(func.count(PacketLoss.id)).where(PacketLoss.status == "pending")
        )
        or 0,
        "failed": db.scalar(select(func.count(PacketLoss.id)).where(PacketLoss.status == "failed"))
        or 0,
        "recovered": db.scalar(
            select(func.count(PacketLoss.id)).where(PacketLoss.status == "recovered")
        )
        or 0,
    }
    return {
        "items": [_packet_loss_dict(row, attempts_map.get(row.id, [])) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "stats": stats,
        "retry_delay_minutes": settings.packet_retry_delay_minutes,
    }


def _packet_attempts(db: Session, loss_ids: list[int]) -> dict[int, list[PacketLossAttempt]]:
    if not loss_ids:
        return {}
    rows = db.scalars(
        select(PacketLossAttempt)
        .where(PacketLossAttempt.packet_loss_id.in_(loss_ids))
        .order_by(PacketLossAttempt.attempt_no, PacketLossAttempt.id)
    ).all()
    grouped: dict[int, list[PacketLossAttempt]] = {}
    for row in rows:
        grouped.setdefault(row.packet_loss_id, []).append(row)
    return grouped


def _packet_loss_dict(row: PacketLoss, attempts: list[PacketLossAttempt]) -> dict:
    log = [
        {
            "attempt_no": item.attempt_no,
            "attempted_at": iso(item.attempted_at),
            "success": bool(item.success),
            "error": item.error,
        }
        for item in attempts
    ]
    if not log:
        # 兼容迁移前的历史记录：用当前错误信息回填一条明细。
        if row.status == "recovered":
            log = [
                {
                    "attempt_no": row.attempts,
                    "attempted_at": iso(row.recovered_at or row.last_attempt_at or row.cycle_ts),
                    "success": True,
                    "error": None,
                }
            ]
        else:
            log = [
                {
                    "attempt_no": row.attempts,
                    "attempted_at": iso(row.last_attempt_at or row.cycle_ts),
                    "success": False,
                    "error": row.error,
                }
            ]
    return {
        "id": row.id,
        "cycle_ts": iso(row.cycle_ts),
        "gateway_code": row.gateway_code,
        "sensor_code": row.sensor_code,
        "motor_code": row.motor_code,
        "attempts": row.attempts,
        "max_attempts": row.max_attempts,
        "status": row.status,
        "error": row.error,
        "next_attempt_at": iso(row.next_attempt_at),
        "last_attempt_at": iso(row.last_attempt_at),
        "recovered_at": iso(row.recovered_at),
        "attempts_log": log,
    }


@router.get("/alarms/{alarm_id}")
def get_alarm(
    alarm_id: int,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    alarm = db.get(Alarm, alarm_id)
    if alarm is None:
        raise HTTPException(status_code=404, detail="告警不存在")
    payload = alarm_dict(alarm)
    log = latest_notification(db, alarm.id)
    payload["notification"] = notification_dict(log) if log else None
    return payload


@router.post("/alarms/{alarm_id}/ack")
def acknowledge_alarm(
    alarm_id: int,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    alarm = db.get(Alarm, alarm_id)
    if alarm is None:
        raise HTTPException(status_code=404, detail="告警不存在")
    if alarm.status == "closed":
        raise HTTPException(status_code=409, detail="该告警已闭环")
    if alarm.status != "ack":
        alarm.status = "ack"
        alarm.last_seen_at = utcnow()
        audit(db, user, "ack_alarm", f"AL-{alarm.id:04d}", {})
        db.commit()
    return alarm_dict(alarm)


@router.post("/alarms/{alarm_id}/close")
def close_alarm(
    alarm_id: int,
    payload: CloseAlarmRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    alarm = db.get(Alarm, alarm_id)
    if alarm is None:
        raise HTTPException(status_code=404, detail="告警不存在")
    if alarm.status == "closed":
        raise HTTPException(status_code=409, detail="该告警已闭环，不能重复处理")
    alarm.status = "closed"
    alarm.closed_at = utcnow()
    alarm.closed_by = user.name
    alarm.solution = payload.solution.strip() or "已现场检查处理，复测正常。"
    alarm.suppressed_until = utcnow() + timedelta(minutes=settings.alarm_suppression_minutes)
    audit(db, user, "close_alarm", f"AL-{alarm.id:04d}", {"solution": alarm.solution})
    db.commit()
    return alarm_dict(alarm)


@router.post("/alarms/bulk-close")
def bulk_close(
    payload: BulkCloseRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    rows = list(
        db.scalars(
            select(Alarm).where(Alarm.id.in_(payload.ids), Alarm.status.in_(("open", "ack")))
        ).all()
    )
    now = utcnow()
    for alarm in rows:
        alarm.status = "closed"
        alarm.closed_at = now
        alarm.closed_by = user.name
        alarm.solution = payload.solution.strip() or "批量闭环：已现场确认处理。"
        alarm.suppressed_until = now + timedelta(minutes=settings.alarm_suppression_minutes)
    audit(
        db,
        user,
        "bulk_close_alarms",
        ", ".join(str(item.id) for item in rows),
        {"count": len(rows)},
    )
    db.commit()
    return {"closed": len(rows), "items": [alarm_dict(alarm) for alarm in rows]}


@router.delete("/alarms/{alarm_id}")
def delete_alarm(
    alarm_id: int,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    alarm = db.get(Alarm, alarm_id)
    if alarm is None:
        raise HTTPException(status_code=404, detail="告警不存在")
    if alarm.status != "closed":
        raise HTTPException(status_code=409, detail="仅允许删除已闭环的历史告警")
    audit(db, user, "delete_alarm", f"AL-{alarm.id:04d}", {})
    db.delete(alarm)
    db.commit()
    return {"deleted": True, "id": alarm_id}
