"""验收指标计算：可自动核验的项自动判定，其余标注人工确认。"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import as_utc, iso, local_now, utcnow
from app.db.models import Alarm, Motor, Reading


def build_acceptance(db: Session) -> list[dict]:
    start_local = local_now()
    try:
        year, month, day = (int(part) for part in settings.pilot_start_date.split("-"))
        pilot_start = datetime(year, month, day, tzinfo=start_local.tzinfo)
    except ValueError:
        pilot_start = start_local - timedelta(days=settings.pilot_days)
    pilot_start_utc = pilot_start.astimezone(timezone.utc)

    notified = list(
        db.scalars(
            select(Alarm).where(
                Alarm.notified_at.is_not(None),
                Alarm.triggered_at >= pilot_start_utc,
            )
        ).all()
    )
    latencies = []
    for alarm in notified:
        triggered = as_utc(alarm.triggered_at)
        notified_at = as_utc(alarm.notified_at)
        if triggered and notified_at:
            latencies.append((notified_at - triggered).total_seconds())
    if latencies:
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        latency_item = {
            "key": "notify_latency",
            "label": "异常发现到飞书通知 ≤ 1 分钟",
            "status": "pass" if max_latency <= 60 else "fail",
            "detail": f"平均 {avg_latency:.1f} 秒 / 最大 {max_latency:.1f} 秒（{len(latencies)} 条已通知告警）",
        }
    else:
        latency_item = {
            "key": "notify_latency",
            "label": "异常发现到飞书通知 ≤ 1 分钟",
            "status": "pending",
            "detail": "试点期尚无已发送的飞书告警，待产生告警后核验",
        }

    now = utcnow()
    day_ago = now - timedelta(days=1)
    motor_count = db.scalar(select(func.count(Motor.id)).where(Motor.enabled.is_(True))) or 0
    readings_24h = (
        db.scalar(
            select(func.count(Reading.id)).where(Reading.ts >= day_ago, Reading.quality != "error")
        )
        or 0
    )
    expected = motor_count * int(24 * 60 / settings.poll_interval_minutes)
    completeness = (readings_24h / expected * 100) if expected else 0
    completeness_item = {
        "key": "completeness",
        "label": "近 24 小时采集完整率 ≥ 95%",
        "status": "pass" if completeness >= 95 else ("fail" if expected else "pending"),
        "detail": f"{readings_24h}/{expected} 条 · {completeness:.1f}%",
    }

    return [
        latency_item,
        completeness_item,
        {
            "key": "downtime",
            "label": "试点期非计划停机 0 次",
            "status": "manual",
            "detail": "由设备科/生产科按月确认停机记录，平台不控制电机，仅提供监测证据",
        },
        {
            "key": "accuracy",
            "label": "告警准确率 ≥ 90%",
            "status": "manual",
            "detail": "需结合人工复核结果统计误报数，建议每月复盘一次",
        },
        {
            "key": "report",
            "label": "验收报告与推广方案",
            "status": "pending",
            "detail": f"试点第 {max(1, (local_now().date() - pilot_start.date()).days + 1)} 天，报告按计划提交",
        },
    ]


def acceptance_snapshot(db: Session) -> dict:
    items = build_acceptance(db)
    return {
        "items": items,
        "generated_at": iso(utcnow()),
        "pass_count": sum(1 for item in items if item["status"] == "pass"),
        "total_auto": sum(1 for item in items if item["status"] in ("pass", "fail", "pending")),
    }
