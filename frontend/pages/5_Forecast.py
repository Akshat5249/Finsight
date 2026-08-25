"""
FinSight — Page 5: Forecast
Phase 3, Prompt 12.

Runs a forecast via POST /forecasts and plots actual history + forecast line.
No financial calculations in this file — all numbers from backend only.
"""

import streamlit as st
import plotly.graph_objects as go
import sys, os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api_client
import ui_components

st.set_page_config(page_title="FinSight — Forecast", page_icon="🔮", layout="wide")
ui_components.setup_ui()

st.title("🔮 Revenue & KPI Forecast")
st.caption("All forecasts computed by the backend — no arithmetic in the UI.")
st.divider()

METRICS = ["revenue", "gross_profit", "ebitda", "operating_income", "net_income",
           "cogs", "opex", "gross_margin_pct"]
MODELS  = ["linear_regression", "moving_average", "exponential_smoothing", "prophet"]

with st.sidebar:
    st.header("⚙️ Forecast Settings")
    metric   = st.selectbox("Metric",  METRICS)
    model    = st.selectbox("Model",   MODELS)
    horizon  = st.slider("Horizon (months)", 1, 24, 6)
    st.divider()
    dept     = st.selectbox("Department (training data)",
                             [None, "Engineering", "Sales", "Marketing", "Operations", "HR", "Finance"],
                             format_func=lambda x: "All" if x is None else x)
    region   = st.selectbox("Region",
                             [None, "India", "US", "Europe", "APAC"],
                             format_func=lambda x: "All" if x is None else x)
    product  = st.selectbox("Product",
                             [None, "Cloud Platform", "Analytics", "AI Solutions", "Consulting"],
                             format_func=lambda x: "All" if x is None else x)
    start_dt = st.date_input("Training Start", value=date(2024, 1, 1))
    end_dt   = st.date_input("Training End",   value=date(2025, 12, 31))

    with st.expander("Model Parameters"):
        window = st.number_input("MA Window (moving_average only)", min_value=1, max_value=12, value=3)
        alpha  = st.slider("Alpha (exponential_smoothing only)", 0.01, 1.0, 0.3)

run_btn = st.button("▶ Run Forecast", type="primary")

if run_btn:
    with st.spinner("Running forecast…"):
        try:
            payload = {
                "metric":     metric,
                "model":      model,
                "horizon":    horizon,
                "start_date": str(start_dt),
                "end_date":   str(end_dt),
            }
            if dept:    payload["department"] = dept
            if region:  payload["region"]     = region
            if product: payload["product"]    = product
            if model == "moving_average":        payload["window"] = int(window)
            if model == "exponential_smoothing": payload["alpha"]  = float(alpha)

            result = api_client._post_json("/forecasts", payload)
            st.session_state["forecast_result"] = result

            hist = api_client.get_growth(
                metric=metric,
                department=dept, region=region, product=product,
                start_date=str(start_dt), end_date=str(end_dt),
            )
            st.session_state["forecast_history"] = hist
            st.success(f"Forecast complete — run_id: {result['run_id']}")
        except Exception as e:
            st.error(f"Forecast error: {e}")

if "forecast_result" in st.session_state:
    result = st.session_state["forecast_result"]
    hist   = st.session_state.get("forecast_history", {})

    periods_f = [p["period"] for p in result["periods"]]
    values_f  = [p["forecast_value"] for p in result["periods"]]

    fig = go.Figure()
    if hist.get("periods"):
        fig.add_trace(go.Scatter(
            x=hist["periods"], y=hist["values"],
            mode="lines+markers",
            name="Actual",
            line=dict(color=ui_components.COLOR_PRIMARY, width=3),
            marker=dict(size=6),
        ))
    fig.add_trace(go.Scatter(
        x=periods_f, y=values_f,
        mode="lines+markers",
        name=f"Forecast ({result['model_used']})",
        line=dict(color=ui_components.COLOR_WARNING, width=3, dash="dash"),
        marker=dict(size=7, symbol="diamond"),
    ))
    if periods_f:
        fig.add_vrect(
            x0=periods_f[0], x1=periods_f[-1],
            fillcolor=ui_components.COLOR_WARNING, opacity=0.05, line_width=0,
        )
    fig.update_layout(
        title=dict(text=f"{metric.replace('_', ' ').title()} — Actual vs {result['model_used'].replace('_',' ').title()} Forecast", font=dict(size=16)),
        height=460,
    )
    fig = ui_components.apply_plotly_defaults(fig)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader(f"Forecast Values — {result['model_used']}")
    import pandas as pd
    df_f = pd.DataFrame(result["periods"])
    df_f.columns = ["Period", "Forecast"]
    
    st.dataframe(
        df_f, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Period": st.column_config.TextColumn("Period"),
            "Forecast": st.column_config.NumberColumn("Forecast (₹K)", format="₹%d"),
        }
    )
    st.caption(f"Run ID: {result['run_id']} · Horizon: {result['horizon']} months")
