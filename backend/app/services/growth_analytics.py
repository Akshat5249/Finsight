"""
FinSight — Growth Analytics Service
Phase 2, Prompt 10. Implements §8.4 growth analysis over time series.

Computes monthly P&L time series from the DB rows, then derives:
  - MoM Growth % per metric (month-over-month)
  - YoY Growth % per metric (year-over-year, requires ≥13 months)

All arithmetic delegates to financial_engine.compute_pnl() per period.
No math is re-implemented here — only grouping and delegation.
"""

from __future__ import annotations

import pandas as pd

from app.services.financial_engine import compute_pnl


def build_monthly_pnl_series(df: pd.DataFrame) -> pd.DataFrame:
    """
    Given a DataFrame of actuals (or budget) rows, group by calendar month
    and compute compute_pnl() for each month.

    Returns a DataFrame indexed by period (YYYY-MM-01) with one column per
    P&L metric: revenue, cogs, gross_profit, gross_margin_pct, opex,
    operating_income, da, ebitda, interest, pretax_income, tax, net_income.

    Requires df to contain columns: date, account_type, amount.
    """
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["period"] = df["date"].dt.to_period("M").dt.to_timestamp()

    periods = sorted(df["period"].unique())
    rows = []
    for p in periods:
        period_df = df[df["period"] == p]
        pnl = compute_pnl(period_df)
        pnl["period"] = p
        rows.append(pnl)

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows).set_index("period").sort_index()
    return result


def calc_growth_series(monthly_pnl: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Given the output of build_monthly_pnl_series(), compute MoM and YoY
    growth % Series for every P&L metric.

    Returns:
        {
            "mom": DataFrame (same shape as monthly_pnl, values are MoM %)
            "yoy": DataFrame (same shape, values are YoY %)
        }

    Uses financial_engine.calc_mom_growth_series / calc_yoy_growth_series
    to stay DRY — the growth formulas live in exactly one place.
    """
    from app.services.financial_engine import calc_mom_growth_series, calc_yoy_growth_series

    mom = monthly_pnl.apply(calc_mom_growth_series, axis=0)
    yoy = monthly_pnl.apply(calc_yoy_growth_series, axis=0)

    return {"mom": mom, "yoy": yoy}


def build_growth_response(
    actual_df: pd.DataFrame,
    metric: str = "revenue",
) -> dict:
    """
    Build the full growth API response for a given metric.

    Returns:
        {
            "metric": str,
            "periods": [str],           # ISO date strings (YYYY-MM-DD)
            "values":  [float],         # raw metric value per month
            "mom_pct": [float|None],    # MoM growth % (None for first month)
            "yoy_pct": [float|None],    # YoY growth % (None for first 12 months)
        }
    """
    monthly = build_monthly_pnl_series(actual_df)
    if monthly.empty or metric not in monthly.columns:
        return {
            "metric":  metric,
            "periods": [],
            "values":  [],
            "mom_pct": [],
            "yoy_pct": [],
        }

    growth = calc_growth_series(monthly)
    mom_s  = growth["mom"][metric]
    yoy_s  = growth["yoy"][metric]

    periods  = [str(p.date()) for p in monthly.index]
    values   = [round(float(v), 2)         for v in monthly[metric]]
    mom_pct  = [None if pd.isna(v) else round(float(v), 2) for v in mom_s]
    yoy_pct  = [None if pd.isna(v) else round(float(v), 2) for v in yoy_s]

    return {
        "metric":  metric,
        "periods": periods,
        "values":  values,
        "mom_pct": mom_pct,
        "yoy_pct": yoy_pct,
    }
