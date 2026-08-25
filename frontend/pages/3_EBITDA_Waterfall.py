"""
FinSight — Page 3: EBITDA Waterfall
Phase 2, Prompt 9.

Fetches EBITDA driver decomposition from GET /financials/ebitda-waterfall.
Renders a Plotly waterfall chart. No financial logic in this file.
"""

import streamlit as st
import plotly.graph_objects as go
import sys, os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api_client
import ui_components

st.set_page_config(page_title="FinSight — EBITDA Waterfall", page_icon="🌊", layout="wide")
ui_components.setup_ui()

st.title("🌊 EBITDA Variance Waterfall")
st.caption(
    "Decomposes the EBITDA variance into its five named drivers. "
    "Drivers always reconcile exactly to the total EBITDA variance (§8.5)."
)
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
    start_date = st.date_input("Start Date", value=date(2024, 4, 1))
    end_date   = st.date_input("End Date",   value=date(2024, 6, 30))

# ── Fetch data ────────────────────────────────────────────────────────────────
try:
    data = api_client._get(
        "/financials/ebitda-waterfall",
        params={
            k: v for k, v in {
                "department": dept_filter,
                "region": region_filter,
                "product": product_filter,
                "start_date": str(start_date),
                "end_date": str(end_date),
            }.items() if v
        },
    )
    data_loaded = True
except Exception as e:
    data_loaded = False
    if "404" in str(e):
        st.warning("No data found. Upload actuals and budget files first.")
    else:
        st.error(f"Backend error: {e}")

if data_loaded:
    drivers = data["drivers"]
    total   = data["total_ebitda_variance"]
    favorable = data["favorable"]

    # ── KPI row ───────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    col1.metric(
        "Total EBITDA Variance",
        f"₹{total:+,.0f}K",
        delta="✅ Favorable" if favorable else "⚠️ Unfavorable",
        delta_color="normal" if favorable else "inverse",
    )
    col2.metric("Largest Positive Driver",
        next(
            (f"{k}: ₹{v:+,.0f}K" for k, v in sorted(drivers.items(), key=lambda x: -x[1])
             if k != "Total" and v > 0),
            "None"
        ),
        delta_color="normal",
    )
    col3.metric("Largest Negative Driver",
        next(
            (f"{k}: ₹{v:+,.0f}K" for k, v in sorted(drivers.items(), key=lambda x: x[1])
             if k != "Total" and v < 0),
            "None"
        ),
        delta_color="inverse",
    )

    st.divider()

    # ── Waterfall chart ───────────────────────────────────────────────────────
    DRIVER_ORDER = ["Revenue", "COGS", "Marketing", "Infrastructure", "Other", "Total"]
    driver_keys  = [d for d in DRIVER_ORDER if d in drivers and d != "Total"]
    driver_vals  = [drivers[d] for d in driver_keys]

    # Plotly waterfall: relative bars for drivers, absolute for Total
    measure = ["relative"] * len(driver_keys) + ["total"]
    x_labels = driver_keys + ["EBITDA Variance"]
    y_values = driver_vals + [total]

    # Color each bar by direction
    marker_colors = []
    for i, v in enumerate(y_values[:-1]):
        marker_colors.append(ui_components.COLOR_SUCCESS if v >= 0 else ui_components.COLOR_DANGER)
    marker_colors.append(ui_components.COLOR_PRIMARY)  # Total bar always primary color

    fig = go.Figure(go.Waterfall(
        name="EBITDA Drivers",
        orientation="v",
        measure=measure,
        x=x_labels,
        y=y_values,
        text=[f"₹{v:+,.0f}K" for v in y_values],
        textposition="outside",
        connector={"line": {"color": "#95A5A6", "width": 1, "dash": "dot"}},
        increasing={"marker": {"color": ui_components.COLOR_SUCCESS}},
        decreasing={"marker": {"color": ui_components.COLOR_DANGER}},
        totals={"marker":    {"color": ui_components.COLOR_PRIMARY}},
    ))
    fig.update_layout(
        title=dict(text="EBITDA Variance Waterfall — Driver Decomposition (§8.5)", font=dict(size=16)),
        height=500,
        showlegend=False,
        annotations=[dict(
            x=len(x_labels) - 1, y=total,
            text=f"Total: ₹{total:+,.0f}K",
            showarrow=False, yshift=20, font=dict(size=12, color=ui_components.COLOR_PRIMARY),
        )],
    )
    fig = ui_components.apply_plotly_defaults(fig)
    st.plotly_chart(fig, use_container_width=True)

    # ── Driver table ──────────────────────────────────────────────────────────
    st.subheader("Driver Breakdown")
    import pandas as pd

    rows = []
    for k in driver_keys:
        v = drivers[k]
        rows.append({
            "Driver":          k,
            "Contribution":    v,
            "Direction":       "↑ Positive" if v >= 0 else "↓ Negative",
            "% of Total":      f"{(v / total * 100):+.1f}%" if total != 0 else "N/A",
        })
    rows.append({
        "Driver":          "EBITDA Total",
        "Contribution":    total,
        "Direction":       "✅ Favorable" if favorable else "⚠️ Unfavorable",
        "% of Total":      "100.0%",
    })
    
    df_rows = pd.DataFrame(rows)
    st.dataframe(
        df_rows, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Driver": st.column_config.TextColumn("Driver", width="medium"),
            "Contribution": st.column_config.NumberColumn("Contribution (₹K)", format="₹%d"),
            "Direction": st.column_config.TextColumn("Direction"),
            "% of Total": st.column_config.TextColumn("% of Total"),
        }
    )

    # Reconciliation check displayed for transparency
    named_sum = sum(drivers[k] for k in driver_keys)
    residual  = abs(total - named_sum)
    if residual < 0.05:
        st.success(f"✅ Reconciliation check passed — drivers sum to ₹{named_sum:+,.2f}K (residual: ₹{residual:.4f}K)")
    else:
        st.error(f"⚠️ Reconciliation mismatch: drivers sum to {named_sum:+,.2f} but total is {total:+,.2f}")

    # Add the waterfall API call to the api_client for completeness
