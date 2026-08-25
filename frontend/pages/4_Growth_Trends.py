"""
FinSight — Page 4: Growth Trends
Phase 2, Prompt 10.

Plots MoM and YoY growth % for any P&L metric over time.
Data sourced exclusively from GET /analytics/growth — no math in this file.
"""

import streamlit as st
import plotly.graph_objects as go
import sys, os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api_client
import ui_components

st.set_page_config(page_title="FinSight — Growth Trends", page_icon="📈", layout="wide")
ui_components.setup_ui()

st.title("📈 Growth Trends")
st.caption("Month-over-Month and Year-over-Year growth for any P&L metric. All numbers from backend only.")
st.divider()

# ── Filters ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔍 Filters")
    metric = st.selectbox(
        "Metric",
        ["revenue", "gross_profit", "ebitda", "operating_income", "net_income",
         "cogs", "opex", "gross_margin_pct"],
        index=0,
    )
    dept_filter = st.selectbox(
        "Department",
        [None, "Engineering", "Sales", "Marketing", "Operations", "HR", "Finance"],
        format_func=lambda x: "All Departments" if x is None else x,
    )
    region_filter = st.selectbox(
        "Region",
        [None, "India", "US", "Europe", "APAC"],
        format_func=lambda x: "All Regions" if x is None else x,
    )
    product_filter = st.selectbox(
        "Product",
        [None, "Cloud Platform", "Analytics", "AI Solutions", "Consulting"],
        format_func=lambda x: "All Products" if x is None else x,
    )
    start_date = st.date_input("Start Date", value=date(2024, 1, 1))
    end_date   = st.date_input("End Date",   value=date(2026, 6, 30))

# ── Fetch ─────────────────────────────────────────────────────────────────────
try:
    data = api_client.get_growth(
        metric=metric,
        department=dept_filter,
        region=region_filter,
        product=product_filter,
        start_date=str(start_date),
        end_date=str(end_date),
    )
    data_loaded = True
except Exception as e:
    data_loaded = False
    if "404" in str(e):
        st.warning("No data found — upload actuals first.")
    else:
        st.error(f"Backend error: {e}")

if data_loaded:
    periods  = data["periods"]
    values   = data["values"]
    mom_pct  = data["mom_pct"]
    yoy_pct  = data["yoy_pct"]

    # ── KPI row ───────────────────────────────────────────────────────────────
    latest_mom = next((v for v in reversed(mom_pct) if v is not None), None)
    latest_yoy = next((v for v in reversed(yoy_pct) if v is not None), None)

    col1, col2, col3 = st.columns(3)
    col1.metric(
        f"Latest {metric.replace('_', ' ').title()}",
        f"₹{values[-1]:,.0f}K" if metric != "gross_margin_pct" else f"{values[-1]:.1f}%",
    )
    col2.metric(
        "Latest MoM Growth",
        f"{latest_mom:+.1f}%" if latest_mom is not None else "N/A",
        delta_color="normal" if latest_mom and latest_mom >= 0 else "inverse",
    )
    col3.metric(
        "Latest YoY Growth",
        f"{latest_yoy:+.1f}%" if latest_yoy is not None else "Insufficient data (need ≥13 months)",
        delta_color="normal" if latest_yoy and latest_yoy >= 0 else "inverse",
    )

    st.divider()

    # ── Absolute value trend chart ─────────────────────────────────────────────
    st.subheader(f"{metric.replace('_', ' ').title()} — Monthly Values")
    fig_val = go.Figure()
    fig_val.add_trace(go.Scatter(
        x=periods, y=values,
        mode="lines+markers",
        name=metric,
        line=dict(color=ui_components.COLOR_PRIMARY, width=3),
        marker=dict(size=6),
    ))
    fig_val.update_layout(
        height=320,
        showlegend=False,
    )
    fig_val = ui_components.apply_plotly_defaults(fig_val)
    st.plotly_chart(fig_val, use_container_width=True)

    # ── MoM Growth chart ──────────────────────────────────────────────────────
    st.subheader("Month-over-Month Growth %")
    mom_valid = [(p, v) for p, v in zip(periods, mom_pct) if v is not None]
    if mom_valid:
        mom_p, mom_v = zip(*mom_valid)
        colors_mom = [ui_components.COLOR_SUCCESS if v >= 0 else ui_components.COLOR_DANGER for v in mom_v]
        fig_mom = go.Figure()
        fig_mom.add_trace(go.Bar(
            x=list(mom_p), y=list(mom_v),
            marker_color=colors_mom,
            text=[f"{v:+.1f}%" for v in mom_v],
            textposition="outside",
        ))
        fig_mom.add_hline(y=0, line_dash="dash", line_color="#95A5A6")
        fig_mom.update_layout(
            height=320,
            showlegend=False,
        )
        fig_mom = ui_components.apply_plotly_defaults(fig_mom)
        st.plotly_chart(fig_mom, use_container_width=True)

    # ── YoY Growth chart ──────────────────────────────────────────────────────
    st.subheader("Year-over-Year Growth %")
    yoy_valid = [(p, v) for p, v in zip(periods, yoy_pct) if v is not None]
    if yoy_valid:
        yoy_p, yoy_v = zip(*yoy_valid)
        colors_yoy = [ui_components.COLOR_SUCCESS if v >= 0 else ui_components.COLOR_DANGER for v in yoy_v]
        fig_yoy = go.Figure()
        fig_yoy.add_trace(go.Bar(
            x=list(yoy_p), y=list(yoy_v),
            marker_color=colors_yoy,
            text=[f"{v:+.1f}%" for v in yoy_v],
            textposition="outside",
        ))
        fig_yoy.add_hline(y=0, line_dash="dash", line_color="#95A5A6")
        fig_yoy.update_layout(
            height=320,
            showlegend=False,
        )
        fig_yoy = ui_components.apply_plotly_defaults(fig_yoy)
        st.plotly_chart(fig_yoy, use_container_width=True)
    else:
        st.info("YoY growth requires at least 13 months of data. Select a wider date range.")
