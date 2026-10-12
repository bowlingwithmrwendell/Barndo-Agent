"""Shared business logic used by the routers."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app import budget
from app.config import get_settings
from app.models import AlertEvent, Project
from app.schemas import BudgetSummaryOut, ClientOut


def get_project_or_404(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


def compute_summary(project: Project) -> budget.BudgetSummary:
    s = get_settings()
    lines = [budget.CostLine(c.cost_type, c.amount, c.phase) for c in project.costs]
    return budget.summarize(project.budget_total, lines, s.budget_warning_pct, s.budget_critical_pct)


def summary_out(project: Project, summary: budget.BudgetSummary) -> BudgetSummaryOut:
    return BudgetSummaryOut(project_id=project.id, **summary.__dict__)


def refresh_alert(db: Session, project: Project) -> budget.BudgetSummary:
    """Recompute the budget and log an AlertEvent if the level changed.

    Call after any change to the budget total or cost entries (before commit).
    """
    db.flush()
    db.refresh(project, attribute_names=["costs"])
    summary = compute_summary(project)
    if summary.alert_level != project.alert_level:
        db.add(
            AlertEvent(
                project_id=project.id,
                previous_level=project.alert_level,
                level=summary.alert_level,
                burn_rate_pct=summary.burn_rate_pct,
                cost_variance=summary.cost_variance,
                reasons="; ".join(summary.alert_reasons),
            )
        )
        project.alert_level = summary.alert_level
    return summary


def client_out(project: Project, can_see_pii: bool) -> ClientOut | None:
    c = project.client
    if c is None:
        return None
    if not can_see_pii:
        return ClientOut(
            name=_mask(c.name),
            company=c.company,  # business name is not personal data; kept for context
            phone=_mask(c.phone, keep=2),
            email=None,
            site_address=None,
            redacted=True,
        )
    return ClientOut.model_validate(c)


def _mask(value: str | None, keep: int = 1) -> str | None:
    if not value:
        return None
    return value[:keep] + "•" * max(len(value) - keep, 3)
