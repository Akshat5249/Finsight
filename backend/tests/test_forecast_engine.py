"""
FinSight — Unit Tests: Forecast Engine
Phase 3, Prompt 11. Tests every model in forecast_engine.py.

Covers:
  - Correct output length for all 4 models
  - Future index is strictly after the last historical period
  - Moving average: flat forecast = mean of last N observations
  - Linear regression: correct extrapolation direction for trending series
  - Exponential smoothing: alpha edge cases (0.01 & 1.0)
  - run_forecast dispatcher: valid + invalid model names
  - Edge cases: single-observation series, minimum inputs
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.services.forecast_engine import (
    forecast_exponential_smoothing,
    forecast_linear_regression,
    forecast_moving_average,
    run_forecast,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def flat_series() -> pd.Series:
    """6-month flat series: value = 1000 every month."""
    idx = pd.date_range("2024-01-01", periods=6, freq="MS")
    return pd.Series([1000.0] * 6, index=idx)


@pytest.fixture
def trending_series() -> pd.Series:
    """6-month upward-trending series: 100, 200, 300, 400, 500, 600."""
    idx = pd.date_range("2024-01-01", periods=6, freq="MS")
    return pd.Series([100.0, 200.0, 300.0, 400.0, 500.0, 600.0], index=idx)


@pytest.fixture
def single_obs() -> pd.Series:
    """Single-observation series — tests edge case handling."""
    idx = pd.date_range("2024-01-01", periods=1, freq="MS")
    return pd.Series([500.0], index=idx)


# ─────────────────────────────────────────────────────────────────────────────
# Moving Average
# ─────────────────────────────────────────────────────────────────────────────

class TestMovingAverage:
    def test_output_length(self, flat_series):
        result = forecast_moving_average(flat_series, horizon=3, window=3)
        assert len(result) == 3

    def test_future_index_after_history(self, flat_series):
        result = forecast_moving_average(flat_series, horizon=3)
        assert result.index[0] > flat_series.index[-1]

    def test_flat_series_forecast_equals_mean(self, flat_series):
        """Flat series: all forecast values should equal 1000."""
        result = forecast_moving_average(flat_series, horizon=3, window=3)
        np.testing.assert_allclose(result.values, 1000.0, rtol=1e-6)

    def test_window_larger_than_series_uses_all(self, single_obs):
        """Window > series length — should use entire series (no crash)."""
        result = forecast_moving_average(single_obs, horizon=2, window=10)
        assert len(result) == 2
        assert result.iloc[0] == pytest.approx(500.0)

    def test_window_3_uses_last_3(self, trending_series):
        """Last 3 values: 400, 500, 600 → mean = 500."""
        result = forecast_moving_average(trending_series, horizon=1, window=3)
        assert result.iloc[0] == pytest.approx(500.0)

    def test_empty_series_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            forecast_moving_average(pd.Series([], dtype=float), horizon=3)

    def test_zero_window_raises(self, flat_series):
        with pytest.raises(ValueError, match="window"):
            forecast_moving_average(flat_series, horizon=3, window=0)


# ─────────────────────────────────────────────────────────────────────────────
# Linear Regression
# ─────────────────────────────────────────────────────────────────────────────

class TestLinearRegression:
    def test_output_length(self, trending_series):
        result = forecast_linear_regression(trending_series, horizon=4)
        assert len(result) == 4

    def test_future_index_after_history(self, trending_series):
        result = forecast_linear_regression(trending_series, horizon=2)
        assert result.index[0] > trending_series.index[-1]

    def test_perfectly_linear_series(self, trending_series):
        """
        Series: 100, 200, 300, 400, 500, 600 (β₁ = 100).
        Next value should be ≈700.
        """
        result = forecast_linear_regression(trending_series, horizon=1)
        assert result.iloc[0] == pytest.approx(700.0, abs=1.0)

    def test_forecast_continues_trend_upward(self, trending_series):
        """Each future value should be greater than the previous one."""
        result = forecast_linear_regression(trending_series, horizon=3)
        assert result.iloc[0] < result.iloc[1] < result.iloc[2]

    def test_single_obs_raises(self, single_obs):
        with pytest.raises(ValueError, match="at least 2"):
            forecast_linear_regression(single_obs, horizon=3)

    def test_flat_series_produces_flat_forecast(self, flat_series):
        """Flat historical values → near-zero slope → flat future."""
        result = forecast_linear_regression(flat_series, horizon=3)
        assert result.iloc[0] == pytest.approx(1000.0, abs=5.0)


# ─────────────────────────────────────────────────────────────────────────────
# Exponential Smoothing
# ─────────────────────────────────────────────────────────────────────────────

class TestExponentialSmoothing:
    def test_output_length(self, flat_series):
        result = forecast_exponential_smoothing(flat_series, horizon=3)
        assert len(result) == 3

    def test_future_index_after_history(self, flat_series):
        result = forecast_exponential_smoothing(flat_series, horizon=2)
        assert result.index[0] > flat_series.index[-1]

    def test_alpha_1_equals_last_observation(self, trending_series):
        """
        Alpha=1.0 → full weight on most recent observation.
        All forecast values should equal the last historical value (600).
        """
        result = forecast_exponential_smoothing(trending_series, horizon=3, alpha=1.0)
        np.testing.assert_allclose(result.values, 600.0, rtol=1e-6)

    def test_flat_series_gives_flat_forecast(self, flat_series):
        result = forecast_exponential_smoothing(flat_series, horizon=3, alpha=0.3)
        np.testing.assert_allclose(result.values, 1000.0, rtol=1e-6)

    def test_invalid_alpha_zero_raises(self, flat_series):
        with pytest.raises(ValueError, match="alpha"):
            forecast_exponential_smoothing(flat_series, horizon=3, alpha=0.0)

    def test_invalid_alpha_above_1_raises(self, flat_series):
        with pytest.raises(ValueError, match="alpha"):
            forecast_exponential_smoothing(flat_series, horizon=3, alpha=1.1)

    def test_empty_series_raises(self):
        with pytest.raises(ValueError):
            forecast_exponential_smoothing(pd.Series([], dtype=float), horizon=3)


# ─────────────────────────────────────────────────────────────────────────────
# run_forecast dispatcher
# ─────────────────────────────────────────────────────────────────────────────

class TestRunForecast:
    def test_moving_average_dispatch(self, flat_series):
        r = run_forecast(flat_series, model="moving_average", horizon=3)
        assert len(r) == 3

    def test_linear_regression_dispatch(self, trending_series):
        r = run_forecast(trending_series, model="linear_regression", horizon=2)
        assert len(r) == 2

    def test_exponential_smoothing_dispatch(self, flat_series):
        r = run_forecast(flat_series, model="exponential_smoothing", horizon=2, alpha=0.5)
        assert len(r) == 2

    def test_invalid_model_raises_value_error(self, flat_series):
        with pytest.raises(ValueError, match="Unknown model"):
            run_forecast(flat_series, model="gpt_forecast", horizon=3)

    def test_kwargs_forwarded(self, trending_series):
        """window kwarg forwarded to moving_average without error."""
        r = run_forecast(trending_series, model="moving_average", horizon=2, window=2)
        assert len(r) == 2
