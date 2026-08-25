"""
FinSight — Page 2: Dashboard
Phase 1, Prompt 8.

Displays:
  - KPI cards: Revenue, EBITDA, Net Income, Gross Margin %, Budget Variance
  - Plotly line/bar chart of Actual vs Budget revenue over time
  - MoM and YoY growth trends (added in Phase 2 Prompt 10)

Calls GET /financials/pnl and GET /financials/variance only.
NO financial calculations in this file.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import sys, os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api_client

st.set_page_config(page_title="FinSight — Dashboard", page_icon="📊", layout="wide")

st.title("📊 Financial Dashboard")
st.caption("All numbers are computed by the backend — the UI only renders results.")
st.divider()

# ── Filters ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔍 Filters")
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

# ── Fetch data ────────────────────────────────────────────────────────────────
try:
    pnl = api_client.get_pnl(
        department=dept_filter,
        region=region_filter,
        product=product_filter,
        start_date=str(start_date),
        end_date=str(end_date),
    )
    variance = api_client.get_variance(
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
        st.warning("No financial data found. Please upload actuals and budget files on the Upload page first.")
    else:
        st.error(f"Backend error: {e}")

if data_loaded:
    # ── KPI Cards ─────────────────────────────────────────────────────────────
    st.subheader("Key Performance Indicators")

    rev_var = variance["revenue"]
    ebitda_var = variance["ebitda"]
    net_var = variance["net_income"]
    gm_var = variance["gross_margin_pct"]

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        rev_delta = rev_var["variance"]
        rev_color = "normal" if rev_var["favorable"] else "inverse"
        st.metric(
            "💰 Revenue",
            f"₹{pnl['revenue']:,.0f}K",
            delta=f"₹{rev_delta:+,.0f}K vs Budget",
            delta_color=rev_color,
        )

    with col2:
        ebitda_delta = ebitda_var["variance"]
        ebitda_color = "normal" if ebitda_var["favorable"] else "inverse"
        st.metric(
            "📈 EBITDA",
            f"₹{pnl['ebitda']:,.0f}K",
            delta=f"₹{ebitda_delta:+,.0f}K vs Budget",
            delta_color=ebitda_color,
        )

    with col3:
        net_delta = net_var["variance"]
        net_color = "normal" if net_var["favorable"] else "inverse"
        st.metric(
            "🏦 Net Income",
            f"₹{pnl['net_income']:,.0f}K",
            delta=f"₹{net_delta:+,.0f}K vs Budget",
            delta_color=net_color,
        )

    with col4:
        st.metric(
            "📊 Gross Margin",
            f"{pnl['gross_margin_pct']:.1f}%",
            delta=f"{gm_var['variance']:+.1f}pp vs Budget",
            delta_color="normal" if gm_var["favorable"] else "inverse",
        )

    with col5:
        ebitda_pct = variance["ebitda"]["variance_pct"]
        pct_label = f"{ebitda_pct:+.1f}%" if ebitda_pct is not None else "N/A"
        favorable_icon = "✅" if ebitda_var["favorable"] else "⚠️"
        st.metric(
            "📉 EBITDA Variance %",
            pct_label,
            delta=f"{favorable_icon} {ebitda_var['label']}",
            delta_color="normal" if ebitda_var["favorable"] else "inverse",
        )

    st.divider()

    # ── Actual vs Budget Bar Chart ─────────────────────────────────────────────
    st.subheader("Actual vs Budget — Core Metrics")

    metrics = ["revenue", "gross_profit", "ebitda", "net_income"]
    labels  = ["Revenue", "Gross Profit", "EBITDA", "Net Income"]

    actual_vals = [pnl[m] for m in metrics]
    budget_vals = [variance[m]["budget"] for m in metrics]

    fig = go.Figure(data=[
        go.Bar(name="Actual", x=labels, y=actual_vals,
               marker_color="#4F8EF7", text=[f"₹{v:,.0f}" for v in actual_vals],
               textposition="outside"),
        go.Bar(name="Budget", x=labels, y=budget_vals,
               marker_color="#A8C8FF", text=[f"₹{v:,.0f}" for v in budget_vals],
               textposition="outside"),
    ])
    fig.update_layout(
        barmode="group",
        title="Actual vs Budget (₹K)",
        yaxis_title="Amount (₹K)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=420,
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Variance Summary Table ─────────────────────────────────────────────────
    st.subheader("Variance Summary")

    table_data = []
    for metric, label in [
        ("revenue", "Revenue"), ("cogs", "COGS"), ("gross_profit", "Gross Profit"),
        ("opex", "Opex"), ("ebitda", "EBITDA"), ("net_income", "Net Income"),
    ]:
        v = variance[metric]
        table_data.append({
            "Metric":       label,
            "Actual (₹K)":  f"₹{v['actual']:,.0f}",
            "Budget (₹K)":  f"₹{v['budget']:,.0f}",
            "Variance":     f"₹{v['variance']:+,.0f}",
            "Variance %":   f"{v['variance_pct']:+.1f}%" if v["variance_pct"] is not None else "N/A",
            "Favorability": v["label"],
        })

    import pandas as pd
    df_table = pd.DataFrame(table_data)
    st.dataframe(df_table, use_container_width=True, hide_index=True)

    # ── MoM Growth Summary ────────────────────────────────────────────────────
    st.subheader("Latest Month-over-Month Revenue Growth")
    try:
        growth_data = api_client.get_growth(
            metric="revenue",
            department=dept_filter,
            region=region_filter,
            product=product_filter,
            start_date=str(start_date),
            end_date=str(end_date),
        )
        mom_vals = [(p, m) for p, m in zip(growth_data["periods"], growth_data["mom_pct"]) if m is not None]
        if mom_vals:
            import plotly.graph_objects as _go2
            mom_p, mom_v = zip(*mom_vals[-12:])  # last 12 months
            colors_d = ["#2ECC71" if v >= 0 else "#E74C3C" for v in mom_v]
            fig_d = _go2.Figure()
            fig_d.add_trace(_go2.Bar(
                x=list(mom_p), y=list(mom_v),
                marker_color=colors_d,
                text=[f"{v:+.1f}%" for v in mom_v],
                textposition="outside",
            ))
            fig_d.add_hline(y=0, line_dash="dash", line_color="#95A5A6")
            fig_d.update_layout(
                yaxis_title="MoM Revenue Growth %",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                height=280,
                showlegend=False,
            )
            st.plotly_chart(fig_d, use_container_width=True)
            st.caption("📈 Full MoM/YoY analytics on the **Growth Trends** page.")
        else:
            st.info("No MoM data available for selected filters.")
    except Exception:
        st.info("📌 MoM/YoY growth trends available on the Growth Trends page.")
