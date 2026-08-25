"""
FinSight — Scenario Engine
Phase 4, Prompt 13. Implements §11 of the Blueprint.

Applies assumption multipliers (revenue_growth_pct, cogs_growth_pct,
marketing_growth_pct) to a base P&L DataFrame and returns a modified
P&L DataFrame. All arithmetic is pure — no DB or API calls.

§11 scenario types: base | upside | downside | custom
"""

from __future__ import annotations

import pandas as pd


# ── Default assumption bands per scenario type (§11) ──────────────────────────
SCENARIO_DEFAULTS: dict[str, dict[str, float]] = {
    "base": {
        "revenue_growth_pct":   0.0,
        "cogs_growth_pct":      0.0,
        "marketing_growth_pct": 0.0,
    },
    "upside": {
        "revenue_growth_pct":   10.0,
        "cogs_growth_pct":      5.0,
        "marketing_growth_pct": 5.0,
    },
    "downside": {
        "revenue_growth_pct":   -10.0,
        "cogs_growth_pct":      3.0,
        "marketing_growth_pct": 8.0,
    },
}

MARKETING_CATS = {"Advertising", "Events", "Social Media", "Agencies", "Software"}


def apply_scenario(
    actual_df: pd.DataFrame,
    revenue_growth_pct:   float,
    cogs_growth_pct:      float,
    marketing_growth_pct: float,
    extra_assumptions:    dict | None = None,
) -> pd.DataFrame:
    """
    Apply scenario assumption multipliers to a base P&L DataFrame.  [§11]

    Modifies amounts in-place by account_type / account_category:
      - revenue rows:         ×(1 + revenue_growth_pct/100)
      - cogs rows:            ×(1 + cogs_growth_pct/100)
      - marketing opex rows:  ×(1 + marketing_growth_pct/100)
      - all other rows:       unchanged

    Args:
        actual_df:            Base DataFrame of financial rows (account_type, amount, ...)
        revenue_growth_pct:   % change in revenue (positive = growth)
        cogs_growth_pct:      % change in COGS (positive = cost increase)
        marketing_growth_pct: % change in marketing opex (positive = more spend)
        extra_assumptions:    extensible bag; ignored by this engine version

    Returns:
        New DataFrame with scenario-adjusted amounts (original is not modified).
    """
    df = actual_df.copy()

    rev_mult = 1 + revenue_growth_pct   / 100
    cogs_mult = 1 + cogs_growth_pct     / 100
    mkt_mult  = 1 + marketing_growth_pct / 100

    # Revenue rows
    rev_mask = df["account_type"] == "revenue"
    df.loc[rev_mask, "amount"] = df.loc[rev_mask, "amount"] * rev_mult

    # COGS rows
    cogs_mask = df["account_type"] == "cogs"
    df.loc[cogs_mask, "amount"] = df.loc[cogs_mask, "amount"] * cogs_mult

    # Marketing opex rows (by account_category)
    if "account_category" in df.columns:
        mkt_mask = (df["account_type"] == "opex") & (df["account_category"].isin(MARKETING_CATS))
        df.loc[mkt_mask, "amount"] = df.loc[mkt_mask, "amount"] * mkt_mult

    return df


def compare_scenarios(
    base_df: pd.DataFrame,
    scenario_df: pd.DataFrame,
) -> dict[str, dict[str, float]]:
    """
    Compare base and scenario P&L DataFrames, returning the delta for each metric.
    Delegates all P&L computation to financial_engine.compute_pnl().

    Returns:
        {
            "base":     {metric: value, ...},
            "scenario": {metric: value, ...},
            "delta":    {metric: scenario - base, ...},
            "delta_pct":{metric: (scenario - base) / base * 100 | None, ...},
        }
    """
    from app.services.financial_engine import compute_pnl

    base_pnl     = compute_pnl(base_df)
    scenario_pnl = compute_pnl(scenario_df)

    delta     = {k: round(scenario_pnl[k] - base_pnl[k], 2)               for k in base_pnl}
    delta_pct = {
        k: round((scenario_pnl[k] - base_pnl[k]) / base_pnl[k] * 100, 2)
        if base_pnl[k] != 0 else None
        for k in base_pnl
    }

    return {
        "base":      {k: round(v, 2) for k, v in base_pnl.items()},
        "scenario":  {k: round(v, 2) for k, v in scenario_pnl.items()},
        "delta":     delta,
        "delta_pct": delta_pct,
    }
