"""
FinSight — Page 8: Report Downloads
Phase 6, Prompt 20.

Download Excel, PDF, or PPTX financial reports via GET /reports/download.
No financial calculations in this file.
"""

import streamlit as st
import sys, os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api_client

st.set_page_config(page_title="FinSight — Reports", page_icon="📄", layout="wide")

st.title("📄 Financial Reports")
st.caption("Download branded financial reports in Excel, PDF, or PowerPoint. All data computed by the backend.")
st.divider()

with st.sidebar:
    st.header("📋 Report Configuration")
    fmt      = st.selectbox("Format", ["excel", "pdf", "pptx"],
                             format_func=lambda x: {"excel": "📊 Excel (.xlsx)", "pdf": "📕 PDF (.pdf)",
                                                     "pptx": "📽️ PowerPoint (.pptx)"}[x])
    dept     = st.selectbox("Department",
                             [None, "Engineering", "Sales", "Marketing", "Operations", "HR", "Finance"],
                             format_func=lambda x: "All Departments" if x is None else x)
    region   = st.selectbox("Region",
                             [None, "India", "US", "Europe", "APAC"],
                             format_func=lambda x: "All Regions" if x is None else x)
    product  = st.selectbox("Product",
                             [None, "Cloud Platform", "Analytics", "AI Solutions", "Consulting"],
                             format_func=lambda x: "All Products" if x is None else x)
    start_dt = st.date_input("Start Date", value=date(2024, 1, 1))
    end_dt   = st.date_input("End Date",   value=date(2025, 12, 31))

# ── Format descriptions ───────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("""
    ### 📊 Excel Report
    - **P&L Summary** sheet — all 12 metrics  
    - **Variance Analysis** sheet — actual vs budget  
    - Color-coded favorable/unfavorable variances  
    - Professional branded formatting
    """)
with col2:
    st.markdown("""
    ### 📕 PDF Report
    - Multi-page A4 layout  
    - P&L table with brand colors  
    - Variance table with green/red highlighting  
    - Date-stamped with department & period
    """)
with col3:
    st.markdown("""
    ### 📽️ PowerPoint Deck
    - 4-slide executive deck  
    - Cover slide with period info  
    - KPI highlight cards  
    - Variance + Key Takeaways slides
    """)

st.divider()

# ── Download button ───────────────────────────────────────────────────────────
MIME_TYPES = {
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf":   "application/pdf",
    "pptx":  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
EXTS = {"excel": "xlsx", "pdf": "pdf", "pptx": "pptx"}
LABELS = {"excel": "📊 Download Excel", "pdf": "📕 Download PDF", "pptx": "📽️ Download PPTX"}

gen_btn = st.button(LABELS[fmt], type="primary", use_container_width=False)

if gen_btn:
    with st.spinner(f"Generating {fmt.upper()} report…"):
        try:
            params: dict = {"format": fmt, "start_date": str(start_dt), "end_date": str(end_dt)}
            if dept:    params["department"] = dept
            if region:  params["region"]     = region
            if product: params["product"]    = product

            file_bytes = api_client._download("/reports/download", params)

            filename = f"finsight_report_{start_dt.isoformat()}.{EXTS[fmt]}"
            st.download_button(
                label=f"⬇️ Save {filename}",
                data=file_bytes,
                file_name=filename,
                mime=MIME_TYPES[fmt],
                type="secondary",
            )
            st.success(f"✅ Report generated ({len(file_bytes):,} bytes). Click above to download.")
        except Exception as e:
            st.error(f"Report generation error: {e}")
