"""
FinSight — Growth Analytics Routes
Phase 2, Prompt 10. GET /analytics/growth endpoint.

Returns MoM and YoY growth time series for any P&L metric,
filterable by department / region / product / date range.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.routes_financials import _load_actuals
from app.db.session import get_db
from app.services.growth_analytics import build_growth_response

router = APIRouter(prefix="/analytics", tags=["analytics"])

VALID_METRICS = {
    "revenue", "cogs", "gross_profit", "gross_margin_pct",
    "opex", "operating_income", "da", "ebitda",
    "interest", "pretax_income", "tax", "net_income",
}


class GrowthResponse(BaseModel):
    metric:  str
    periods: list[str]
    values:  list[float]
    mom_pct: list[float | None]
    yoy_pct: list[float | None]


@router.get("/growth", response_model=GrowthResponse)
def get_growth(
    metric:      str        = Query("revenue", description="P&L metric to analyse"),
    department:  str | None = Query(None),
    region:      str | None = Query(None),
    product:     str | None = Query(None),
    start_date:  date | None = Query(None),
    end_date:    date | None = Query(None),
    db: Session = Depends(get_db),
) -> GrowthResponse:
    """
    Return monthly values + MoM and YoY growth % for the chosen P&L metric.
    All arithmetic delegated to growth_analytics.build_growth_response().
    """
    if metric not in VALID_METRICS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid metric '{metric}'. Choose from: {sorted(VALID_METRICS)}"
        )

    actual_df = _load_actuals(db, department, region, product, start_date, end_date)
    if actual_df.empty:
        raise HTTPException(status_code=404, detail="No actuals data found for the given filters")

    result = build_growth_response(actual_df, metric=metric)
    if not result["periods"]:
        raise HTTPException(status_code=404, detail=f"No data for metric '{metric}'")

    return GrowthResponse(**result)
