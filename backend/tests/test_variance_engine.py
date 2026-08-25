"""
FinSight — Unit Tests: Variance Engine
Phase 1, Prompt 6. Tests every function in variance_engine.py (§8.2, §8.3).

Covers:
  - Normal variance and variance %
  - Zero-budget edge case (variance_pct must return None, not raise)
  - Negative variance for revenue-type metric → Unfavorable
  - Positive variance for revenue-type metric → Favorable
  - Positive variance for cost-type metric → Unfavorable (more spend = bad)
  - Negative variance for cost-type metric → Favorable (underspend = good)
  - Full variance report via compute_variance_report()
"""

import pandas as pd
import pytest

from app.services.variance_engine import (
    calc_variance,
    calc_variance_pct,
    compute_variance_report,
    favorability_label,
    is_favorable,
)


# ─────────────────────────────────────────────────────────────────────────────
# §8.2 — Variance calculation
# ─────────────────────────────────────────────────────────────────────────────

class TestCalcVariance:
    def test_positive_variance(self):
        assert calc_variance(1100.0, 1000.0) == pytest.approx(100.0)

    def test_negative_variance(self):
        assert calc_variance(900.0, 1000.0) == pytest.approx(-100.0)

    def test_zero_variance(self):
        assert calc_variance(500.0, 500.0) == pytest.approx(0.0)


class TestCalcVariancePct:
    def test_positive(self):
        assert calc_variance_pct(1100.0, 1000.0) == pytest.approx(10.0)

    def test_negative(self):
        assert calc_variance_pct(900.0, 1000.0) == pytest.approx(-10.0)

    def test_zero_budget_returns_none(self):
        """§8.2 — budget=0 must return None, not raise ZeroDivisionError."""
        assert calc_variance_pct(500.0, 0.0) is None

    def test_zero_variance(self):
        assert calc_variance_pct(1000.0, 1000.0) == pytest.approx(0.0)


# ─────────────────────────────────────────────────────────────────────────────
# §8.3 — Favorability classification
# ─────────────────────────────────────────────────────────────────────────────

class TestIsFavorable:
    # Revenue-type: positive variance = Favorable
    def test_revenue_positive_variance_is_favorable(self):
        assert is_favorable("revenue", 100.0) is True

    def test_revenue_negative_variance_is_unfavorable(self):
        assert is_favorable("revenue", -50.0) is False

    # Profit-type: same logic
    def test_gross_profit_positive_is_favorable(self):
        assert is_favorable("gross_profit", 200.0) is True

    def test_ebitda_negative_is_unfavorable(self):
        assert is_favorable("ebitda", -300.0) is False

    def test_net_income_positive_is_favorable(self):
        assert is_favorable("net_income", 50.0) is True

    # Cost-type: positive variance (overspend) = Unfavorable
    def test_cogs_positive_variance_is_unfavorable(self):
        """COGS went up vs budget — that's bad (Unfavorable)."""
        assert is_favorable("cogs", 100.0) is False

    def test_opex_positive_variance_is_unfavorable(self):
        assert is_favorable("opex", 50.0) is False

    def test_cogs_negative_variance_is_favorable(self):
        """COGS came in below budget — that's good (Favorable)."""
        assert is_favorable("cogs", -80.0) is True

    def test_opex_negative_variance_is_favorable(self):
        assert is_favorable("opex", -30.0) is True

    # Granular opex categories are also cost-type
    def test_advertising_overspend_is_unfavorable(self):
        assert is_favorable("advertising", 400.0) is False

    def test_salaries_underspend_is_favorable(self):
        assert is_favorable("salaries", -100.0) is True

    # Unknown metric
    def test_unknown_metric_returns_none(self):
        assert is_favorable("unknown_metric_xyz", 50.0) is None


class TestFavorabilityLabel:
    def test_favorable_label(self):
        assert favorability_label("revenue", 100.0) == "Favorable"

    def test_unfavorable_label_revenue(self):
        assert favorability_label("revenue", -100.0) == "Unfavorable"

    def test_unfavorable_label_cost(self):
        assert favorability_label("cogs", 200.0) == "Unfavorable"

    def test_favorable_label_cost(self):
        assert favorability_label("opex", -50.0) == "Favorable"

    def test_unknown_label(self):
        assert favorability_label("mystery", 0.0) == "Unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Full variance report
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def actual_df():
    return pd.DataFrame([
        {"account_type": "revenue",  "amount": 1100.0},
        {"account_type": "cogs",     "amount": 450.0},  # overspend vs budget
        {"account_type": "opex",     "amount": 180.0},  # underspend vs budget
        {"account_type": "da",       "amount": 30.0},
        {"account_type": "interest", "amount": 20.0},
        {"account_type": "tax",      "amount": 100.0},
    ])


