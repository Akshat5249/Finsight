"""
FinSight — Page 6: Scenario Planning
Phase 4, Prompt 14.

Interactive what-if scenario modeller. Calls POST /scenarios/run.
Displays side-by-side base vs scenario P&L with delta highlighting.
No financial calculations in this file.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api_client

st.set_page_config(page_title="FinSight — Scenarios", page_icon="🎲", layout="wide")

st.title("🎲 Scenario Planning")
st.caption("Adjust revenue, COGS, and marketing assumptions to model what-if outcomes. All calculations on the backend.")
st.divider()

with st.sidebar:
    st.header("⚙️ Scenario Configuration")
    scenario_type = st.selectbox("Scenario Preset", ["custom", "upside", "downside", "base"])

    if scenario_type == "upside":
        default_rev, default_cogs, default_mkt = 10.0, 5.0, 5.0
    elif scenario_type == "downside":
        default_rev, default_cogs, default_mkt = -10.0, 3.0, 8.0
    else:
        default_rev, default_cogs, default_mkt = 0.0, 0.0, 0.0

    st.markdown("**Assumption Overrides**")
    rev_pct = st.slider("Revenue Growth %",  -30.0, 30.0, default_rev, step=0.5)
    cogs_pct = st.slider("COGS Growth %",    -20.0, 30.0, default_cogs, step=0.5)
    mkt_pct  = st.slider("Marketing Growth %", -20.0, 50.0, default_mkt, step=0.5)

    st.divider()
    dept_filter = st.selectbox("Department",
        [None, "Engineering", "Sales", "Marketing", "Operations", "HR", "Finance"],
        format_func=lambda x: "All" if x is None else x)
    region_filter = st.selectbox("Region",
        [None, "India", "US", "Europe", "APAC"],
        format_func=lambda x: "All" if x is None else x)
    from datetime import date
    start_dt = st.date_input("Start Date", value=date(2024, 1, 1))
    end_dt   = st.date_input("End Date",   value=date(2025, 12, 31))

run_btn = st.button("▶ Run Scenario", type="primary")

if run_btn:
    with st.spinner("Running scenario…"):
        try:
            payload = {
                "name":                 scenario_type,
                "revenue_growth_pct":   rev_pct,
                "cogs_growth_pct":      cogs_pct,
                "marketing_growth_pct": mkt_pct,
                "start_date":           str(start_dt),
                "end_date":             str(end_dt),
            }
            if dept_filter:   payload["department"] = dept_filter
            if region_filter: payload["region"]     = region_filter

            result = api_client._post_json("/scenarios/run", payload)
            st.session_state["scenario_result"] = result
            st.success(f"Scenario complete — '{scenario_type}'")
        except Exception as e:
            st.error(f"Error: {e}")

if "scenario_result" in st.session_state:
    r = st.session_state["scenario_result"]
    base = r["base"]
    scen = r["scenario"]
    delta = r["delta"]
    delta_pct = r["delta_pct"]

    # ── Summary KPI row ───────────────────────────────────────────────────────
    st.subheader(f"'{r['scenario_name'].upper()}' Scenario vs Actuals")
    kpi_metrics = ["revenue", "ebitda", "net_income", "gross_margin_pct"]
    kpi_labels  = ["Revenue", "EBITDA", "Net Income", "Gross Margin %"]
    cols = st.columns(4)
    for col, metric, label in zip(cols, kpi_metrics, kpi_labels):
        d = delta[metric]
        dp = delta_pct.get(metric)
        dp_str = f"{dp:+.1f}%" if dp is not None else ""
        col.metric(
            label,
            f"₹{scen[metric]:,.0f}" if metric != "gross_margin_pct" else f"{scen[metric]:.1f}%",
            delta=f"₹{d:+,.0f} ({dp_str})" if metric != "gross_margin_pct" else f"{d:+.1f}pp",
            delta_color="normal" if d >= 0 else "inverse",
        )

    st.divider()

    # ── Side-by-side grouped bar ──────────────────────────────────────────────
    st.subheader("Base vs Scenario — Full P&L Comparison")
    metrics = ["revenue", "gross_profit", "ebitda", "net_income"]
    labels  = ["Revenue", "Gross Profit", "EBITDA", "Net Income"]

    fig = go.Figure(data=[
        go.Bar(name="Base",     x=labels, y=[base[m] for m in metrics],
               marker_color="#4F8EF7", text=[f"₹{base[m]:,.0f}" for m in metrics], textposition="outside"),
        go.Bar(name="Scenario", x=labels, y=[scen[m] for m in metrics],
               marker_color="#F39C12", text=[f"₹{scen[m]:,.0f}" for m in metrics], textposition="outside"),
    ])
    fig.update_layout(
        barmode="group",
        yaxis_title="₹K",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Delta waterfall ───────────────────────────────────────────────────────
    st.subheader("EBITDA Delta Breakdown")
    delta_metrics = ["revenue", "cogs", "opex", "da"]
    delta_labels  = ["Revenue Impact", "COGS Impact", "Opex Impact", "D&A Impact"]
    delta_vals    = [delta[m] for m in delta_metrics]

    fwf = go.Figure(go.Waterfall(
        name="Delta",
        orientation="v",
        measure=["relative", "relative", "relative", "relative", "total"],
        x=delta_labels + ["EBITDA Delta"],
        y=delta_vals + [delta["ebitda"]],
        text=[f"₹{v:+,.0f}" for v in delta_vals + [delta["ebitda"]]],
        textposition="outside",
        increasing={"marker": {"color": "#2ECC71"}},
        decreasing={"marker": {"color": "#E74C3C"}},
        totals={"marker":    {"color": "#4F8EF7"}},
        connector={"line": {"color": "#95A5A6", "width": 1, "dash": "dot"}},
    ))
    fwf.update_layout(
        yaxis_title="Δ ₹K",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=380,
        showlegend=False,
    )
    st.plotly_chart(fwf, use_container_width=True)

    # ── Full P&L comparison table ─────────────────────────────────────────────
    st.subheader("Full P&L Comparison Table")
    table_rows = []
    for m in ["revenue", "cogs", "gross_profit", "gross_margin_pct", "opex",
              "operating_income", "da", "ebitda", "interest", "pretax_income", "tax", "net_income"]:
        is_pct = m == "gross_margin_pct"
        fmt = lambda v, pct=is_pct: f"{v:.1f}%" if pct else f"₹{v:,.0f}"
        d = delta[m]
        dp = delta_pct.get(m)
        table_rows.append({
            "Metric":     m.replace("_", " ").title(),
            "Base":       fmt(base[m]),
            "Scenario":   fmt(scen[m]),
            "Delta":      f"₹{d:+,.0f}" if not is_pct else f"{d:+.1f}pp",
            "Delta %":    f"{dp:+.1f}%" if dp is not None else "—",
            "Direction":  "↑" if d > 0 else ("↓" if d < 0 else "→"),
        })
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

    # ── Assumptions summary ───────────────────────────────────────────────────
    with st.expander("📋 Scenario Assumptions Used"):
        st.json(r["assumptions"])
