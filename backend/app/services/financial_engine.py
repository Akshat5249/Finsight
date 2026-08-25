"""
FinSight — Financial Engine
Phase 1, Prompt 6. Implements every formula in §8.1 and §8.4 of the Blueprint EXACTLY.

GROUND RULE: Every function here is a pure function.
  - Input:  a pandas DataFrame of actuals or budgets rows (or a numeric series)
  - Output: a numeric value (or Series)
  - No database calls, no API calls, no side effects
  - The LLM is NEVER asked to compute these — it only explains already-computed results

All formulas follow §8.1 / §8.4 verbatim:
  Revenue        = sum(amount) where account_type = 'revenue'
  COGS           = sum(amount) where account_type = 'cogs'
  Gross Profit   = Revenue − COGS
  Gross Margin % = Gross Profit / Revenue × 100
  Opex           = sum(amount) where account_type = 'opex'
  EBIT           = Gross Profit − Opex
  D&A            = sum(amount) where account_type = 'da'
  EBITDA         = EBIT + D&A
  Interest       = sum(amount) where account_type = 'interest'
  Pre-tax Income = EBIT − Interest
  Tax            = sum(amount) where account_type = 'tax'
  Net Income     = Pre-tax Income − Tax
  MoM Growth %   = (Current − Previous) / Previous × 100
  YoY Growth %   = (Current − Same Month Last Year) / Same Month Last Year × 100
"""

from __future__ import annotations

import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# §8.1 — Core P&L (pure functions)
# ─────────────────────────────────────────────────────────────────────────────

def calc_revenue(df: pd.DataFrame) -> float:
    """Revenue = sum(amount) where account_type = 'revenue'  [§8.1]"""
    return float(df.loc[df["account_type"] == "revenue", "amount"].sum())


def calc_cogs(df: pd.DataFrame) -> float:
    """COGS = sum(amount) where account_type = 'cogs'  [§8.1]"""
    return float(df.loc[df["account_type"] == "cogs", "amount"].sum())


def calc_gross_profit(revenue: float, cogs: float) -> float:
    """Gross Profit = Revenue − COGS  [§8.1]"""
    return revenue - cogs


def calc_gross_margin_pct(gross_profit: float, revenue: float) -> float:
    """
    Gross Margin % = Gross Profit / Revenue × 100  [§8.1]
    Returns 0.0 if revenue is zero to avoid ZeroDivisionError.
    """
    if revenue == 0:
        return 0.0
    return (gross_profit / revenue) * 100


def calc_opex(df: pd.DataFrame) -> float:
    """Operating Expenses = sum(amount) where account_type = 'opex'  [§8.1]"""
    return float(df.loc[df["account_type"] == "opex", "amount"].sum())


def calc_operating_income(gross_profit: float, opex: float) -> float:
    """Operating Income (EBIT) = Gross Profit − Operating Expenses  [§8.1]"""
    return gross_profit - opex


def calc_da(df: pd.DataFrame) -> float:
    """D&A = sum(amount) where account_type = 'da'  [§8.1]"""
    return float(df.loc[df["account_type"] == "da", "amount"].sum())


def calc_ebitda(operating_income: float, da: float) -> float:
    """EBITDA = Operating Income + D&A  [§8.1]"""
    return operating_income + da


def calc_interest(df: pd.DataFrame) -> float:
    """Interest = sum(amount) where account_type = 'interest'  [§8.1]"""
    return float(df.loc[df["account_type"] == "interest", "amount"].sum())


def calc_pretax_income(operating_income: float, interest: float) -> float:
    """Pre-tax Income = Operating Income − Interest  [§8.1]"""
    return operating_income - interest


def calc_tax(df: pd.DataFrame) -> float:
    """
    Tax = sum(amount) where account_type = 'tax'  [§8.1]
    Approach chosen: use itemised tax rows from the dataset (not assumed rate).
    This is documented here so the approach is consistent throughout the codebase.
    """
    return float(df.loc[df["account_type"] == "tax", "amount"].sum())


def calc_net_income(pretax_income: float, tax: float) -> float:
    """Net Income = Pre-tax Income − Tax  [§8.1]"""
    return pretax_income - tax


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: compute full P&L from a DataFrame in one call
# ─────────────────────────────────────────────────────────────────────────────

def compute_pnl(df: pd.DataFrame) -> dict[str, float]:
    """
    Compute the complete P&L statement from a DataFrame of financial rows.
    Returns a dict keyed by metric name — no DB or API calls.

    This is the single source of truth for all P&L numbers in the system.
    Downstream consumers (API routes, reporting, RAG) read from this output;
    they never re-derive any of these values independently.
    """
    revenue        = calc_revenue(df)
    cogs           = calc_cogs(df)
    gross_profit   = calc_gross_profit(revenue, cogs)
    gross_margin   = calc_gross_margin_pct(gross_profit, revenue)
    opex           = calc_opex(df)
    operating_income = calc_operating_income(gross_profit, opex)
    da             = calc_da(df)
    ebitda         = calc_ebitda(operating_income, da)
    interest       = calc_interest(df)
    pretax_income  = calc_pretax_income(operating_income, interest)
    tax            = calc_tax(df)
    net_income     = calc_net_income(pretax_income, tax)

    return {
        "revenue":          revenue,
        "cogs":             cogs,
        "gross_profit":     gross_profit,
        "gross_margin_pct": gross_margin,
        "opex":             opex,
        "operating_income": operating_income,
        "da":               da,
        "ebitda":           ebitda,
        "interest":         interest,
        "pretax_income":    pretax_income,
        "tax":              tax,
        "net_income":       net_income,
    }


# ─────────────────────────────────────────────────────────────────────────────
# §8.4 — Growth rates (pure functions on numeric Series)
# ─────────────────────────────────────────────────────────────────────────────

def calc_mom_growth_pct(current: float, previous: float) -> float | None:
    """
    MoM Growth % = (Current − Previous) / Previous × 100  [§8.4]
    Returns None if previous is 0 (undefined / avoid divide-by-zero).
    """
    if previous == 0:
        return None
    return ((current - previous) / previous) * 100


def calc_yoy_growth_pct(current: float, same_month_last_year: float) -> float | None:
    """
    YoY Growth % = (Current − Same Month Last Year) / Same Month Last Year × 100  [§8.4]
    Returns None if same_month_last_year is 0.
    """
    if same_month_last_year == 0:
        return None
    return ((current - same_month_last_year) / same_month_last_year) * 100


def calc_mom_growth_series(series: pd.Series) -> pd.Series:
    """
    Compute MoM growth % for an ordered time series of metric values.
    Returns a Series of the same length with NaN for the first element.
    """
    pct = series.pct_change() * 100
    return pct


def calc_yoy_growth_series(series: pd.Series) -> pd.Series:
    """
    Compute YoY growth % for a monthly time series.
    Compares each element to the one 12 periods earlier.
    Returns NaN for the first 12 periods.
    """
    pct = series.pct_change(periods=12) * 100
    return pct
