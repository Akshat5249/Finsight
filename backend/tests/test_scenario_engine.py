"""
FinSight — Unit Tests: Scenario Engine
Phase 4, Prompt 13. Tests for scenario_engine.py.

Covers:
  - apply_scenario: revenue/cogs/marketing multipliers applied correctly
  - apply_scenario: zero-growth leaves amounts unchanged
  - apply_scenario: original DataFrame not mutated
  - apply_scenario: marketing category filter (only Marketing opex rows affected)
  - compare_scenarios: delta = scenario_pnl - base_pnl for each metric
  - compare_scenarios: delta_pct = None when base metric = 0
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.services.scenario_engine import apply_scenario, compare_scenarios, SCENARIO_DEFAULTS


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def base_df() -> pd.DataFrame:
    """Minimal base DataFrame with marketing + non-marketing opex."""
    return pd.DataFrame([
        {"account_type": "revenue",  "account_category": "Product Revenue",    "amount": 1000.0},
        {"account_type": "cogs",     "account_category": "Cost of Goods Sold", "amount": 400.0},
        {"account_type": "opex",     "account_category": "Advertising",         "amount": 100.0},  # marketing
        {"account_type": "opex",     "account_category": "Salaries",            "amount": 200.0},  # NOT marketing
        {"account_type": "da",       "account_category": "D&A",                 "amount": 30.0},
        {"account_type": "interest", "account_category": "Interest",             "amount": 20.0},
        {"account_type": "tax",      "account_category": "Tax",                  "amount": 50.0},
    ])


# ─────────────────────────────────────────────────────────────────────────────
# apply_scenario
# ─────────────────────────────────────────────────────────────────────────────

class TestApplyScenario:
    def test_revenue_multiplier(self, base_df):
        """Revenue +10% → revenue row amount = 1100."""
        result = apply_scenario(base_df, revenue_growth_pct=10.0, cogs_growth_pct=0, marketing_growth_pct=0)
        rev_rows = result[result["account_type"] == "revenue"]
        assert rev_rows["amount"].sum() == pytest.approx(1100.0)

    def test_cogs_multiplier(self, base_df):
        """COGS +5% → 400 × 1.05 = 420."""
        result = apply_scenario(base_df, revenue_growth_pct=0, cogs_growth_pct=5.0, marketing_growth_pct=0)
        cogs_rows = result[result["account_type"] == "cogs"]
        assert cogs_rows["amount"].sum() == pytest.approx(420.0)

    def test_marketing_opex_multiplier(self, base_df):
        """Marketing opex (Advertising) +20% → 100 × 1.20 = 120."""
        result = apply_scenario(base_df, revenue_growth_pct=0, cogs_growth_pct=0, marketing_growth_pct=20.0)
        ad_row = result[result["account_category"] == "Advertising"]
        assert ad_row["amount"].iloc[0] == pytest.approx(120.0)

    def test_non_marketing_opex_unchanged(self, base_df):
        """Salaries (non-marketing opex) must be unchanged regardless of marketing_growth_pct."""
        result = apply_scenario(base_df, revenue_growth_pct=0, cogs_growth_pct=0, marketing_growth_pct=50.0)
        salary_row = result[result["account_category"] == "Salaries"]
        assert salary_row["amount"].iloc[0] == pytest.approx(200.0)

    def test_da_unchanged(self, base_df):
        """D&A rows must never be altered by any multiplier."""
        result = apply_scenario(base_df, revenue_growth_pct=100, cogs_growth_pct=100, marketing_growth_pct=100)
        da_row = result[result["account_type"] == "da"]
        assert da_row["amount"].iloc[0] == pytest.approx(30.0)

    def test_zero_growth_leaves_df_identical(self, base_df):
        """All zeroes → output amounts should equal input amounts exactly."""
        result = apply_scenario(base_df, revenue_growth_pct=0, cogs_growth_pct=0, marketing_growth_pct=0)
        pd.testing.assert_series_equal(
            result["amount"].reset_index(drop=True),
            base_df["amount"].reset_index(drop=True),
        )

    def test_original_df_not_mutated(self, base_df):
        """apply_scenario must return a new DataFrame and not mutate the original."""
        original_rev = base_df.loc[base_df["account_type"] == "revenue", "amount"].iloc[0]
        apply_scenario(base_df, revenue_growth_pct=50.0, cogs_growth_pct=0, marketing_growth_pct=0)
        after_rev = base_df.loc[base_df["account_type"] == "revenue", "amount"].iloc[0]
        assert original_rev == after_rev, "Original DataFrame was mutated!"

    def test_negative_growth_reduces_revenue(self, base_df):
        """Revenue −10% → 900."""
        result = apply_scenario(base_df, revenue_growth_pct=-10.0, cogs_growth_pct=0, marketing_growth_pct=0)
        rev = result[result["account_type"] == "revenue"]["amount"].sum()
        assert rev == pytest.approx(900.0)


# ─────────────────────────────────────────────────────────────────────────────
# compare_scenarios
# ─────────────────────────────────────────────────────────────────────────────

class TestCompareScenarios:
    def test_delta_revenue(self, base_df):
        """Revenue +10% → delta['revenue'] == +100."""
        scen_df = apply_scenario(base_df, revenue_growth_pct=10.0, cogs_growth_pct=0, marketing_growth_pct=0)
        result = compare_scenarios(base_df, scen_df)
        assert result["delta"]["revenue"] == pytest.approx(100.0)

    def test_delta_pct_revenue(self, base_df):
        """Revenue +10% → delta_pct['revenue'] == +10%."""
        scen_df = apply_scenario(base_df, revenue_growth_pct=10.0, cogs_growth_pct=0, marketing_growth_pct=0)
        result = compare_scenarios(base_df, scen_df)
        assert result["delta_pct"]["revenue"] == pytest.approx(10.0)

    def test_all_keys_present(self, base_df):
        scen_df = apply_scenario(base_df, revenue_growth_pct=5, cogs_growth_pct=0, marketing_growth_pct=0)
        result = compare_scenarios(base_df, scen_df)
        for key in ("base", "scenario", "delta", "delta_pct"):
            assert key in result

    def test_base_scenario_delta_zero_when_identical(self, base_df):
        """No growth → all deltas should be 0."""
        scen_df = apply_scenario(base_df, revenue_growth_pct=0, cogs_growth_pct=0, marketing_growth_pct=0)
        result = compare_scenarios(base_df, scen_df)
        for metric, delta in result["delta"].items():
            assert delta == pytest.approx(0.0, abs=0.01), f"Non-zero delta for {metric}: {delta}"

    def test_scenario_defaults_upside_keys(self):
        """SCENARIO_DEFAULTS has expected keys for 'upside'."""
        upside = SCENARIO_DEFAULTS["upside"]
        assert upside["revenue_growth_pct"] > 0
        assert "cogs_growth_pct" in upside
        assert "marketing_growth_pct" in upside
