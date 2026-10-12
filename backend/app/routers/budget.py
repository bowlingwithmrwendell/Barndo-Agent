from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AlertEvent, AlertLevel, CostEntry, CostType, Project
from app.schemas import (
    AlertEventOut,
    BudgetSummaryOut,
    CostCreate,
    CostOut,
    CostUpdate,
    DashboardOut,
    DashboardProject,
)
from app.security import Principal, require
from app.services import compute_summary, get_project_or_404, refresh_alert, summary_out

router = APIRouter(tags=["budget"])

# Field crews log what was spent on site; forecasting entries need a manager.
FIELD_ALLOWED = {CostType.invoice, CostType.labor, CostType.material}


def _check_type_allowed(principal: Principal, cost_type: CostType) -> None:
    if not principal.at_least("manager") and cost_type not in FIELD_ALLOWED:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, f"Role '{principal.role}' cannot log '{cost_type.value}' entries"
        )


@router.get("/projects/{project_id}/budget", response_model=BudgetSummaryOut)
def budget_summary(project_id: str, db: Session = Depends(get_db), _: Principal = Depends(require("viewer"))):
    project = get_project_or_404(db, project_id)
    return summary_out(project, compute_summary(project))


@router.get("/projects/{project_id}/costs", response_model=list[CostOut])
def list_costs(
    project_id: str,
    cost_type: CostType | None = None,
    phase: str | None = None,
    updated_since: datetime | None = None,
    db: Session = Depends(get_db),
    _: Principal = Depends(require("viewer")),
):
    get_project_or_404(db, project_id)
    stmt = select(CostEntry).where(CostEntry.project_id == project_id).order_by(CostEntry.created_at)
    if cost_type:
        stmt = stmt.where(CostEntry.cost_type == cost_type)
    if phase:
        stmt = stmt.where(CostEntry.phase == phase)
    if updated_since:
        stmt = stmt.where(CostEntry.updated_at > updated_since)
    return list(db.scalars(stmt))


@router.post("/projects/{project_id}/costs", response_model=CostOut, status_code=status.HTTP_201_CREATED)
def add_cost(
    project_id: str,
    body: CostCreate,
    response: Response,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require("field")),
):
    project = get_project_or_404(db, project_id)
    _check_type_allowed(principal, body.cost_type)

    # Idempotent replay from the app's offline queue.
    if body.id:
        existing = db.get(CostEntry, body.id)
        if existing is not None:
            if existing.project_id != project_id:
                raise HTTPException(status.HTTP_409_CONFLICT, "Cost id already used by another project")
            response.status_code = status.HTTP_200_OK
            return existing

    data = body.model_dump(exclude_none=True)
    entry = CostEntry(project_id=project.id, created_by_role=principal.role, **data)
    db.add(entry)
    refresh_alert(db, project)
    db.commit()
    return entry


@router.patch("/projects/{project_id}/costs/{cost_id}", response_model=CostOut)
def update_cost(
    project_id: str,
    cost_id: str,
    body: CostUpdate,
    db: Session = Depends(get_db),
    _: Principal = Depends(require("manager")),
):
    project = get_project_or_404(db, project_id)
    entry = db.get(CostEntry, cost_id)
    if entry is None or entry.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cost entry not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        if k in {"cost_type", "amount"} and v is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"'{k}' cannot be null")
        setattr(entry, k, v)
    refresh_alert(db, project)
    db.commit()
    return entry


@router.delete("/projects/{project_id}/costs/{cost_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cost(
    project_id: str,
    cost_id: str,
    db: Session = Depends(get_db),
    _: Principal = Depends(require("manager")),
):
    project = get_project_or_404(db, project_id)
    entry = db.get(CostEntry, cost_id)
    if entry is None or entry.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cost entry not found")
    db.delete(entry)
    refresh_alert(db, project)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/projects/{project_id}/alerts", response_model=list[AlertEventOut])
def project_alerts(project_id: str, db: Session = Depends(get_db), _: Principal = Depends(require("viewer"))):
    get_project_or_404(db, project_id)
    stmt = select(AlertEvent).where(AlertEvent.project_id == project_id).order_by(AlertEvent.created_at.desc())
    return list(db.scalars(stmt))


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    recent: int = Query(10, ge=0, le=100),
    db: Session = Depends(get_db),
    _: Principal = Depends(require("viewer")),
):
    projects = list(db.scalars(select(Project).order_by(Project.updated_at.desc())))
    rows = []
    for p in projects:
        s = compute_summary(p)
        rows.append(
            DashboardProject(
                id=p.id,
                name=p.name,
                project_type=p.project_type,
                status=p.status,
                budget_total=s.budget_total,
                projected_total=s.projected_total,
                burn_rate_pct=s.burn_rate_pct,
                cost_variance=s.cost_variance,
                alert_level=s.alert_level,
                updated_at=p.updated_at,
            )
        )
    alerts = list(db.scalars(select(AlertEvent).order_by(AlertEvent.created_at.desc()).limit(recent)))
    return DashboardOut(
        project_count=len(rows),
        active_count=sum(1 for r in rows if r.status.value == "active"),
        warning_count=sum(1 for r in rows if r.alert_level is AlertLevel.warning),
        critical_count=sum(1 for r in rows if r.alert_level is AlertLevel.critical),
        projects=rows,
        recent_alerts=alerts,
    )
