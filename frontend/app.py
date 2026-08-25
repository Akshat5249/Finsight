"""
FinSight — Streamlit Frontend Entrypoint
Minimal landing page for Phase 0. Full pages added Phase 1 onwards.
This file NEVER performs financial calculations — it only calls the backend API.
"""

import streamlit as st

st.set_page_config(
    page_title="FinSight — AI-Powered FP&A",
    page_icon="📊",
    layout="wide",
)

st.title("📊 FinSight")
st.subheader("AI-Powered FP&A & Financial Analytics Platform")

st.info(
    "Use the **sidebar** to navigate between pages. "
    "Upload your actuals and budget files to get started."
)

st.markdown(
    """
    **Phase 0 scaffold** — backend API and all feature pages are added in Phase 1 onwards.

    | Page | Phase | Description |
    |------|-------|-------------|
    | 1 Upload | Phase 1 | Upload actuals & budget Excel files |
    | 2 Dashboard | Phase 1 | KPI cards, Revenue vs Budget chart |
    | 3 Variance Drivers | Phase 2 | EBITDA waterfall decomposition |
    | 4 Drilldown | Phase 2 | Department / Region / Product breakdown |
    | 5 Forecast | Phase 3 | Rolling forecast with accuracy metrics |
    | 6 Scenarios | Phase 4 | What-if scenario planning |
    | 7 AI Analyst | Phase 5 | Grounded RAG chat with sources |
    | 8 Reports | Phase 6 | Excel / PDF / PPTX report generation |
    """
)
