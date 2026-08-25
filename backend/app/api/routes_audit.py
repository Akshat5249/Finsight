"""
FinSight — Audit Trail Routes
Phase 7, Prompt 21.

Provides full audit trail over all platform activity:
  GET /audit/runs               — list all analysis_runs (paginated)
  GET /audit/runs/{id}          — single run details
  GET /audit/uploads            — list all uploads
  GET /audit/uploads/{id}       — single upload details
  GET /audit/runs/{id}/lineage  — full data lineage (upload → run → forecasts/reports)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.db.models import AnalysisRun, Forecast, Report, Upload
from app.db.session import get_db

router = APIRouter(prefix="/audit", tags=["audit"])


# ── Pydantic response schemas ─────────────────────────────────────────────────

class UploadSummary(BaseModel):
    id:          int
    file_type:   str
    filename:    str
    status:      str
    row_count:   int | None
    created_at:  str

    model_config = {"from_attributes": True}


class RunSummary(BaseModel):
    id:           int
    status:       str
    created_at:   str
    completed_at: str | None

    model_config = {"from_attributes": True}


class RunDetail(BaseModel):
    id:                 int
    status:             str
    actuals_upload_id:  int | None
    budget_upload_id:   int | None
    scenario_id:        int | None
    metrics_json:       dict | None
    created_at:         str
    completed_at:       str | None
    forecast_count:     int
    report_count:       int

    model_config = {"from_attributes": True}


class LineageResponse(BaseModel):
    run_id:             int
    actuals_upload:     UploadSummary | None
    budget_upload:      UploadSummary | None
    forecasts:          list[dict]
    reports:            list[dict]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_dt(dt) -> str | None:
    return dt.isoformat() if dt else None


def _upload_to_summary(u: Upload) -> UploadSummary:
    return UploadSummary(
        id=u.id,
        file_type=u.file_type.value if hasattr(u.file_type, "value") else str(u.file_type),
        filename=u.filename or "",
        status=u.status.value if hasattr(u.status, "value") else str(u.status),
        row_count=u.rows_processed,
        created_at=_fmt_dt(u.created_at) or "",
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/runs", response_model=list[RunSummary])
def list_runs(
    limit:  int = Query(50, ge=1, le=200),
    offset: int = Query(0,  ge=0),
    db: Session = Depends(get_db),
) -> list[RunSummary]:
    """List all analysis runs, newest first."""
    rows = db.execute(
        select(AnalysisRun).order_by(desc(AnalysisRun.created_at)).limit(limit).offset(offset)
    ).scalars().all()

    return [
        RunSummary(
            id=r.id,
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
            created_at=_fmt_dt(r.created_at) or "",
            completed_at=_fmt_dt(r.completed_at),
        )
        for r in rows
    ]


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: int, db: Session = Depends(get_db)) -> RunDetail:
    """Full detail for a single analysis run."""
    row = db.execute(
        select(AnalysisRun).where(AnalysisRun.id == run_id)
    ).scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Run id={run_id} not found")

    fc_count = len(db.execute(
        select(Forecast).where(Forecast.analysis_run_id == run_id)
    ).scalars().all())

    rpt_count = len(db.execute(
        select(Report).where(Report.analysis_run_id == run_id)
    ).scalars().all())

    return RunDetail(
        id=row.id,
        status=row.status.value if hasattr(row.status, "value") else str(row.status),
        actuals_upload_id=row.actuals_upload_id,
        budget_upload_id=row.budget_upload_id,
        scenario_id=row.scenario_id,
        metrics_json=row.metrics_json,
        created_at=_fmt_dt(row.created_at) or "",
        completed_at=_fmt_dt(row.completed_at),
        forecast_count=fc_count,
        report_count=rpt_count,
    )


@router.get("/uploads", response_model=list[UploadSummary])
def list_uploads(
    limit:  int = Query(50, ge=1, le=200),
    offset: int = Query(0,  ge=0),
    db: Session = Depends(get_db),
) -> list[UploadSummary]:
    """List all upload events, newest first."""
    rows = db.execute(
        select(Upload).order_by(desc(Upload.created_at)).limit(limit).offset(offset)
    ).scalars().all()
    return [_upload_to_summary(u) for u in rows]


@router.get("/uploads/{upload_id}", response_model=UploadSummary)
def get_upload(upload_id: int, db: Session = Depends(get_db)) -> UploadSummary:
    """Single upload record."""
    row = db.execute(
        select(Upload).where(Upload.id == upload_id)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Upload id={upload_id} not found")
    return _upload_to_summary(row)


@router.get("/runs/{run_id}/lineage", response_model=LineageResponse)
def get_lineage(run_id: int, db: Session = Depends(get_db)) -> LineageResponse:
    """
    Full data lineage for a run:
      uploads (actuals + budget) → analysis_run → forecasts + reports
    """
    row = db.execute(
        select(AnalysisRun).where(AnalysisRun.id == run_id)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Run id={run_id} not found")

    # Actuals upload
    actuals_upload = None
    if row.actuals_upload_id:
        u = db.execute(select(Upload).where(Upload.id == row.actuals_upload_id)).scalar_one_or_none()
        if u:
            actuals_upload = _upload_to_summary(u)

    # Budget upload
    budget_upload = None
    if row.budget_upload_id:
        u = db.execute(select(Upload).where(Upload.id == row.budget_upload_id)).scalar_one_or_none()
        if u:
            budget_upload = _upload_to_summary(u)

    # Forecasts
    fc_rows = db.execute(
        select(Forecast).where(Forecast.analysis_run_id == run_id)
    ).scalars().all()
    forecasts = [
        {
            "id":             f.id,
            "metric":         f.metric,
            "period":         str(f.period),
            "forecast_value": float(f.forecast_value),
            "model_used":     f.model_used.value if hasattr(f.model_used, "value") else str(f.model_used),
        }
        for f in fc_rows
    ]

    # Reports
    rpt_rows = db.execute(
        select(Report).where(Report.analysis_run_id == run_id)
    ).scalars().all()
    reports = [
        {
            "id":        r.id,
            "format":    r.format.value if hasattr(r.format, "value") else str(r.format),
            "file_path": r.file_path,
            "created_at": _fmt_dt(r.created_at),
        }
        for r in rpt_rows
    ]

    return LineageResponse(
        run_id=run_id,
        actuals_upload=actuals_upload,
        budget_upload=budget_upload,
        forecasts=forecasts,
        reports=reports,
    )
