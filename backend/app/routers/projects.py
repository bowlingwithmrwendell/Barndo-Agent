from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Client, Project, ProjectStatus
from app.schemas import (
    ClientIn,
    ClientOut,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    StorageProvisionOut,
)
from app.security import Principal, require
from app.services import client_out, get_project_or_404, refresh_alert
from app.storage import get_provider

router = APIRouter(prefix="/projects", tags=["projects"])


def _out(project: Project, principal: Principal) -> ProjectOut:
    data = ProjectOut.model_validate(project, from_attributes=True).model_dump(exclude={"client"})
    return ProjectOut(**data, client=client_out(project, principal.at_least("manager")))


@router.get("", response_model=list[ProjectOut])
def list_projects(
    status_: ProjectStatus | None = Query(None, alias="status"),
    updated_since: datetime | None = Query(None, description="For offline sync: only projects changed after this time"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(require("viewer")),
):
    stmt = select(Project).order_by(Project.updated_at.desc())
    if status_:
        stmt = stmt.where(Project.status == status_)
    if updated_since:
        stmt = stmt.where(Project.updated_at > updated_since)
    return [_out(p, principal) for p in db.scalars(stmt)]


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require("manager")),
):
    data = body.model_dump(exclude={"client"})
    project = Project(**data)
    if body.client and any(body.client.model_dump().values()):
        project.client = Client(**body.client.model_dump())
    db.add(project)
    refresh_alert(db, project)
    db.commit()
    return _out(project, principal)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db), principal: Principal = Depends(require("viewer"))):
    return _out(get_project_or_404(db, project_id), principal)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: str,
    body: ProjectUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require("manager")),
):
    project = get_project_or_404(db, project_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        if k in {"name", "project_type", "status", "budget_total"} and v is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"'{k}' cannot be null")
        setattr(project, k, v)
    refresh_alert(db, project)
    db.commit()
    return _out(project, principal)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, db: Session = Depends(get_db), _: Principal = Depends(require("admin"))):
    db.delete(get_project_or_404(db, project_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ----- Client metadata (optional; PII encrypted at rest) -----
@router.put("/{project_id}/client", response_model=ClientOut)
def upsert_client(
    project_id: str,
    body: ClientIn,
    db: Session = Depends(get_db),
    _: Principal = Depends(require("manager")),
):
    project = get_project_or_404(db, project_id)
    values = body.model_dump()
    if project.client is None:
        project.client = Client(**values)
    else:
        for k, v in values.items():
            setattr(project.client, k, v)
    project.updated_at = datetime.now(UTC)  # bump so offline sync picks up the change
    db.commit()
    return ClientOut.model_validate(project.client)


@router.delete("/{project_id}/client", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(project_id: str, db: Session = Depends(get_db), _: Principal = Depends(require("manager"))):
    project = get_project_or_404(db, project_id)
    if project.client is not None:
        db.delete(project.client)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ----- Cloud storage -----
@router.post("/{project_id}/storage/provision", response_model=StorageProvisionOut)
def provision_storage(project_id: str, db: Session = Depends(get_db), _: Principal = Depends(require("admin"))):
    project = get_project_or_404(db, project_id)
    try:
        result = get_provider().provision_project(project.id, project.name)
    except Exception as exc:  # surface provider config/API problems clearly
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Storage provisioning failed: {exc}") from exc
    project.storage_provider = result.provider
    project.storage_folder_ref = result.folder_ref
    db.commit()
    return StorageProvisionOut(**result.__dict__)
