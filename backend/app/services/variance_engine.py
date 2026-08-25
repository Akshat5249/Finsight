"""
FinSight — Variance Engine
Phase 1, Prompt 6. Implements §8.2 and §8.3 of the Blueprint.
Phase 2, Prompt 9 adds §8.5 EBITDA driver decomposition.

§8.2 Variance:
  Variance (absolute) = Actual − Budget
  Variance %          = (Actual − Budget) / Budget × 100
  (Budget = 0 handled explicitly — returns None for %)

§8.3 Favorability (critical business logic — not just sign):
  Revenue/profit metrics: positive variance = Favorable
  Cost metrics:           positive variance (overspend) = Unfavorable
  Implemented as explicit is_favorable() — never infer from sign in UI code.

§8.5 EBITDA driver decomposition:
  Decompose total EBITDA variance into named drivers that sum exactly to total.
  (Implemented in Phase 2, Prompt 9)
"""

from __future__ import annotations

import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# Metric type classification — drives favorability logic
# ─────────────────────────────────────────────────────────────────────────────

# Revenue-type and profit-type metrics: positive variance = Favorable
REVENUE_PROFIT_METRICS = frozenset({
    "revenue",
    "gross_profit",
    "operating_income",
    "ebitda",
    "pretax_income",
    "net_income",
})

# Cost-type metrics: positive variance (actual > budget = overspend) = Unfavorable
COST_METRICS = frozenset({
    "cogs",
    "opex",
    "da",
    "interest",
    "tax",
    # Granular opex sub-categories are also cost-type
    "advertising",
    "events",
    "social_media",
    "agencies",
    "software",
    "salaries",
    "infrastructure",
    "cloud_hosting",
    "r&d",
    "travel",
    "facilities",
})


# ─────────────────────────────────────────────────────────────────────────────
# §8.3 — Favorability classification
# ─────────────────────────────────────────────────────────────────────────────

def is_favorable(metric_type: str, variance_value: float) -> bool | None:
    """
    Classify whether a variance is favorable for a given metric type.  [§8.3]

    For revenue/profit metrics: positive variance → True (Favorable)
    For cost metrics:           positive variance → False (Unfavorable)
    Returns None if metric_type is unrecognised.

    This function is the ONLY place in the codebase that classifies favorability.
    UI and API code must call this — never infer from sign alone.
    """
    normalized = metric_type.lower().strip()
    if normalized in REVENUE_PROFIT_METRICS:
        return variance_value >= 0
    if normalized in COST_METRICS:
        return variance_value <= 0
    return None  # Unknown metric — caller should handle


def favorability_label(metric_type: str, variance_value: float) -> str:
    """
    Human-readable favorability label: "Favorable", "Unfavorable", or "Unknown".
    Convenience wrapper around is_favorable().
    """
    result = is_favorable(metric_type, variance_value)
    if result is True:
        return "Favorable"
    if result is False:
        return "Unfavorable"
    return "Unknown"


# ─────────────────────────────────────────────────────────────────────────────
# §8.2 — Variance calculation
# ─────────────────────────────────────────────────────────────────────────────

def calc_variance(actual: float, budget: float) -> float:
    """
    Variance (absolute) = Actual − Budget  [§8.2]
    """
    return actual - budget


def calc_variance_pct(actual: float, budget: float) -> float | None:
    """
    Variance % = (Actual − Budget) / Budget × 100  [§8.2]
    Returns None if budget is 0 (explicitly handled — never divide-by-zero).
    """
    if budget == 0:
        return None
    return ((actual - budget) / budget) * 100


def compute_variance_report(
    actual_df: pd.DataFrame,
    budget_df: pd.DataFrame,
) -> dict[str, dict]:
    """
    Compute full variance report for all P&L metrics.
    Calls financial_engine.compute_pnl() for both datasets — never re-derives.

    Returns a dict:
      {
        "revenue": {
          "actual": float, "budget": float,
          "variance": float, "variance_pct": float|None,
          "favorable": bool|None, "label": str
        },
        ...
      }
    """
    from app.services.financial_engine import compute_pnl

    actual_pnl = compute_pnl(actual_df)
    budget_pnl = compute_pnl(budget_df)

    result: dict[str, dict] = {}
    for metric in actual_pnl:
        actual_val = actual_pnl[metric]
        budget_val = budget_pnl[metric]
        var        = calc_variance(actual_val, budget_val)
        var_pct    = calc_variance_pct(actual_val, budget_val)
        fav        = is_favorable(metric, var)
        label      = favorability_label(metric, var)

        result[metric] = {
            "actual":       round(actual_val, 2),
            "budget":       round(budget_val, 2),
            "variance":     round(var, 2),
            "variance_pct": round(var_pct, 2) if var_pct is not None else None,
            "favorable":    fav,
            "label":        label,
        }

    return result


