"""
FinSight — Report Generation Routes
Phase 6, Prompt 19.

GET /reports/download?format=excel|pdf|pptx

Generates and streams the report file directly — no DB persistence required.
All data loaded from the financials DB and computed by financial_engine +
variance_engine. All rendering delegated to reporting.py.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.routes_financials import _load_actuals, _load_budgets
from app.db.session import get_db
from app.services.financial_engine import compute_pnl
from app.services.reporting import generate_excel_report, generate_pdf_report, generate_pptx_report
from app.services.variance_engine import compute_variance_report

router = APIRouter(prefix="/reports", tags=["reports"])

MIME_TYPES = {
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf":   "application/pdf",
    "pptx":  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

EXTENSIONS = {
    "excel": "xlsx",
    "pdf":   "pdf",
    "pptx":  "pptx",
}


@router.get("/download")
def download_report(
    format:      str       = Query("excel", description="excel | pdf | pptx"),
    department:  str | None = Query(None),
    region:      str | None = Query(None),
    product:     str | None = Query(None),
    start_date:  date | None = Query(None),
    end_date:    date | None = Query(None),
    db: Session = Depends(get_db),
) -> Response:
    """
    Generate and stream a financial report in the requested format.
    Data computed from actuals + budget in the DB for the given filter window.
    """
    if format not in MIME_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid format '{format}'. Choose from: {sorted(MIME_TYPES)}"
        )

    actual_df = _load_actuals(db, department, region, product, start_date, end_date)
    if actual_df.empty:
        raise HTTPException(status_code=404, detail="No actuals data for the given filters")

    budget_df = _load_budgets(db, department, region, product, start_date, end_date)

    pnl      = compute_pnl(actual_df)
    variance = compute_variance_report(actual_df, budget_df) if not budget_df.empty else {}

    meta = {
        "title":      "FinSight Financial Report",
        "department": department or "All Departments",
        "region":     region     or "All Regions",
        "period":     f"{start_date or 'start'} to {end_date or 'latest'}",
    }

    # Delegate rendering to reporting.py — no arithmetic here
    if format == "excel":
        content = generate_excel_report(pnl, variance, metadata=meta)
    elif format == "pdf":
        content = generate_pdf_report(pnl, variance, metadata=meta)
    else:
        content = generate_pptx_report(pnl, variance, metadata=meta)

    filename = f"finsight_report_{(start_date or date.today()).isoformat()}.{EXTENSIONS[format]}"

    return Response(
        content=content,
        media_type=MIME_TYPES[format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
