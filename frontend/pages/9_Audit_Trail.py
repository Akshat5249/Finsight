"""
FinSight — Page 9: Audit Trail
Phase 7, Prompt 21.

Shows full data lineage — every upload, analysis run, forecast, and report.
Calls GET /audit/runs, GET /audit/uploads, GET /audit/runs/{id}/lineage.
No financial calculations in this file.
"""

import streamlit as st
import pandas as pd
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api_client

st.set_page_config(page_title="FinSight — Audit Trail", page_icon="🔍", layout="wide")

st.title("🔍 Audit Trail & Data Lineage")
st.caption("Full traceability: every number shown in the platform can be traced back to its source upload and code path.")
st.divider()

tab_runs, tab_uploads, tab_lineage = st.tabs(["📊 Analysis Runs", "📁 Upload History", "🔗 Data Lineage"])

# ── Tab 1: Analysis Runs ──────────────────────────────────────────────────────
with tab_runs:
    st.subheader("Analysis Runs")
    st.caption("Every forecast, scenario, and report is linked to an analysis run.")
    try:
        runs = api_client._get("/audit/runs", {"limit": 100})
        if runs:
            df = pd.DataFrame(runs)
            df.columns = [c.replace("_", " ").title() for c in df.columns]
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"Showing {len(runs)} most recent analysis runs.")
        else:
            st.info("No analysis runs yet. Run a Forecast or Scenario to create one.")
    except Exception as e:
        st.error(f"Error loading audit runs: {e}")

# ── Tab 2: Upload History ─────────────────────────────────────────────────────
with tab_uploads:
    st.subheader("Upload History")
    st.caption("All actuals and budget file uploads with ingestion status.")
    try:
        uploads = api_client._get("/audit/uploads", {"limit": 100})
        if uploads:
            df = pd.DataFrame(uploads)
            df.columns = [c.replace("_", " ").title() for c in df.columns]
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"Showing {len(uploads)} uploads.")
        else:
            st.info("No uploads yet. Go to the Upload page to ingest your first dataset.")
    except Exception as e:
        st.error(f"Error loading upload history: {e}")

# ── Tab 3: Data Lineage ────────────────────────────────────────────────────────
with tab_lineage:
    st.subheader("Data Lineage Explorer")
    st.caption("Trace a specific analysis run from source upload to computed outputs.")

    try:
        runs = api_client._get("/audit/runs", {"limit": 100})
        run_ids = [r["id"] for r in runs] if runs else []
    except Exception:
        run_ids = []

    if not run_ids:
        st.info("No analysis runs found. Run a Forecast first.")
    else:
        selected_run = st.selectbox("Select Analysis Run", run_ids,
                                    format_func=lambda x: f"Run #{x}")

        if st.button("Load Lineage", type="primary"):
            try:
                lineage = api_client._get(f"/audit/runs/{selected_run}/lineage")
                st.session_state["lineage"] = lineage
            except Exception as e:
                st.error(f"Error loading lineage: {e}")

        if "lineage" in st.session_state:
            lin = st.session_state["lineage"]
            st.markdown(f"### Run #{lin['run_id']} — Full Lineage")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**📁 Source Uploads**")
                if lin.get("actuals_upload"):
                    u = lin["actuals_upload"]
                    st.success(f"✅ Actuals — Upload #{u['id']} — {u['filename']} ({u['row_count'] or 0:,} rows)")
                else:
                    st.info("No actuals upload linked.")
                if lin.get("budget_upload"):
                    u = lin["budget_upload"]
                    st.success(f"✅ Budget — Upload #{u['id']} — {u['filename']} ({u['row_count'] or 0:,} rows)")
                else:
                    st.info("No budget upload linked.")

            with col2:
                st.markdown("**📊 Outputs**")
                fcs = lin.get("forecasts", [])
                rpts = lin.get("reports", [])
                st.metric("Forecast Periods", len(fcs))
                st.metric("Reports Generated", len(rpts))

            if fcs:
                st.markdown("**Forecast Periods**")
                st.dataframe(pd.DataFrame(fcs), use_container_width=True, hide_index=True)

            if rpts:
                st.markdown("**Generated Reports**")
                st.dataframe(pd.DataFrame(rpts), use_container_width=True, hide_index=True)
