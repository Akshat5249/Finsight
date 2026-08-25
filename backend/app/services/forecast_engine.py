"""
FinSight — Forecast Engine
Phase 3, Prompt 11. Implements §10 of the Blueprint.

Four forecasting models, all pure functions:
  1. Moving Average (simple, configurable window)
  2. Linear Regression (OLS via numpy, no sklearn dep needed)
  3. Exponential Smoothing (Holt's single exponential, alpha configurable)
  4. Prophet (Facebook Prophet via PyPI prophet package — Phase 3 only)

Ground rule from §10:
  - Every model takes a pd.Series of historical values (indexed by period)
    and returns a pd.Series of forecast values for the next N periods.
  - No DB calls. No API calls. Pure input→output.
  - The calling service handles DB persistence (Phase 3, Prompt 12).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# §10.1 — Moving Average
# ─────────────────────────────────────────────────────────────────────────────

def forecast_moving_average(
    series: pd.Series,
    horizon: int,
    window: int = 3,
) -> pd.Series:
    """
    Simple moving-average forecast.  [§10.1]

    Projects the mean of the last `window` observed values forward for
    `horizon` periods. The forecast is flat (all periods equal the window mean).

    Args:
        series:  Historical monthly values, ordered oldest→newest.
        horizon: Number of future periods to forecast.
        window:  Rolling window size (default 3).

    Returns:
        pd.Series of length `horizon` with DatetimeIndex of future periods.
    """
    if len(series) == 0:
        raise ValueError("series must have at least one observation")
    if window < 1:
        raise ValueError(f"window must be ≥ 1, got {window}")

    effective_window = min(window, len(series))
    mean_val = float(series.iloc[-effective_window:].mean())

    future_index = _future_monthly_index(series, horizon)
    forecast_values = np.full(horizon, mean_val)
    return pd.Series(forecast_values, index=future_index, name="forecast_moving_average")


# ─────────────────────────────────────────────────────────────────────────────
# §10.2 — Linear Regression (OLS)
# ─────────────────────────────────────────────────────────────────────────────

def forecast_linear_regression(
    series: pd.Series,
    horizon: int,
) -> pd.Series:
    """
    Ordinary Least-Squares linear-trend forecast.  [§10.2]

    Fits y = β₀ + β₁ × t to the historical series, where t is the integer
    time index (0, 1, 2, …, n−1). Extrapolates for t = n, n+1, …, n+horizon−1.

    Uses numpy (no sklearn dependency) for pure, auditable arithmetic.

    Returns:
        pd.Series of length `horizon` with DatetimeIndex of future periods.
    """
    n = len(series)
    if n < 2:
        raise ValueError("Linear regression requires at least 2 observations")

    t = np.arange(n, dtype=float)
    y = series.values.astype(float)

    # OLS solution: β = (XᵀX)⁻¹Xᵀy  where X = [1, t]
    X = np.column_stack([np.ones(n), t])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    beta0, beta1 = beta

    future_t = np.arange(n, n + horizon, dtype=float)
    forecast_values = beta0 + beta1 * future_t

    future_index = _future_monthly_index(series, horizon)
    return pd.Series(forecast_values, index=future_index, name="forecast_linear_regression")


# ─────────────────────────────────────────────────────────────────────────────
# §10.3 — Exponential Smoothing (Holt's single)
# ─────────────────────────────────────────────────────────────────────────────

def forecast_exponential_smoothing(
    series: pd.Series,
    horizon: int,
    alpha: float = 0.3,
) -> pd.Series:
    """
    Single Exponential Smoothing (SES) forecast.  [§10.3]

    S_t = α × y_t + (1 − α) × S_{t-1}   (recursion)
    Forecast: ŷ_{t+h} = S_n  (flat projection of the last smoothed level)

    Args:
        series: Historical series, oldest→newest.
        horizon: Periods to forecast.
        alpha:  Smoothing parameter ∈ (0, 1]. Higher = more weight on recent obs.

    Returns:
        pd.Series of length `horizon` with DatetimeIndex.
    """
    if not (0 < alpha <= 1):
        raise ValueError(f"alpha must be in (0, 1], got {alpha}")
    if len(series) == 0:
        raise ValueError("series must have at least one observation")

    # Initialise level with the first observation
    level = float(series.iloc[0])
    for val in series.iloc[1:]:
        level = alpha * float(val) + (1 - alpha) * level

    future_index = _future_monthly_index(series, horizon)
    forecast_values = np.full(horizon, level)
    return pd.Series(forecast_values, index=future_index, name="forecast_exponential_smoothing")


# ─────────────────────────────────────────────────────────────────────────────
# §10.4 — Prophet (Facebook/Meta's Prophet package)
# ─────────────────────────────────────────────────────────────────────────────

def forecast_prophet(
    series: pd.Series,
    horizon: int,
    yearly_seasonality: bool = True,
    weekly_seasonality: bool = False,
    daily_seasonality: bool = False,
) -> pd.Series:
    """
    Prophet forecast — recommended model for business time-series.  [§10.4]

    Requires the `prophet` package (installed via requirements.txt).
    Falls back to a linear-regression forecast if Prophet is unavailable,
    logging a warning — this avoids hard crashes in lightweight environments.

    Returns:
        pd.Series of length `horizon` with DatetimeIndex.
    """
    try:
        from prophet import Prophet  # type: ignore[import-untyped]
    except ImportError:
        import logging
        logging.getLogger(__name__).warning(
            "prophet not installed; falling back to linear_regression for this forecast"
        )
        return forecast_linear_regression(series, horizon)

    # Prophet expects a DataFrame with columns ds (date) and y (value)
    df = pd.DataFrame({"ds": series.index, "y": series.values.astype(float)})
    df["ds"] = pd.to_datetime(df["ds"])

    model = Prophet(
        yearly_seasonality=yearly_seasonality,
        weekly_seasonality=weekly_seasonality,
        daily_seasonality=daily_seasonality,
    )
    model.fit(df)

    future = model.make_future_dataframe(periods=horizon, freq="MS")
    forecast_df = model.predict(future)

    # Extract only the future horizon periods (tail)
    future_rows = forecast_df.tail(horizon)
    future_index = pd.DatetimeIndex(future_rows["ds"].values)
    forecast_values = future_rows["yhat"].values

    return pd.Series(forecast_values, index=future_index, name="forecast_prophet")


# ─────────────────────────────────────────────────────────────────────────────
# §10.5 — Unified entry point
# ─────────────────────────────────────────────────────────────────────────────

MODEL_REGISTRY: dict[str, callable] = {
    "moving_average":        forecast_moving_average,
    "linear_regression":     forecast_linear_regression,
    "exponential_smoothing": forecast_exponential_smoothing,
    "prophet":               forecast_prophet,
}


def run_forecast(
    series: pd.Series,
    model: str,
    horizon: int,
    **kwargs,
) -> pd.Series:
    """
    Dispatch to the correct model by name and return forecast Series.

    Args:
        series:  Historical values (pd.Series, DatetimeIndex, oldest→newest).
        model:   One of: moving_average | linear_regression |
                         exponential_smoothing | prophet
        horizon: Number of future monthly periods to forecast.
        **kwargs: Model-specific parameters forwarded transparently.

    Returns:
        pd.Series of `horizon` forecast values with DatetimeIndex.
    """
    if model not in MODEL_REGISTRY:
        raise ValueError(
            f"Unknown model '{model}'. Valid options: {sorted(MODEL_REGISTRY)}"
        )
    return MODEL_REGISTRY[model](series, horizon, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _future_monthly_index(series: pd.Series, horizon: int) -> pd.DatetimeIndex:
    """
    Given a historical Series, return a DatetimeIndex of the next `horizon`
    month-start dates immediately following the last observation.

    Handles both DatetimeIndex (preferred) and integer/RangeIndex fallback.
    """
    if isinstance(series.index, pd.DatetimeIndex) and len(series.index) > 0:
        last_period = series.index[-1].to_period("M")
        future_periods = pd.period_range(
            start=last_period + 1, periods=horizon, freq="M"
        )
        return future_periods.to_timestamp()
    else:
        # Fallback: integer-indexed — produce synthetic monthly dates from 2020-01
        base = pd.Timestamp("2020-01-01")
        return pd.date_range(start=base, periods=horizon, freq="MS")
