"""
FinSight — Financial & Variance API Routes
Phase 1, Prompt 7. Implements §9 financial endpoints.

Endpoints:
  GET /financials/pnl       — P&L filterable by dept/region/product/dates
  GET /financials/variance  — budget-vs-actual variance with favorability
  GET /financials/drilldown — breakdown by dimension

These routes call financial_engine.py and variance_engine.py only.
They NEVER re-implement any financial math.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Actual, Budget
from app.db.session import get_db
from app.schemas.financials import DrilldownItem, DrilldownResponse, PnLResponse, VarianceResponse
from app.schemas.waterfall import EbitdaWaterfallResponse
from app.services.financial_engine import compute_pnl
from app.services.variance_engine import (
    calc_variance, calc_variance_pct, compute_variance_report,
    decompose_ebitda_variance, is_favorable, favorability_label,
)

router = APIRouter(prefix="/financials", tags=["financials"])


# ── Shared helpers ────────────────────────────────────────────────────────────

def _load_actuals(
    db: Session,
    department: str | None,
    region: str | None,
    product: str | None,
    start_date: date | None,
    end_date: date | None,
) -> pd.DataFrame:
    """Load actuals rows from DB, apply optional filters, return DataFrame."""
    q = select(Actual)
    if department:
        q = q.where(Actual.department == department)
    if region:
        q = q.where(Actual.region == region)
    if product:
        q = q.where(Actual.product == product)
    if start_date:
        q = q.where(Actual.date >= start_date)
    if end_date:
        q = q.where(Actual.date <= end_date)

    rows = db.execute(q).scalars().all()
    if not rows:
        return pd.DataFrame(columns=["account_type", "amount", "department", "region", "product", "account_category", "date"])

    return pd.DataFrame([{
        "account_type":     r.account_type.value if hasattr(r.account_type, 'value') else r.account_type,
        "amount":           float(r.amount),
        "department":       r.department,
        "region":           r.region,
        "product":          r.product,
        "account_category": r.account_category,
        "date":             r.date,
    } for r in rows])


def _load_budgets(
    db: Session,
    department: str | None,
    region: str | None,
    product: str | None,
    start_date: date | None,
    end_date: date | None,
) -> pd.DataFrame:
    """Load budget rows from DB, apply optional filters, return DataFrame."""
    q = select(Budget)
    if department:
        q = q.where(Budget.department == department)
    if region:
        q = q.where(Budget.region == region)
    if product:
        q = q.where(Budget.product == product)
    if start_date:
        q = q.where(Budget.date >= start_date)
    if end_date:
        q = q.where(Budget.date <= end_date)

    rows = db.execute(q).scalars().all()
    if not rows:
        return pd.DataFrame(columns=["account_type", "amount", "department", "region", "product", "account_category", "date"])

    return pd.DataFrame([{
        "account_type":     r.account_type.value if hasattr(r.account_type, 'value') else r.account_type,
        "amount":           float(r.amount),
        "department":       r.department,
        "region":           r.region,
        "product":          r.product,
        "account_category": r.account_category,
        "date":             r.date,
    } for r in rows])


# ── GET /financials/pnl ───────────────────────────────────────────────────────

@router.get("/pnl", response_model=PnLResponse)
def get_pnl(
    department:  str | None = Query(None),
    region:      str | None = Query(None),
    product:     str | None = Query(None),
    start_date:  date | None = Query(None),
    end_date:    date | None = Query(None),
    db: Session = Depends(get_db),
) -> PnLResponse:
    """
    Compute P&L for the filtered subset of actuals.
    All arithmetic delegated to financial_engine.compute_pnl().
    """
    actual_df = _load_actuals(db, department, region, product, start_date, end_date)
    if actual_df.empty:
        raise HTTPException(status_code=404, detail="No actuals data found for the given filters")

    pnl = compute_pnl(actual_df)
    return PnLResponse(**pnl)


# ── GET /financials/variance ──────────────────────────────────────────────────

@router.get("/variance", response_model=VarianceResponse)
def get_variance(
    department:  str | None = Query(None),
    region:      str | None = Query(None),
    product:     str | None = Query(None),
    start_date:  date | None = Query(None),
    end_date:    date | None = Query(None),
    db: Session = Depends(get_db),
) -> VarianceResponse:
    """
    Compute budget-vs-actual variance with favorability for all P&L metrics.
    Calls variance_engine.compute_variance_report() — no math re-implemented here.
    """
    actual_df = _load_actuals(db, department, region, product, start_date, end_date)
    budget_df = _load_budgets(db, department, region, product, start_date, end_date)

    if actual_df.empty:
        raise HTTPException(status_code=404, detail="No actuals data found for the given filters")
    if budget_df.empty:
        raise HTTPException(status_code=404, detail="No budget data found for the given filters")

    report = compute_variance_report(actual_df, budget_df)
    return VarianceResponse(**report)


# ── GET /financials/drilldown ─────────────────────────────────────────────────

@router.get("/drilldown", response_model=DrilldownResponse)
def get_drilldown(
    dimension:   str         = Query("department", description="department | region | product | account_category"),
    department:  str | None  = Query(None),
    region:      str | None  = Query(None),
    product:     str | None  = Query(None),
    start_date:  date | None = Query(None),
    end_date:    date | None = Query(None),
    db: Session = Depends(get_db),
) -> DrilldownResponse:
    """
    Breakdown of actuals vs budget by the chosen dimension.
    Variance + favorability computed per-group using variance_engine.
    """
    valid_dimensions = {"department", "region", "product", "account_category"}
    if dimension not in valid_dimensions:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid dimension '{dimension}'. Choose from: {sorted(valid_dimensions)}"
        )

    actual_df = _load_actuals(db, department, region, product, start_date, end_date)
    budget_df = _load_budgets(db, department, region, product, start_date, end_date)

    if actual_df.empty:
        raise HTTPException(status_code=404, detail="No actuals data found for the given filters")

    # Group by dimension + account_type, sum amounts
    actual_grp = (
        actual_df.groupby([dimension, "account_type"], dropna=False)["amount"]
        .sum()
        .reset_index()
        .rename(columns={"amount": "actual"})
    )
    budget_grp = (
        budget_df.groupby([dimension, "account_type"], dropna=False)["amount"]
        .sum()
        .reset_index()
        .rename(columns={"amount": "budget"})
    ) if not budget_df.empty else pd.DataFrame(columns=[dimension, "account_type", "budget"])

    merged = actual_grp.merge(budget_grp, on=[dimension, "account_type"], how="left").fillna(0)

    items = []
    for _, row in merged.iterrows():
        dim_key  = str(row[dimension]) if row[dimension] is not None else "Unknown"
        acc_type = str(row["account_type"])
        actual   = float(row["actual"])
        budget   = float(row["budget"])
        var      = calc_variance(actual, budget)
        var_pct  = calc_variance_pct(actual, budget)
        fav      = is_favorable(acc_type, var)
        label    = favorability_label(acc_type, var)

        items.append(DrilldownItem(
            dimension_key=dim_key,
            dimension_type=dimension,
            account_type=acc_type,
            actual=round(actual, 2),
            budget=round(budget, 2),
            variance=round(var, 2),
            variance_pct=round(var_pct, 2) if var_pct is not None else None,
            favorable=fav,
            label=label,
        ))

    total_actual = float(actual_df["amount"].sum())
    total_budget = float(budget_df["amount"].sum()) if not budget_df.empty else 0.0

    return DrilldownResponse(
        items=items,
        total_actual=round(total_actual, 2),
        total_budget=round(total_budget, 2),
    )


# ── GET /financials/ebitda-waterfall ─────────────────────────────────────────

@router.get("/ebitda-waterfall", response_model=EbitdaWaterfallResponse)
def get_ebitda_waterfall(
    department:  str | None = Query(None),
    region:      str | None = Query(None),
    product:     str | None = Query(None),
    start_date:  date | None = Query(None),
    end_date:    date | None = Query(None),
    db: Session = Depends(get_db),
) -> EbitdaWaterfallResponse:
    """
    Decompose the EBITDA variance into named drivers (§8.5).
    Returns a waterfall-ready dict:
      {Revenue, COGS, Marketing, Infrastructure, Other, Total}
    Reconciliation invariant: sum(drivers) == Total.
    """
    actual_df = _load_actuals(db, department, region, product, start_date, end_date)
    budget_df = _load_budgets(db, department, region, product, start_date, end_date)

    if actual_df.empty:
        raise HTTPException(status_code=404, detail="No actuals data found for the given filters")
    if budget_df.empty:
        raise HTTPException(status_code=404, detail="No budget data found for the given filters")

    drivers = decompose_ebitda_variance(actual_df, budget_df)
    total   = drivers["Total"]
    fav     = is_favorable("ebitda", total)

    return EbitdaWaterfallResponse(
        drivers=drivers,
        total_ebitda_variance=total,
        favorable=bool(fav) if fav is not None else False,
    )
