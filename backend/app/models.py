"""SQLAlchemy ORM models."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    TypeDecorator,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app import crypto
from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class EncryptedString(TypeDecorator):
    """Transparently AES-256-GCM encrypts a string column at rest."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None or value == "":
            return None
        return crypto.encrypt(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return crypto.decrypt(value)


class ProjectType(enum.StrEnum):
    barndominium = "barndominium"
    traditional_home = "traditional_home"
    remodel = "remodel"
    commercial = "commercial"
    other = "other"


class ProjectStatus(enum.StrEnum):
    planning = "planning"
    active = "active"
    on_hold = "on_hold"
    complete = "complete"
    cancelled = "cancelled"


class CostType(enum.StrEnum):
    # Actual expenditures (E_actual)
    invoice = "invoice"
    labor = "labor"
    material = "material"
    # Committed costs (C_committed)
    purchase_order = "purchase_order"
    unbilled_subcontract = "unbilled_subcontract"
    # Remaining estimated costs (part of P_total)
    remaining_estimate = "remaining_estimate"


ACTUAL_TYPES = {CostType.invoice, CostType.labor, CostType.material}
COMMITTED_TYPES = {CostType.purchase_order, CostType.unbilled_subcontract}


class AlertLevel(enum.StrEnum):
    none = "none"
    warning = "warning"
    critical = "critical"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    project_type: Mapped[ProjectType] = mapped_column(
        Enum(ProjectType, native_enum=False), default=ProjectType.barndominium
    )
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, native_enum=False), default=ProjectStatus.planning
    )
    budget_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    square_footage: Mapped[int | None] = mapped_column(nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_completion: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Cloud storage folder reference, set by /storage/provision
    storage_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    storage_folder_ref: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Last computed alert level, so changes can be logged as AlertEvents
    alert_level: Mapped[AlertLevel] = mapped_column(Enum(AlertLevel, native_enum=False), default=AlertLevel.none)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    client: Mapped[Client | None] = relationship(back_populates="project", uselist=False, cascade="all, delete-orphan")
    costs: Mapped[list[CostEntry]] = relationship(back_populates="project", cascade="all, delete-orphan")
    alerts: Mapped[list[AlertEvent]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Client(Base):
    """Optional client metadata. Every PII field is encrypted at rest."""

    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), unique=True)
    name: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    company: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    phone: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    email: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    site_address: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    project: Mapped[Project] = relationship(back_populates="client")


class CostEntry(Base):
    __tablename__ = "cost_entries"

    # The mobile app may supply its own UUID so replaying the offline queue is idempotent.
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    cost_type: Mapped[CostType] = mapped_column(Enum(CostType, native_enum=False))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    description: Mapped[str] = mapped_column(String(500), default="")
    phase: Mapped[str | None] = mapped_column(String(60), nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    incurred_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    project: Mapped[Project] = relationship(back_populates="costs")


class AlertEvent(Base):
    """Logged whenever a project's budget alert level changes."""

    __tablename__ = "alert_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    previous_level: Mapped[AlertLevel] = mapped_column(Enum(AlertLevel, native_enum=False))
    level: Mapped[AlertLevel] = mapped_column(Enum(AlertLevel, native_enum=False))
    burn_rate_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    cost_variance: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    reasons: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    project: Mapped[Project] = relationship(back_populates="alerts")


class FeedbackType(enum.StrEnum):
    bug = "bug"
    usability = "usability"
    feature_request = "feature_request"
    other = "other"


class FeedbackStatus(enum.StrEnum):
    new = "new"
    triaged = "triaged"
    in_progress = "in_progress"
    resolved = "resolved"
    wont_fix = "wont_fix"


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    feedback_type: Mapped[FeedbackType] = mapped_column(Enum(FeedbackType, native_enum=False))
    message: Mapped[str] = mapped_column(Text)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    screen: Mapped[str | None] = mapped_column(String(100), nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    device_info: Mapped[str | None] = mapped_column(String(200), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[FeedbackStatus] = mapped_column(Enum(FeedbackStatus, native_enum=False), default=FeedbackStatus.new)
    submitted_by_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
