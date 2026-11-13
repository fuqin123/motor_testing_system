from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Gateway(TimestampMixin, Base):
    __tablename__ = "gateways"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    host: Mapped[str] = mapped_column(String(64))
    port: Mapped[int] = mapped_column(Integer, default=502)
    framer: Mapped[str] = mapped_column(String(8), default="rtu")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    model: Mapped[str] = mapped_column(String(64), default="LoRa 网关")
    firmware: Mapped[str] = mapped_column(String(32), default="—")
    note: Mapped[str] = mapped_column(String(255), default="")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)

    sensors: Mapped[list["Sensor"]] = relationship(back_populates="gateway")


class Motor(TimestampMixin, Base):
    __tablename__ = "motors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    location: Mapped[str] = mapped_column(String(128), default="")
    group_name: Mapped[str] = mapped_column(String(64), default="未分组")
    rated_kw: Mapped[float] = mapped_column(Float, default=0.0)
    rated_current_a: Mapped[float] = mapped_column(Float, default=0.0)
    pilot: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    node_code: Mapped[str] = mapped_column(String(32), default="N-01")
    vfd_model: Mapped[str] = mapped_column(String(64), default="")
    install_date: Mapped[str] = mapped_column(String(16), default="")
    last_maintenance: Mapped[str] = mapped_column(String(64), default="")
    notes: Mapped[str] = mapped_column(Text, default="")

    temp_limit_c: Mapped[float] = mapped_column(Float, default=85.0)
    current_limit_a: Mapped[float] = mapped_column(Float, default=0.0)
    temp_deviation_pct: Mapped[float] = mapped_column(Float, default=8.0)
    current_deviation_pct: Mapped[float] = mapped_column(Float, default=10.0)
    phase_imbalance_pct: Mapped[float] = mapped_column(Float, default=10.0)
    vibration_limit_mm_s: Mapped[float] = mapped_column(Float, default=4.5)
    rise_rate_limit_c_per_day: Mapped[float] = mapped_column(Float, default=1.0)
    notify_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    sensors: Mapped[list["Sensor"]] = relationship(
        back_populates="motor", cascade="all, delete-orphan"
    )
    readings: Mapped[list["Reading"]] = relationship(
        back_populates="motor", cascade="all, delete-orphan"
    )


class Sensor(TimestampMixin, Base):
    __tablename__ = "sensors"
    __table_args__ = (UniqueConstraint("motor_id", "kind", name="uq_sensor_motor_kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    motor_id: Mapped[int] = mapped_column(ForeignKey("motors.id", ondelete="CASCADE"), index=True)
    gateway_id: Mapped[int] = mapped_column(
        ForeignKey("gateways.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(16), default="temperature")
    name: Mapped[str] = mapped_column(String(128), default="")
    slave_id: Mapped[int] = mapped_column(Integer, default=1)
    register_address: Mapped[int] = mapped_column(Integer, default=0)
    register_count: Mapped[int] = mapped_column(Integer, default=1)
    scale: Mapped[float] = mapped_column(Float, default=0.1)
    unit: Mapped[str] = mapped_column(String(8), default="℃")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    power_type: Mapped[str] = mapped_column(String(16), default="市电供电")
    firmware: Mapped[str] = mapped_column(String(32), default="—")
    signal_dbm: Mapped[float | None] = mapped_column(Float, nullable=True)
    snr_db: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)

    motor: Mapped["Motor"] = relationship(back_populates="sensors")
    gateway: Mapped["Gateway"] = relationship(back_populates="sensors")


class Reading(Base):
    __tablename__ = "readings"
    __table_args__ = (
        UniqueConstraint("motor_id", "ts", name="uq_reading_motor_ts"),
        Index("ix_readings_motor_ts", "motor_id", "ts"),
        Index("ix_readings_ts", "ts"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    motor_id: Mapped[int] = mapped_column(ForeignKey("motors.id", ondelete="CASCADE"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_a: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_b: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_avg_a: Mapped[float | None] = mapped_column(Float, nullable=True)
    vibration_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    vibration_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    vibration_z: Mapped[float | None] = mapped_column(Float, nullable=True)
    vibration_total_mm_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality: Mapped[str] = mapped_column(String(16), default="ok")
    raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    motor: Mapped["Motor"] = relationship(back_populates="readings")


class Alarm(Base):
    __tablename__ = "alarms"
    __table_args__ = (
        Index("ix_alarms_status_triggered", "status", "triggered_at"),
        Index("ix_alarms_motor_code", "motor_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String(8), default="warn")
    rule_key: Mapped[str] = mapped_column(String(32), default="")
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    advice: Mapped[str] = mapped_column(Text, default="")
    motor_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    motor_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    device_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    metric: Mapped[str] = mapped_column(String(32), default="")
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(8), default="")
    status: Mapped[str] = mapped_column(String(8), default="open")
    owner: Mapped[str] = mapped_column(String(64), default="")
    notification_status: Mapped[str] = mapped_column(String(16), default="pending")
    notification_to: Mapped[str] = mapped_column(String(128), default="")
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    solution: Mapped[str | None] = mapped_column(Text, nullable=True)
    suppressed_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    normal_count: Mapped[int] = mapped_column(Integer, default=0)
    dedup_key: Mapped[str] = mapped_column(String(96), index=True, default="")

    notifications: Mapped[list["NotificationLog"]] = relationship(
        back_populates="alarm", cascade="all, delete-orphan"
    )


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alarm_id: Mapped[int | None] = mapped_column(
        ForeignKey("alarms.id", ondelete="CASCADE"), nullable=True, index=True
    )
    channel: Mapped[str] = mapped_column(String(16), default="feishu")
    target: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    alarm: Mapped["Alarm"] = relationship(back_populates="notifications")


class PollCycle(Base):
    __tablename__ = "poll_cycles"
    __table_args__ = (Index("ix_poll_cycles_started", "started_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gateway_code: Mapped[str] = mapped_column(String(32), default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    successes: Mapped[int] = mapped_column(Integer, default=0)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String(255), nullable=True)


class AppConfig(Base):
    __tablename__ = "app_configs"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    updated_by: Mapped[str] = mapped_column(String(64), default="system")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(64), default="system")
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(String(128), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
