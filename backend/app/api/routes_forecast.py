"""
FinSight — Forecast Routes
Phase 3, Prompt 12. POST /forecasts + GET /forecasts/{run_id}

POST /forecasts:
  1. Load actuals time series from DB (filtered by request params)
  2. Build monthly P&L series via growth_analytics.build_monthly_pnl_series()
  3. Pass the chosen metric's series to forecast_engine.run_forecast()
  4. Persist each forecast period to the forecasts table
  5. Create an analysis_run record linking everything
  6. Return ForecastResponse

GET /forecasts/{run_id}:
  Load persisted forecast rows for the given analysis_run_id.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.routes_financials import _load_actuals
from app.db.models import AnalysisRun, Forecast, ForecastModel, RunStatus
from app.db.session import get_db
from app.schemas.forecasts import (
    ForecastPeriod,
    ForecastRequest,
    ForecastResponse,
    StoredForecastResponse,
)
from app.services.forecast_engine import run_forecast
from app.services.growth_analytics import build_monthly_pnl_series

router = APIRouter(prefix="/forecasts", tags=["forecasts"])

VALID_METRICS = {
    "revenue", "cogs", "gross_profit", "gross_margin_pct",
    "opex", "operating_income", "da", "ebitda",
    "interest", "pretax_income", "tax", "net_income",
}


@router.post("", response_model=StoredForecastResponse, status_code=201)
def create_forecast(
    request: ForecastRequest,
    db: Session = Depends(get_db),
) -> StoredForecastResponse:
    """
    Run a forecast and persist the results.
    Arithmetic is fully delegated to forecast_engine.run_forecast().
    """
    if request.metric not in VALID_METRICS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid metric '{request.metric}'. Valid: {sorted(VALID_METRICS)}"
        )

    # 1. Load actuals
    actual_df = _load_actuals(
        db,
        request.department, request.region, request.product,
        request.start_date, request.end_date,
    )
    if actual_df.empty:
        raise HTTPException(status_code=404, detail="No actuals data found for the given filters")

    # 2. Build monthly P&L time series
    monthly = build_monthly_pnl_series(actual_df)
    if monthly.empty or request.metric not in monthly.columns:
        raise HTTPException(status_code=404, detail=f"No data for metric '{request.metric}'")

    series = monthly[request.metric]

    # 3. Run the forecast model
    kwargs: dict = {}
    if request.window is not None:
        kwargs["window"] = request.window
    if request.alpha is not None:
        kwargs["alpha"] = request.alpha

    try:
        forecast_series = run_forecast(series, model=request.model, horizon=request.horizon, **kwargs)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # 4. Create analysis_run record
    run = AnalysisRun(
        status=RunStatus.complete,
        created_at=datetime.now(tz=timezone.utc),
        completed_at=datetime.now(tz=timezone.utc),
    )
    db.add(run)
    db.flush()  # get run.id

    # 5. Persist forecast rows
    model_enum = ForecastModel(request.model)
    now_utc = datetime.now(tz=timezone.utc)

    forecast_rows = []
    for period, value in forecast_series.items():
        row = Forecast(
            analysis_run_id=run.id,
            metric=request.metric,
            period=period,
            forecast_value=round(float(value), 2),
            model_used=model_enum,
            created_at=now_utc,
        )
        db.add(row)
        forecast_rows.append(row)

    db.commit()

    # 6. Build response
    periods = [
        ForecastPeriod(
            period=str(p.date()) if hasattr(p, "date") else str(p),
            forecast_value=round(float(v), 2),
        )
        for p, v in forecast_series.items()
    ]

    return StoredForecastResponse(
        run_id=run.id,
        metric=request.metric,
        model_used=request.model,
        horizon=request.horizon,
        periods=periods,
        created_at=now_utc,
    )


@router.get("/{run_id}", response_model=ForecastResponse)
def get_forecast(
    run_id: int,
    db: Session = Depends(get_db),
) -> ForecastResponse:
    """Retrieve persisted forecast results for a given analysis_run_id."""
    rows = db.execute(
        select(Forecast).where(Forecast.analysis_run_id == run_id)
    ).scalars().all()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No forecast found for run_id={run_id}")

    # All rows share the same metric and model (validated at creation)
    metric     = rows[0].metric
    model_used = rows[0].model_used.value if hasattr(rows[0].model_used, "value") else str(rows[0].model_used)

    periods = sorted([
        ForecastPeriod(
            period=str(r.period.date()) if hasattr(r.period, "date") else str(r.period),
            forecast_value=float(r.forecast_value),
        )
        for r in rows
    ], key=lambda x: x.period)

    return ForecastResponse(
        metric=metric,
        model_used=model_used,
        horizon=len(periods),
        periods=periods,
    )
