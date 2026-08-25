"""
FinSight — Unit Tests: Financial Engine
Phase 1, Prompt 6. Tests every function in financial_engine.py.

Tests cover:
  - Normal cases for every §8.1 formula
  - Zero-revenue edge case (gross_margin_pct)
  - Full P&L reconciliation against a hand-computed example dataset
  - §8.4 growth rate functions (MoM, YoY, zero-previous handling)
  - Series-based MoM/YoY growth helpers

IMPORTANT: Expected values in the reconciliation test are computed BY HAND
in this test file — they are NOT derived by calling the function under test.
"""

import pandas as pd
import pytest

from app.services.financial_engine import (
    calc_cogs,
    calc_da,
    calc_ebitda,
    calc_gross_margin_pct,
    calc_gross_profit,
    calc_interest,
    calc_mom_growth_pct,
    calc_mom_growth_series,
    calc_net_income,
    calc_opex,
    calc_operating_income,
    calc_pretax_income,
    calc_revenue,
    calc_tax,
    calc_yoy_growth_pct,
    calc_yoy_growth_series,
    compute_pnl,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def small_df() -> pd.DataFrame:
    """
    Minimal hand-crafted dataset for individual function tests.
    Expected P&L (computed by hand):
      Revenue        = 1000
      COGS           = 400
      Gross Profit   = 600
      Gross Margin % = 60.0
      Opex           = 200
      EBIT           = 400
      D&A            = 30
      EBITDA         = 430
      Interest       = 20
      Pre-tax        = 380
      Tax            = 95
      Net Income     = 285
    """
    return pd.DataFrame([
        {"account_type": "revenue",  "amount": 600.0},
        {"account_type": "revenue",  "amount": 400.0},
        {"account_type": "cogs",     "amount": 250.0},
        {"account_type": "cogs",     "amount": 150.0},
        {"account_type": "opex",     "amount": 120.0},
        {"account_type": "opex",     "amount": 80.0},
        {"account_type": "da",       "amount": 30.0},
        {"account_type": "interest", "amount": 20.0},
        {"account_type": "tax",      "amount": 95.0},
    ])


@pytest.fixture
def zero_revenue_df() -> pd.DataFrame:
    """Dataset where revenue = 0 — tests divide-by-zero guard in gross_margin_pct."""
    return pd.DataFrame([
        {"account_type": "revenue",  "amount": 0.0},
        {"account_type": "cogs",     "amount": 50.0},
        {"account_type": "opex",     "amount": 20.0},
        {"account_type": "da",       "amount": 5.0},
        {"account_type": "interest", "amount": 2.0},
        {"account_type": "tax",      "amount": 0.0},
    ])


# ─────────────────────────────────────────────────────────────────────────────
# §8.1 individual function tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRevenue:
    def test_normal(self, small_df):
        assert calc_revenue(small_df) == pytest.approx(1000.0)

    def test_empty_df(self):
        df = pd.DataFrame(columns=["account_type", "amount"])
        assert calc_revenue(df) == pytest.approx(0.0)


class TestCOGS:
    def test_normal(self, small_df):
        assert calc_cogs(small_df) == pytest.approx(400.0)


class TestGrossProfit:
    def test_normal(self):
        assert calc_gross_profit(1000.0, 400.0) == pytest.approx(600.0)

    def test_negative_when_cogs_exceed_revenue(self):
        assert calc_gross_profit(300.0, 500.0) == pytest.approx(-200.0)


class TestGrossMarginPct:
    def test_normal(self):
        assert calc_gross_margin_pct(600.0, 1000.0) == pytest.approx(60.0)

    def test_zero_revenue_returns_zero(self):
        """§8.1 — revenue=0 must not raise ZeroDivisionError."""
        assert calc_gross_margin_pct(0.0, 0.0) == pytest.approx(0.0)

    def test_zero_gross_profit(self):
        assert calc_gross_margin_pct(0.0, 500.0) == pytest.approx(0.0)


class TestOpex:
    def test_normal(self, small_df):
        assert calc_opex(small_df) == pytest.approx(200.0)


class TestOperatingIncome:
    def test_normal(self):
        assert calc_operating_income(600.0, 200.0) == pytest.approx(400.0)


class TestDA:
    def test_normal(self, small_df):
        assert calc_da(small_df) == pytest.approx(30.0)


class TestEBITDA:
    def test_normal(self):
        assert calc_ebitda(400.0, 30.0) == pytest.approx(430.0)


class TestInterest:
    def test_normal(self, small_df):
        assert calc_interest(small_df) == pytest.approx(20.0)


class TestPretaxIncome:
    def test_normal(self):
        assert calc_pretax_income(400.0, 20.0) == pytest.approx(380.0)


class TestTax:
    def test_normal(self, small_df):
        assert calc_tax(small_df) == pytest.approx(95.0)


class TestNetIncome:
    def test_normal(self):
        assert calc_net_income(380.0, 95.0) == pytest.approx(285.0)

    def test_negative(self):
        assert calc_net_income(-50.0, 0.0) == pytest.approx(-50.0)


# ─────────────────────────────────────────────────────────────────────────────
# Full P&L reconciliation test (hand-computed expected values)
# ─────────────────────────────────────────────────────────────────────────────

class TestComputePnlReconciliation:
    """
    Full reconciliation against a small, hand-computed dataset.
    Every expected value was derived by hand BEFORE looking at the function output.
    This test proves the whole P&L chain is internally consistent.
    """

    def test_full_pnl_chain(self, small_df):
        # Hand-computed expected values:
        #   revenue = 600 + 400 = 1000
        #   cogs    = 250 + 150 = 400
        #   gross_profit = 1000 - 400 = 600
        #   gross_margin_pct = 600/1000*100 = 60.0
        #   opex = 120 + 80 = 200
        #   operating_income = 600 - 200 = 400
        #   da = 30
        #   ebitda = 400 + 30 = 430
        #   interest = 20
        #   pretax_income = 400 - 20 = 380
        #   tax = 95
        #   net_income = 380 - 95 = 285

        pnl = compute_pnl(small_df)

        assert pnl["revenue"]          == pytest.approx(1000.0)
        assert pnl["cogs"]             == pytest.approx(400.0)
        assert pnl["gross_profit"]     == pytest.approx(600.0)
        assert pnl["gross_margin_pct"] == pytest.approx(60.0)
        assert pnl["opex"]             == pytest.approx(200.0)
        assert pnl["operating_income"] == pytest.approx(400.0)
        assert pnl["da"]               == pytest.approx(30.0)
        assert pnl["ebitda"]           == pytest.approx(430.0)
        assert pnl["interest"]         == pytest.approx(20.0)
        assert pnl["pretax_income"]    == pytest.approx(380.0)
        assert pnl["tax"]              == pytest.approx(95.0)
        assert pnl["net_income"]       == pytest.approx(285.0)

    def test_zero_revenue_dataset(self, zero_revenue_df):
        pnl = compute_pnl(zero_revenue_df)
        assert pnl["revenue"]          == pytest.approx(0.0)
        assert pnl["gross_margin_pct"] == pytest.approx(0.0)  # no ZeroDivisionError

    def test_all_keys_present(self, small_df):
        pnl = compute_pnl(small_df)
        expected_keys = {
            "revenue", "cogs", "gross_profit", "gross_margin_pct",
            "opex", "operating_income", "da", "ebitda",
            "interest", "pretax_income", "tax", "net_income",
        }
        assert set(pnl.keys()) == expected_keys


# ─────────────────────────────────────────────────────────────────────────────
# §8.4 Growth rate tests
# ─────────────────────────────────────────────────────────────────────────────

class TestMoMGrowthPct:
    def test_positive_growth(self):
        assert calc_mom_growth_pct(110.0, 100.0) == pytest.approx(10.0)

    def test_negative_growth(self):
        assert calc_mom_growth_pct(90.0, 100.0) == pytest.approx(-10.0)

    def test_zero_previous_returns_none(self):
        """Previous = 0 → undefined growth; must return None, not raise."""
        assert calc_mom_growth_pct(50.0, 0.0) is None

    def test_zero_growth(self):
        assert calc_mom_growth_pct(100.0, 100.0) == pytest.approx(0.0)


class TestYoYGrowthPct:
    def test_positive_growth(self):
        assert calc_yoy_growth_pct(1200.0, 1000.0) == pytest.approx(20.0)

    def test_negative_growth(self):
        assert calc_yoy_growth_pct(800.0, 1000.0) == pytest.approx(-20.0)

    def test_zero_base_returns_none(self):
        assert calc_yoy_growth_pct(500.0, 0.0) is None


class TestGrowthSeries:
    """Tests for Series-based growth helpers — covers lines 177-178, 187-188."""

    def test_mom_growth_series(self):
        s = pd.Series([100.0, 110.0, 121.0])
        result = calc_mom_growth_series(s)
        assert result.iloc[1] == pytest.approx(10.0)
        assert result.iloc[2] == pytest.approx(10.0)

    def test_yoy_growth_series(self):
        # 13 months: month 13 = 1.2× month 1
        values = [100.0] * 12 + [120.0]
        s = pd.Series(values)
        result = calc_yoy_growth_series(s)
        assert result.iloc[12] == pytest.approx(20.0)

    def test_mom_growth_series_first_element_is_nan(self):
        s = pd.Series([100.0, 110.0])
        result = calc_mom_growth_series(s)
        import math
        assert math.isnan(result.iloc[0])
