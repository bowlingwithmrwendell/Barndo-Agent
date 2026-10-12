"""In-app feedback & bug log aggregation (spec sections 3 and 8)."""

from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Feedback, FeedbackStatus, FeedbackType
from app.schemas import FeedbackCreate, FeedbackOut, FeedbackStats, FeedbackUpdate
from app.security import Principal, require

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    body: FeedbackCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require("field")),
):
    fb = Feedback(**body.model_dump(), submitted_by_role=principal.role)
    db.add(fb)
    db.commit()
    return fb


@router.get("", response_model=list[FeedbackOut])
def list_feedback(
    feedback_type: FeedbackType | None = None,
    status_: FeedbackStatus | None = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: Principal = Depends(require("admin")),
):
    stmt = select(Feedback).order_by(Feedback.created_at.desc()).limit(limit)
    if feedback_type:
        stmt = stmt.where(Feedback.feedback_type == feedback_type)
    if status_:
        stmt = stmt.where(Feedback.status == status_)
    return list(db.scalars(stmt))


@router.get("/stats", response_model=FeedbackStats)
def feedback_stats(db: Session = Depends(get_db), _: Principal = Depends(require("admin"))):
    items = list(db.scalars(select(Feedback)))
    return FeedbackStats(
        total=len(items),
        by_type=dict(Counter(f.feedback_type.value for f in items)),
        by_status=dict(Counter(f.status.value for f in items)),
    )


@router.patch("/{feedback_id}", response_model=FeedbackOut)
def update_feedback(
    feedback_id: str,
    body: FeedbackUpdate,
    db: Session = Depends(get_db),
    _: Principal = Depends(require("admin")),
):
    fb = db.get(Feedback, feedback_id)
    if fb is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Feedback not found")
    fb.status = body.status
    db.commit()
    return fb