@pytest.fixture
def budget_df():
    return pd.DataFrame([
        {"account_type": "revenue",  "amount": 1000.0},
        {"account_type": "cogs",     "amount": 400.0},
        {"account_type": "opex",     "amount": 200.0},
        {"account_type": "da",       "amount": 30.0},
        {"account_type": "interest", "amount": 20.0},
        {"account_type": "tax",      "amount": 90.0},
    ])


class TestComputeVarianceReport:
    def test_revenue_variance_favorable(self, actual_df, budget_df):
        report = compute_variance_report(actual_df, budget_df)
        rev = report["revenue"]
        # Hand-computed: actual=1100, budget=1000, var=+100, var%=+10%
        assert rev["actual"]       == pytest.approx(1100.0)
        assert rev["budget"]       == pytest.approx(1000.0)
        assert rev["variance"]     == pytest.approx(100.0)
        assert rev["variance_pct"] == pytest.approx(10.0)
        assert rev["favorable"]    is True
        assert rev["label"]        == "Favorable"

    def test_cogs_variance_unfavorable(self, actual_df, budget_df):
        report = compute_variance_report(actual_df, budget_df)
        cogs = report["cogs"]
        # actual=450, budget=400, var=+50 → overspend → Unfavorable
        assert cogs["variance"]  == pytest.approx(50.0)
        assert cogs["favorable"] is False
        assert cogs["label"]     == "Unfavorable"

    def test_opex_variance_favorable(self, actual_df, budget_df):
        report = compute_variance_report(actual_df, budget_df)
        opex = report["opex"]
        # actual=180, budget=200, var=-20 → underspend → Favorable
        assert opex["variance"]  == pytest.approx(-20.0)
        assert opex["favorable"] is True
        assert opex["label"]     == "Favorable"

    def test_zero_budget_variance_pct_is_none(self):
        """When budget=0, variance_pct must be None — not raise."""
        actual_df = pd.DataFrame([
            {"account_type": "revenue",  "amount": 100.0},
            {"account_type": "cogs",     "amount": 0.0},
            {"account_type": "opex",     "amount": 0.0},
            {"account_type": "da",       "amount": 0.0},
            {"account_type": "interest", "amount": 0.0},
            {"account_type": "tax",      "amount": 0.0},
        ])
        budget_df = pd.DataFrame([
            {"account_type": "revenue",  "amount": 0.0},  # budget revenue = 0
            {"account_type": "cogs",     "amount": 0.0},
            {"account_type": "opex",     "amount": 0.0},
            {"account_type": "da",       "amount": 0.0},
            {"account_type": "interest", "amount": 0.0},
            {"account_type": "tax",      "amount": 0.0},
        ])
        report = compute_variance_report(actual_df, budget_df)
        assert report["revenue"]["variance_pct"] is None

    def test_all_metrics_present_in_report(self, actual_df, budget_df):
        report = compute_variance_report(actual_df, budget_df)
        expected_metrics = {
            "revenue", "cogs", "gross_profit", "gross_margin_pct",
            "opex", "operating_income", "da", "ebitda",
            "interest", "pretax_income", "tax", "net_income",
        }
        assert set(report.keys()) == expected_metrics



