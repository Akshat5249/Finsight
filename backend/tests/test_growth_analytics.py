"""
FinSight — Unit Tests: Growth Analytics
Phase 2, Prompt 10. Tests for growth_analytics.py.

Covers:
  - build_monthly_pnl_series: correct period grouping, correct metric values
  - calc_growth_series: MoM correct for consecutive months
  - calc_growth_series: YoY returns None for first 12 months
  - build_growth_response: full response shape and content
  - Empty DataFrame handling (no crash)
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from app.services.growth_analytics import (
    build_growth_response,
    build_monthly_pnl_series,
    calc_growth_series,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_rows(period: date, revenue: float, cogs: float, opex: float) -> list[dict]:
    """Build minimal financial rows for one period."""
    return [
        {"date": period, "account_type": "revenue",  "account_category": "Rev",  "amount": revenue},
        {"date": period, "account_type": "cogs",     "account_category": "COGS", "amount": cogs},
        {"date": period, "account_type": "opex",     "account_category": "Opex", "amount": opex},
        {"date": period, "account_type": "da",       "account_category": "DA",   "amount": 10.0},
        {"date": period, "account_type": "interest", "account_category": "Int",  "amount": 5.0},
        {"date": period, "account_type": "tax",      "account_category": "Tax",  "amount": 20.0},
    ]


@pytest.fixture
def two_month_df() -> pd.DataFrame:
    """Two months of data: Jan 1000 rev, Feb 1100 rev (10% MoM growth)."""
    rows = (
        _make_rows(date(2025, 1, 1), revenue=1000, cogs=400, opex=200)
        + _make_rows(date(2025, 2, 1), revenue=1100, cogs=440, opex=200)
    )
    return pd.DataFrame(rows)


@pytest.fixture
def thirteen_month_df() -> pd.DataFrame:
    """13 months of data to enable YoY calculation on month 13."""
    rows = []
    for m in range(13):
        year, month = divmod(m, 12)
        period = date(2024 + year, month + 1, 1)
        # Revenue grows 5% per month
        rev = 1000 * (1.05 ** m)
        rows.extend(_make_rows(period, revenue=rev, cogs=rev * 0.4, opex=rev * 0.2))
    return pd.DataFrame(rows)


# ── build_monthly_pnl_series ──────────────────────────────────────────────────

class TestBuildMonthlyPnlSeries:
    def test_returns_two_periods(self, two_month_df):
        result = build_monthly_pnl_series(two_month_df)
        assert len(result) == 2

    def test_correct_revenue_per_period(self, two_month_df):
        result = build_monthly_pnl_series(two_month_df)
        # Jan revenue = 1000, Feb = 1100
        assert result["revenue"].iloc[0] == pytest.approx(1000.0)
        assert result["revenue"].iloc[1] == pytest.approx(1100.0)

    def test_pnl_chain_per_period(self, two_month_df):
        """gross_profit per period = revenue - cogs (not cumulative)."""
        result = build_monthly_pnl_series(two_month_df)
        assert result["gross_profit"].iloc[0] == pytest.approx(600.0)  # 1000-400
        assert result["gross_profit"].iloc[1] == pytest.approx(660.0)  # 1100-440

    def test_empty_df_returns_empty(self):
        result = build_monthly_pnl_series(pd.DataFrame())
        assert result.empty

    def test_all_metrics_present(self, two_month_df):
        result = build_monthly_pnl_series(two_month_df)
        expected = {"revenue", "cogs", "gross_profit", "gross_margin_pct", "opex",
                    "operating_income", "da", "ebitda", "interest", "pretax_income",
                    "tax", "net_income"}
        assert expected.issubset(set(result.columns))


# ── calc_growth_series ────────────────────────────────────────────────────────

class TestCalcGrowthSeries:
    def test_mom_first_period_is_nan(self, two_month_df):
        monthly = build_monthly_pnl_series(two_month_df)
        growth  = calc_growth_series(monthly)
        assert pd.isna(growth["mom"]["revenue"].iloc[0])

    def test_mom_second_period_correct(self, two_month_df):
        """Revenue: 1000→1100 = 10% MoM."""
        monthly = build_monthly_pnl_series(two_month_df)
        growth  = calc_growth_series(monthly)
        assert growth["mom"]["revenue"].iloc[1] == pytest.approx(10.0)

    def test_yoy_requires_12_periods(self, two_month_df):
        """Only 2 months of data → all YoY values are NaN."""
        monthly = build_monthly_pnl_series(two_month_df)
        growth  = calc_growth_series(monthly)
        assert growth["yoy"]["revenue"].isna().all()

    def test_yoy_available_at_period_13(self, thirteen_month_df):
        """With 13 months, YoY is available only at index 12 (13th month)."""
        monthly = build_monthly_pnl_series(thirteen_month_df)
        growth  = calc_growth_series(monthly)
        # First 12 are NaN
        assert growth["yoy"]["revenue"].iloc[:12].isna().all()
        # Month 13 has a YoY value
        assert not pd.isna(growth["yoy"]["revenue"].iloc[12])

    def test_growth_series_returns_both_keys(self, two_month_df):
        monthly = build_monthly_pnl_series(two_month_df)
        growth  = calc_growth_series(monthly)
        assert "mom" in growth and "yoy" in growth


# ── build_growth_response ─────────────────────────────────────────────────────

class TestBuildGrowthResponse:
    def test_response_shape(self, two_month_df):
        r = build_growth_response(two_month_df, metric="revenue")
        assert r["metric"]  == "revenue"
        assert len(r["periods"])  == 2
        assert len(r["values"])   == 2
        assert len(r["mom_pct"])  == 2
        assert len(r["yoy_pct"])  == 2

    def test_first_mom_is_none(self, two_month_df):
        """First period MoM must be None (no prior period)."""
        r = build_growth_response(two_month_df, metric="revenue")
        assert r["mom_pct"][0] is None

    def test_second_mom_correct(self, two_month_df):
        r = build_growth_response(two_month_df, metric="revenue")
        assert r["mom_pct"][1] == pytest.approx(10.0)

    def test_values_correct(self, two_month_df):
        r = build_growth_response(two_month_df, metric="revenue")
        assert r["values"][0] == pytest.approx(1000.0)
        assert r["values"][1] == pytest.approx(1100.0)

    def test_empty_df_returns_empty_lists(self):
        r = build_growth_response(pd.DataFrame(), metric="revenue")
        assert r["periods"] == []
        assert r["values"]  == []

    def test_unknown_metric_returns_empty(self, two_month_df):
        r = build_growth_response(two_month_df, metric="nonexistent_metric")
        assert r["periods"] == []
