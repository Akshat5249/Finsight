"""
FinSight — Forecast API Schemas
Phase 3, Prompt 12. Typed Pydantic models for forecast endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ForecastRequest(BaseModel):
    metric:  str   = Field("revenue", description="P&L metric to forecast")
    model:   str   = Field("linear_regression",
                           description="moving_average | linear_regression | exponential_smoothing | prophet")
    horizon: int   = Field(6, ge=1, le=24, description="Months to forecast (1–24)")
    # Optional training-window filters
    department:  str | None = None
    region:      str | None = None
    product:     str | None = None
    start_date:  str | None = None
    end_date:    str | None = None
    # Model-specific hyper-params (forwarded as **kwargs)
    window: int   | None = Field(None, ge=1, description="MA window (moving_average only)")
    alpha:  float | None = Field(None, gt=0, le=1, description="Smoothing factor (exponential_smoothing only)")


class ForecastPeriod(BaseModel):
    period:         str    # ISO date string YYYY-MM-DD
    forecast_value: float


class ForecastResponse(BaseModel):
    metric:      str
    model_used:  str
    horizon:     int
    periods:     list[ForecastPeriod]

    model_config = {"protected_namespaces": ()}


class StoredForecastResponse(BaseModel):
    """Response after persisting a forecast to the forecasts table."""
    run_id:      int | None  # analysis_run_id
    metric:      str
    model_used:  str
    horizon:     int
    periods:     list[ForecastPeriod]
    created_at:  datetime | None = None

    model_config = {"from_attributes": True, "protected_namespaces": ()}
