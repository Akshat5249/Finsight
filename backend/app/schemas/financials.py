"""
FinSight — Financial & Variance API Schemas
Phase 1, Prompt 7. Typed Pydantic response models for §9 financial endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel


# ── P&L Response ──────────────────────────────────────────────────────────────

class PnLResponse(BaseModel):
    revenue:          float
    cogs:             float
    gross_profit:     float
    gross_margin_pct: float
    opex:             float
    operating_income: float
    da:               float
    ebitda:           float
    interest:         float
    pretax_income:    float
    tax:              float
    net_income:       float


# ── Variance Response ─────────────────────────────────────────────────────────

class MetricVariance(BaseModel):
    actual:       float
    budget:       float
    variance:     float
    variance_pct: float | None
    favorable:    bool | None
    label:        str   # "Favorable" | "Unfavorable" | "Unknown"


class VarianceResponse(BaseModel):
    revenue:          MetricVariance
    cogs:             MetricVariance
    gross_profit:     MetricVariance
    gross_margin_pct: MetricVariance
    opex:             MetricVariance
    operating_income: MetricVariance
    da:               MetricVariance
    ebitda:           MetricVariance
    interest:         MetricVariance
    pretax_income:    MetricVariance
    tax:              MetricVariance
    net_income:       MetricVariance


# ── Drilldown Response ────────────────────────────────────────────────────────

class DrilldownItem(BaseModel):
    dimension_key:   str    # e.g. "Engineering" | "US" | "AI Solutions"
    dimension_type:  str    # "department" | "region" | "product" | "account_category"
    account_type:    str | None
    actual:          float
    budget:          float
    variance:        float
    variance_pct:    float | None
    favorable:       bool | None
    label:           str


class DrilldownResponse(BaseModel):
    items: list[DrilldownItem]
    total_actual: float
    total_budget: float

# ── Trend Response ────────────────────────────────────────────────────────────

class TrendDataPoint(BaseModel):
    date: str  # YYYY-MM
    revenue: float
    revenue_mom: float | None
    revenue_yoy: float | None
    ebitda: float
    ebitda_mom: float | None
    ebitda_yoy: float | None

class TrendResponse(BaseModel):
    trend: list[TrendDataPoint]
