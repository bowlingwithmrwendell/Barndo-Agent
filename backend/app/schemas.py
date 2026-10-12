"""Pydantic request/response schemas (the JSON contract with the Android app)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import (
    AlertLevel,
    CostType,
    FeedbackStatus,
    FeedbackType,
    ProjectStatus,
    ProjectType,
)

Money = Annotated[Decimal, Field(max_digits=14, decimal_places=2)]
NonNegMoney = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Client ----------
class ClientIn(BaseModel):
    name: str | None = Field(None, max_length=200)
    company: str | None = Field(None, max_length=200)
    phone: str | None = Field(None, max_length=40)
    email: EmailStr | None = None
    site_address: str | None = Field(None, max_length=500)


class ClientOut(ORM):
    name: str | None = None
    company: str | None = None
    phone: str | None = None
    email: str | None = None
    site_address: str | None = None
    redacted: bool = False


# ---------- Project ----------
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    project_type: ProjectType = ProjectType.barndominium
    status: ProjectStatus = ProjectStatus.planning
    budget_total: NonNegMoney = Decimal("0")
    square_footage: int | None = Field(None, gt=0, le=200_000)
    start_date: date | None = None
    target_completion: date | None = None
    notes: str | None = None
    client: ClientIn | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    project_type: ProjectType | None = None
    status: ProjectStatus | None = None
    budget_total: NonNegMoney | None = None
    square_footage: int | None = Field(None, gt=0, le=200_000)
    start_date: date | None = None
    target_completion: date | None = None
    notes: str | None = None


class ProjectOut(ORM):
    id: str
    name: str
    project_type: ProjectType
    status: ProjectStatus
    budget_total: Decimal
    square_footage: int | None
    start_date: date | None
    target_completion: date | None
    notes: str | None
    storage_provider: str | None
    storage_folder_ref: str | None
    alert_level: AlertLevel
    created_at: datetime
    updated_at: datetime
    client: ClientOut | None = None


# ---------- Costs ----------
class CostCreate(BaseModel):
    id: str | None = Field(None, description="Optional client-generated UUID for idempotent offline sync")
    cost_type: CostType
    amount: NonNegMoney
    description: str = Field("", max_length=500)
    phase: str | None = Field(None, max_length=60)
    vendor: str | None = Field(None, max_length=200)
    incurred_on: date | None = None

    @field_validator("id")
    @classmethod
    def _uuid_shape(cls, v):
        if v is not None:
            import uuid

            uuid.UUID(v)
        return v


class CostUpdate(BaseModel):
    cost_type: CostType | None = None
    amount: NonNegMoney | None = None
    description: str | None = Field(None, max_length=500)
    phase: str | None = Field(None, max_length=60)
    vendor: str | None = Field(None, max_length=200)
    incurred_on: date | None = None


class CostOut(ORM):
    id: str
    project_id: str
    cost_type: CostType
    amount: Decimal
    description: str
    phase: str | None
    vendor: str | None
    incurred_on: date | None
    created_at: datetime
    updated_at: datetime


# ---------- Budget ----------
class BudgetSummaryOut(BaseModel):
    project_id: str
    budget_total: Decimal
    actual_invoices: Decimal
    actual_labor: Decimal
    actual_materials: Decimal
    actual_total: Decimal
    committed_purchase_orders: Decimal
    committed_unbilled_subcontracts: Decimal
    committed_total: Decimal
    remaining_estimated: Decimal
    projected_total: Decimal
    cost_variance: Decimal
    burn_rate_pct: Decimal | None
    remaining_budget: Decimal
    alert_level: AlertLevel
    alert_reasons: list[str]
    by_phase: dict[str, Decimal]


class AlertEventOut(ORM):
    id: str
    project_id: str
    previous_level: AlertLevel
    level: AlertLevel
    burn_rate_pct: Decimal | None
    cost_variance: Decimal
    reasons: str
    created_at: datetime


# ---------- Dashboard ----------
class DashboardProject(BaseModel):
    id: str
    name: str
    project_type: ProjectType
    status: ProjectStatus
    budget_total: Decimal
    projected_total: Decimal
    burn_rate_pct: Decimal | None
    cost_variance: Decimal
    alert_level: AlertLevel
    updated_at: datetime


class DashboardOut(BaseModel):
    project_count: int
    active_count: int
    warning_count: int
    critical_count: int
    projects: list[DashboardProject]
    recent_alerts: list[AlertEventOut]


# ---------- Feedback ----------
class FeedbackCreate(BaseModel):
    feedback_type: FeedbackType
    message: str = Field(min_length=3, max_length=5000)
    severity: str | None = Field(None, pattern="^(low|medium|high|blocker)$")
    screen: str | None = Field(None, max_length=100)
    app_version: str | None = Field(None, max_length=40)
    device_info: str | None = Field(None, max_length=200)
    project_id: str | None = None


class FeedbackUpdate(BaseModel):
    status: FeedbackStatus


class FeedbackOut(ORM):
    id: str
    feedback_type: FeedbackType
    message: str
    severity: str | None
    screen: str | None
    app_version: str | None
    device_info: str | None
    project_id: str | None
    status: FeedbackStatus
    created_at: datetime
    updated_at: datetime


class FeedbackStats(BaseModel):
    total: int
    by_type: dict[str, int]
    by_status: dict[str, int]


# ---------- Storage ----------
class StorageProvisionOut(BaseModel):
    provider: str
    folder_ref: str
    folder_name: str
    subfolders: list[str]
