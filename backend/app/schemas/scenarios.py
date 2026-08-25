"""
FinSight — Scenario API Schemas
Phase 4, Prompt 13. Pydantic models for scenario endpoints.
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class ScenarioRequest(BaseModel):
    name:                 str   = Field("custom", description="base | upside | downside | custom")
    revenue_growth_pct:   float = Field(0.0)
    cogs_growth_pct:      float = Field(0.0)
    marketing_growth_pct: float = Field(0.0)
    # Optional training-data filters (same as financial endpoints)
    department:  str | None = None
    region:      str | None = None
    product:     str | None = None
    start_date:  str | None = None
    end_date:    str | None = None


class ScenarioPnL(BaseModel):
    revenue:           float
    cogs:              float
    gross_profit:      float
    gross_margin_pct:  float
    opex:              float
    operating_income:  float
    da:                float
    ebitda:            float
    interest:          float
    pretax_income:     float
    tax:               float
    net_income:        float


class ScenarioDelta(BaseModel):
    revenue:           float
    cogs:              float
    gross_profit:      float
    gross_margin_pct:  float
    opex:              float
    operating_income:  float
    da:                float
    ebitda:            float
    interest:          float
    pretax_income:     float
    tax:               float
    net_income:        float


class ScenarioResponse(BaseModel):
    scenario_name:        str
    assumptions:          dict[str, float]
    base:                 dict[str, float]
    scenario:             dict[str, float]
    delta:                dict[str, float]
    delta_pct:            dict[str, float | None]