class TestDecomposeEbitdaVariance:
    """
    §8.5 EBITDA driver decomposition tests.
    Key invariant: sum(named drivers) + Other == total EBITDA variance EXACTLY.
    This is a hard architectural requirement per the Blueprint.
    """

    def _make_dfs(self, rev_actual, cogs_actual, mkt_actual, infra_actual,
                  rev_budget, cogs_budget, mkt_budget, infra_budget):
        """Build minimal actual/budget DataFrames for decomposition tests."""
        actual = pd.DataFrame([
            {"account_type": "revenue",  "account_category": "Product Revenue",    "amount": rev_actual},
            {"account_type": "cogs",     "account_category": "Cost of Goods Sold", "amount": cogs_actual},
            {"account_type": "opex",     "account_category": "Advertising",         "amount": mkt_actual},
            {"account_type": "opex",     "account_category": "Infrastructure",       "amount": infra_actual},
            {"account_type": "da",       "account_category": "D&A",                 "amount": 30.0},
            {"account_type": "interest", "account_category": "Interest",             "amount": 20.0},
            {"account_type": "tax",      "account_category": "Tax",                  "amount": 50.0},
        ])
        budget = pd.DataFrame([
            {"account_type": "revenue",  "account_category": "Product Revenue",    "amount": rev_budget},
            {"account_type": "cogs",     "account_category": "Cost of Goods Sold", "amount": cogs_budget},
            {"account_type": "opex",     "account_category": "Advertising",         "amount": mkt_budget},
            {"account_type": "opex",     "account_category": "Infrastructure",       "amount": infra_budget},
            {"account_type": "da",       "account_category": "D&A",                 "amount": 30.0},
            {"account_type": "interest", "account_category": "Interest",             "amount": 20.0},
            {"account_type": "tax",      "account_category": "Tax",                  "amount": 50.0},
        ])
        return actual, budget

    def test_drivers_sum_to_total_period_1(self):
        """§8.5 invariant: sum(drivers) == Total for period 1."""
        actual, budget = self._make_dfs(
            rev_actual=1100, cogs_actual=450, mkt_actual=300, infra_actual=80,
            rev_budget=1000, cogs_budget=400, mkt_budget=200, infra_budget=70,
        )
        from app.services.variance_engine import decompose_ebitda_variance
        drivers = decompose_ebitda_variance(actual, budget)

        named_sum = (
            drivers["Revenue"] + drivers["COGS"] +
            drivers["Marketing"] + drivers["Infrastructure"] + drivers["Other"]
        )
        assert named_sum == pytest.approx(drivers["Total"], abs=0.01), (
            f"Drivers don't sum to total: {named_sum} != {drivers['Total']}"
        )

    def test_drivers_sum_to_total_period_2(self):
        """§8.5 invariant: sum(drivers) == Total for a different set of inputs."""
        actual, budget = self._make_dfs(
            rev_actual=900, cogs_actual=380, mkt_actual=400, infra_actual=120,
            rev_budget=1000, cogs_budget=400, mkt_budget=200, infra_budget=80,
        )
        from app.services.variance_engine import decompose_ebitda_variance
        drivers = decompose_ebitda_variance(actual, budget)

        named_sum = (
            drivers["Revenue"] + drivers["COGS"] +
            drivers["Marketing"] + drivers["Infrastructure"] + drivers["Other"]
        )
        assert named_sum == pytest.approx(drivers["Total"], abs=0.01)

    def test_revenue_driver_sign(self):
        """Revenue increase → positive Revenue driver (more revenue = higher EBITDA)."""
        actual, budget = self._make_dfs(
            rev_actual=1200, cogs_actual=400, mkt_actual=200, infra_actual=70,
            rev_budget=1000, cogs_budget=400, mkt_budget=200, infra_budget=70,
        )
        from app.services.variance_engine import decompose_ebitda_variance
        drivers = decompose_ebitda_variance(actual, budget)
        assert drivers["Revenue"] == pytest.approx(200.0)

    def test_marketing_overspend_driver_is_negative(self):
        """Marketing overspend → negative Marketing driver (cost increase hurts EBITDA)."""
        actual, budget = self._make_dfs(
            rev_actual=1000, cogs_actual=400, mkt_actual=350, infra_actual=70,
            rev_budget=1000, cogs_budget=400, mkt_budget=200, infra_budget=70,
        )
        from app.services.variance_engine import decompose_ebitda_variance
        drivers = decompose_ebitda_variance(actual, budget)
        assert drivers["Marketing"] == pytest.approx(-150.0)

    def test_all_driver_keys_present(self):
        actual, budget = self._make_dfs(1000, 400, 200, 70, 1000, 400, 200, 70)
        from app.services.variance_engine import decompose_ebitda_variance
        drivers = decompose_ebitda_variance(actual, budget)
        assert set(drivers.keys()) == {"Revenue", "COGS", "Marketing", "Infrastructure", "Other", "Total"}

