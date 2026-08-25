"""
FinSight — Page 7: AI Analyst
Phase 5, Prompt 17.

Natural-language Q&A interface + AI executive commentary.
Calls POST /ai/ask and POST /ai/commentary.
No financial calculations in this file.
"""

import streamlit as st
import sys, os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api_client
import ui_components

st.set_page_config(page_title="FinSight — AI Analyst", page_icon="🤖", layout="wide")
ui_components.setup_ui()

st.title("🤖 AI Financial Analyst")
st.caption("Ask natural-language questions about your financial data. Powered by RAG over ingested fact documents.")

col_cfg, col_ingest = st.columns([3, 1])
with col_cfg:
    st.info(
        "💡 **AI Setup:** Set `OPENROUTER_API_KEY` (or `OPENAI_API_KEY`) and `QDRANT_URL` in your `.env` file to enable full AI features. "
        "In demo mode, the system returns a graceful configuration message."
    )
with col_ingest:
    with st.expander("📥 Ingest Fact Docs"):
        ingest_start = st.date_input("From", value=date(2024, 1, 1), key="ingest_start")
        ingest_end   = st.date_input("To",   value=date(2025, 12, 31), key="ingest_end")
        if st.button("Ingest into Qdrant", key="btn_ingest"):
            with st.spinner("Upserting fact documents…"):
                try:
                    r = api_client._post_json("/ai/ingest", {
                        "start_date": str(ingest_start),
                        "end_date":   str(ingest_end),
                    })
                    if r["success"]:
                        st.success(r["message"])
                    else:
                        st.warning(r["message"])
                except Exception as e:
                    st.error(f"Ingest error: {e}")

st.divider()

tab_qa, tab_commentary = st.tabs(["💬 Ask a Question", "📝 AI Commentary"])

with tab_qa:
    st.subheader("Natural-Language Financial Q&A")
    with st.form("qa_form"):
        question = st.text_area("Your question",
            placeholder="e.g. What drove the EBITDA decline in Q2 2024 for Marketing?", height=80)
        col1, col2 = st.columns(2)
        with col1:
            qa_dept  = st.selectbox("Department context",
                                     [None, "Engineering", "Sales", "Marketing", "Operations", "HR", "Finance"],
                                     format_func=lambda x: "All" if x is None else x, key="qa_dept")
            qa_start = st.date_input("From", value=date(2024, 1, 1), key="qa_start")
        with col2:
            top_k    = st.slider("Context docs (top-k)", 1, 10, 5)
            qa_end   = st.date_input("To",   value=date(2025, 12, 31), key="qa_end")
        submitted = st.form_submit_button("Ask FinSight AI ▶", type="primary")

    if submitted and question.strip():
        with st.spinner("Thinking…"):
            try:
                payload = {"question": question, "top_k": top_k,
                           "start_date": str(qa_start), "end_date": str(qa_end)}
                if qa_dept: payload["department"] = qa_dept
                st.session_state["qa_result"] = api_client._post_json("/ai/ask", payload)
            except Exception as e:
                st.error(f"Error: {e}")

    if "qa_result" in st.session_state:
        r = st.session_state["qa_result"]
        if not r["configured"]:
            st.warning(r["answer"])
        else:
            st.success("✅ AI Answer")
            st.markdown(r["answer"])
            if r["sources"]:
                with st.expander(f"📚 Sources ({len(r['sources'])} retrieved)"):
                    for i, src in enumerate(r["sources"], 1):
                        st.markdown(f"**Source {i}** (relevance: {src.get('score', 0):.3f})")
                        st.code(src.get("text", "")[:500], language=None)
            st.caption(f"Model: {r['model_used']}")

with tab_commentary:
    st.subheader("AI Executive Commentary")
    with st.form("commentary_form"):
        col1, col2 = st.columns(2)
        with col1:
            c_dept   = st.selectbox("Department",
                                     [None, "Engineering", "Sales", "Marketing", "Operations", "HR", "Finance"],
                                     format_func=lambda x: "All" if x is None else x, key="c_dept")
            c_region = st.selectbox("Region",
                                     [None, "India", "US", "Europe", "APAC"],
                                     format_func=lambda x: "All" if x is None else x, key="c_region")
        with col2:
            c_start  = st.date_input("Start Date", value=date(2024, 4, 1), key="c_start")
            c_end    = st.date_input("End Date",   value=date(2024, 6, 30), key="c_end")
        gen_btn = st.form_submit_button("Generate Commentary ▶", type="primary")

    if gen_btn:
        with st.spinner("Generating executive commentary…"):
            try:
                payload = {"start_date": str(c_start), "end_date": str(c_end)}
                if c_dept:   payload["department"] = c_dept
                if c_region: payload["region"]     = c_region
                st.session_state["commentary_result"] = api_client._post_json("/ai/commentary", payload)
            except Exception as e:
                st.error(f"Error: {e}")

    if "commentary_result" in st.session_state:
        cr = st.session_state["commentary_result"]
        if not cr.get("configured", True):
            st.warning(cr["commentary"])
        else:
            st.success("✅ AI Commentary")
            st.markdown(f'> {cr["commentary"]}')