# ─────────────────────────────────────────────────────────────────────────────
# §8.5 — EBITDA Variance Driver Decomposition (Phase 2, Prompt 9)
# ─────────────────────────────────────────────────────────────────────────────

def decompose_ebitda_variance(
    actual_df: pd.DataFrame,
    budget_df: pd.DataFrame,
) -> dict[str, float]:
    """
    Decompose the total EBITDA variance into named drivers.  [§8.5]

    Named drivers: Revenue, COGS, Marketing, Infrastructure, Other

    Methodology (verbatim from Blueprint §8.5):
      1. Compute each driver's own variance contribution independently.
      2. Sum the named drivers.
      3. Assign any unexplained residual to 'Other' so the waterfall always
         reconciles exactly to the total EBITDA variance.

    Invariant enforced by unit test:
      sum(drivers.values()) == total_ebitda_variance   (within float tolerance)

    Driver sign convention:
      - Revenue driver:      positive = favorable (more revenue → higher EBITDA)
      - COGS driver:         negative sign = cost increase hurts EBITDA
      - Marketing driver:    negative sign = opex increase hurts EBITDA
      - Infrastructure driver: negative sign = opex increase hurts EBITDA
      - Other:               residual, can be positive or negative

    Returns a dict with keys:
      Revenue, COGS, Marketing, Infrastructure, Other, Total
    """
    from app.services.financial_engine import compute_pnl

    actual_pnl = compute_pnl(actual_df)
    budget_pnl = compute_pnl(budget_df)

    total_ebitda_variance = actual_pnl["ebitda"] - budget_pnl["ebitda"]

    # ── Driver 1: Revenue contribution to EBITDA variance ────────────────────
    # If revenue increases, EBITDA increases by the same amount (assuming costs fixed)
    revenue_driver = actual_pnl["revenue"] - budget_pnl["revenue"]

    # ── Driver 2: COGS contribution (sign: cost increase → negative EBITDA impact) ──
    cogs_driver = -(actual_pnl["cogs"] - budget_pnl["cogs"])

    # ── Driver 3: Marketing opex contribution ─────────────────────────────────
    # Filter opex rows to Marketing categories only
    MARKETING_CATS = {"Advertising", "Events", "Social Media", "Agencies", "Software"}

    def _sum_opex_cats(df: pd.DataFrame, cats: set[str]) -> float:
        mask = (df["account_type"] == "opex") & (df["account_category"].isin(cats))
        return float(df.loc[mask, "amount"].sum())

    actual_mkt  = _sum_opex_cats(actual_df, MARKETING_CATS)
    budget_mkt  = _sum_opex_cats(budget_df, MARKETING_CATS)
    marketing_driver = -(actual_mkt - budget_mkt)

    # ── Driver 4: Infrastructure opex contribution ────────────────────────────
    INFRA_CATS = {"Infrastructure", "Cloud Hosting"}

    actual_infra = _sum_opex_cats(actual_df, INFRA_CATS)
    budget_infra = _sum_opex_cats(budget_df, INFRA_CATS)
    infrastructure_driver = -(actual_infra - budget_infra)

    # ── Driver 5: Other (residual) — ensures sum == total ────────────────────
    named_sum = revenue_driver + cogs_driver + marketing_driver + infrastructure_driver
    other_driver = total_ebitda_variance - named_sum

    drivers = {
        "Revenue":        round(revenue_driver, 2),
        "COGS":           round(cogs_driver, 2),
        "Marketing":      round(marketing_driver, 2),
        "Infrastructure": round(infrastructure_driver, 2),
        "Other":          round(other_driver, 2),
        "Total":          round(total_ebitda_variance, 2),
    }

    return drivers

