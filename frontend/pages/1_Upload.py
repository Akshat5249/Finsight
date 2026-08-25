"""
FinSight — Page 1: Upload
Phase 1, Prompt 8.

Allows users to upload actuals and budget Excel files.
Calls POST /uploads/actuals and /uploads/budget on the backend.
Displays the returned data-quality validation report clearly.

NO financial calculations in this file — all processing happens in the backend.
"""

import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api_client

st.set_page_config(page_title="FinSight — Upload", page_icon="📤", layout="wide")

st.title("📤 Upload Financial Data")
st.markdown(
    "Upload your **actuals** and **budget** Excel files. "
    "The platform will validate each file and report any data-quality issues."
)
st.divider()

col1, col2 = st.columns(2)

# ── Upload Actuals ────────────────────────────────────────────────────────────
with col1:
    st.subheader("📊 Actuals File")
    st.caption("Upload your actuals Excel (.xlsx) file")

    actuals_file = st.file_uploader(
        "Choose actuals file", type=["xlsx", "csv"], key="actuals_uploader"
    )
    if actuals_file and st.button("Upload Actuals", type="primary", key="btn_upload_actuals"):
        with st.spinner("Uploading and validating actuals…"):
            try:
                result = api_client.upload_actuals(
                    actuals_file.read(), actuals_file.name
                )
                st.session_state["actuals_upload"] = result
                st.success(f"✅ Upload complete — ID: {result['id']}")
            except Exception as e:
                st.error(f"Upload failed: {e}")

    if "actuals_upload" in st.session_state:
        r = st.session_state["actuals_upload"]
        _report = r.get("validation_report", {})

        st.markdown("#### Validation Report")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Rows Processed", f"{r['rows_processed']:,}")
        c2.metric("Valid Records",  f"{r['valid_records']:,}")
        c3.metric("Warnings",       r['warning_count'], delta_color="inverse")
        c4.metric("Errors",         r['error_count'],   delta_color="inverse")

        status_color = "🟢" if r["status"] == "success" else "🔴"
        st.markdown(f"**Status:** {status_color} {r['status'].upper()}")

        issues = _report.get("issues", [])
        if issues:
            st.markdown("#### Issues Found")
            for issue in issues:
                icon = "🔴" if issue["level"] == "error" else "🟡"
                with st.expander(f"{icon} [{issue['level'].upper()}] {issue['type']}: {issue['detail']}"):
                    if issue.get("rows"):
                        st.write(f"Affected row indices (first 50): {issue['rows'][:50]}")
        else:
            st.success("No issues detected — data is clean!")


# ── Upload Budget ─────────────────────────────────────────────────────────────
with col2:
    st.subheader("📋 Budget File")
    st.caption("Upload your budget Excel (.xlsx) file")

    budget_file = st.file_uploader(
        "Choose budget file", type=["xlsx", "csv"], key="budget_uploader"
    )
    if budget_file and st.button("Upload Budget", type="primary", key="btn_upload_budget"):
        with st.spinner("Uploading and validating budget…"):
            try:
                result = api_client.upload_budget(
                    budget_file.read(), budget_file.name
                )
                st.session_state["budget_upload"] = result
                st.success(f"✅ Upload complete — ID: {result['id']}")
            except Exception as e:
                st.error(f"Upload failed: {e}")

    if "budget_upload" in st.session_state:
        r = st.session_state["budget_upload"]
        _report = r.get("validation_report", {})

        st.markdown("#### Validation Report")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Rows Processed", f"{r['rows_processed']:,}")
        c2.metric("Valid Records",  f"{r['valid_records']:,}")
        c3.metric("Warnings",       r['warning_count'], delta_color="inverse")
        c4.metric("Errors",         r['error_count'],   delta_color="inverse")

        status_color = "🟢" if r["status"] == "success" else "🔴"
        st.markdown(f"**Status:** {status_color} {r['status'].upper()}")

        issues = _report.get("issues", [])
        if issues:
            st.markdown("#### Issues Found")
            for issue in issues:
                icon = "🔴" if issue["level"] == "error" else "🟡"
                with st.expander(f"{icon} [{issue['level'].upper()}] {issue['type']}: {issue['detail']}"):
                    if issue.get("rows"):
                        st.write(f"Affected row indices (first 50): {issue['rows'][:50]}")
        else:
            st.success("No issues detected — data is clean!")
