"""
FinSight — RAG Pipeline
Phase 5, Prompts 15–17. Implements §13 of the Blueprint.

Architecture:
  1. fact_doc_generator.py   — turns P&L snapshots into structured fact documents
  2. qdrant_client.py        — upsert/search wrapper around Qdrant
  3. rag_pipeline.py         — orchestrates: embed → retrieve → LLM → ground answer

Graceful degradation:
  If OPENAI_API_KEY or QDRANT_URL is not set, the pipeline returns a clearly-
  labelled "AI features require configuration" message instead of crashing.
  This allows the rest of the platform to work without AI credentials.

Environment variables (read from os.environ at call time, not import time):
  OPENAI_API_KEY       — required for embeddings + GPT calls
  QDRANT_URL           — Qdrant instance URL (default: http://localhost:6333)
  QDRANT_API_KEY       — optional, for Qdrant Cloud
  QDRANT_COLLECTION    — collection name (default: finsight_facts)
  OPENAI_EMBED_MODEL   — embedding model (default: text-embedding-3-small)
  OPENAI_CHAT_MODEL    — chat model     (default: gpt-4o-mini)
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any

import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# §13.1 — Fact Document Generator
# ─────────────────────────────────────────────────────────────────────────────

def generate_fact_doc(
    pnl: dict[str, float],
    metadata: dict[str, Any] | None = None,
) -> str:
    """
    Convert a P&L dict (from financial_engine.compute_pnl) into a structured
    text fact document suitable for embedding and RAG retrieval.

    Args:
        pnl:      Output of compute_pnl — all metrics present.
        metadata: Optional context (department, period, region, etc.)

    Returns:
        A multi-line string fact document.
    """
    meta = metadata or {}
    period    = meta.get("period",     "all periods")
    dept      = meta.get("department", "all departments")
    region    = meta.get("region",     "all regions")
    product   = meta.get("product",    "all products")

    lines = [
        f"FinSight Financial Fact Document",
        f"Period: {period}  |  Department: {dept}  |  Region: {region}  |  Product: {product}",
        f"",
        f"Revenue:          ₹{pnl['revenue']:>12,.2f}K",
        f"COGS:             ₹{pnl['cogs']:>12,.2f}K",
        f"Gross Profit:     ₹{pnl['gross_profit']:>12,.2f}K  ({pnl['gross_margin_pct']:.1f}% margin)",
        f"Operating Expense:₹{pnl['opex']:>12,.2f}K",
        f"Operating Income: ₹{pnl['operating_income']:>12,.2f}K",
        f"D&A:              ₹{pnl['da']:>12,.2f}K",
        f"EBITDA:           ₹{pnl['ebitda']:>12,.2f}K",
        f"Interest Expense: ₹{pnl['interest']:>12,.2f}K",
        f"Pre-Tax Income:   ₹{pnl['pretax_income']:>12,.2f}K",
        f"Tax:              ₹{pnl['tax']:>12,.2f}K",
        f"Net Income:       ₹{pnl['net_income']:>12,.2f}K",
    ]
    return "\n".join(lines)


def generate_variance_fact_doc(
    variance_report: dict,
    metadata: dict[str, Any] | None = None,
) -> str:
    """
    Convert a compute_variance_report output into a variance fact document.
    """
    meta    = metadata or {}
    period  = meta.get("period", "all periods")
    dept    = meta.get("department", "all departments")

    lines = [
        f"FinSight Variance Fact Document",
        f"Period: {period}  |  Department: {dept}",
        f"",
    ]
    for metric, v in variance_report.items():
        if not isinstance(v, dict):
            continue
        label    = v.get("label", "")
        variance = v.get("variance", 0)
        var_pct  = v.get("variance_pct")
        pct_str  = f" ({var_pct:+.1f}%)" if var_pct is not None else ""
        lines.append(
            f"{metric.replace('_',' ').title():25s}: "
            f"actual={v.get('actual', 0):>10,.0f}  "
            f"budget={v.get('budget', 0):>10,.0f}  "
            f"var={variance:>+10,.0f}{pct_str}  [{label}]"
        )
    return "\n".join(lines)


def _doc_id(text: str) -> str:
    """Deterministic UUID-ish ID based on SHA256 of the document text."""
    return hashlib.sha256(text.encode()).hexdigest()[:32]


# ─────────────────────────────────────────────────────────────────────────────
# §13.2 — Qdrant Upsert / Search
# ─────────────────────────────────────────────────────────────────────────────

def _get_embed_client():
    """
    Return an OpenAI-compatible client for embeddings + chat completions.
    Preference order:
      1. OPENROUTER_API_KEY  → uses OpenRouter (openrouter.ai/api/v1)
      2. OPENAI_API_KEY      → uses OpenAI directly
      3. Neither set         → returns None (graceful degradation)
    """
    try:
        from openai import OpenAI
    except ImportError:
        return None

    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    if openrouter_key:
        return OpenAI(
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",
        )

    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        return OpenAI(api_key=openai_key)

    return None


def _get_qdrant_client():
    """Return a QdrantClient or None if not configured."""
    url = os.getenv("QDRANT_URL", "")
    if not url:
        return None
    try:
        from qdrant_client import QdrantClient
        api_key = os.getenv("QDRANT_API_KEY") or None
        return QdrantClient(url=url, api_key=api_key, timeout=10)
    except Exception:
        return None


def embed_text(text: str) -> list[float] | None:
    """
    Embed a text string.
    Uses OPENAI_EMBED_MODEL env var, defaulting to text-embedding-3-small
    (supported by both OpenAI and OpenRouter).
    Returns None if no LLM provider is configured.
    """
    client = _get_embed_client()
    if client is None:
        return None

    model = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
    response = client.embeddings.create(input=[text], model=model)
    return response.data[0].embedding


def upsert_fact_doc(text: str, metadata: dict | None = None) -> bool:
    """
    Embed and upsert a fact document into Qdrant.
    Returns True on success, False if not configured.
    """
    qdrant = _get_qdrant_client()
    if qdrant is None:
        return False

    vector = embed_text(text)
    if vector is None:
        return False

    from qdrant_client.models import PointStruct
    collection = os.getenv("QDRANT_COLLECTION", "finsight_facts")

    _ensure_collection(qdrant, collection, len(vector))

    point = PointStruct(
        id=int(_doc_id(text)[:8], 16),   # int hash as ID
        vector=vector,
        payload={"text": text, "metadata": metadata or {}, "ingested_at": str(datetime.now(tz=timezone.utc))},
    )
    qdrant.upsert(collection_name=collection, points=[point])
    return True


def search_fact_docs(query: str, top_k: int = 5) -> list[dict]:
    """
    Embed the query and retrieve the top-k most semantically similar fact docs.
    Returns a list of dicts with 'text' and 'score'.
    Returns [] if not configured.
    """
    qdrant = _get_qdrant_client()
    if qdrant is None:
        return []

    vector = embed_text(query)
    if vector is None:
        return []

    collection = os.getenv("QDRANT_COLLECTION", "finsight_facts")
    try:
        results = qdrant.search(
            collection_name=collection,
            query_vector=vector,
            limit=top_k,
        )
        return [
            {"text": r.payload.get("text", ""), "score": r.score, "metadata": r.payload.get("metadata", {})}
            for r in results
        ]
    except Exception:
        return []


def _ensure_collection(qdrant, collection: str, vector_size: int) -> None:
    """Create the Qdrant collection if it doesn't already exist."""
    from qdrant_client.models import Distance, VectorParams
    existing = [c.name for c in qdrant.get_collections().collections]
    if collection not in existing:
        qdrant.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )


# ─────────────────────────────────────────────────────────────────────────────
# §13.3 — Grounded Q&A (RAG)
# ─────────────────────────────────────────────────────────────────────────────

_NOT_CONFIGURED_MSG = (
    "AI features are not yet configured. "
    "Please set OPENAI_API_KEY and QDRANT_URL in your .env file to enable "
    "natural-language Q&A and AI-generated commentary."
)

SYSTEM_PROMPT = """You are FinSight, an expert FP&A analyst AI.
Answer the user's financial question ONLY using the context documents provided.
Do NOT fabricate numbers. If the context does not contain enough information to
answer confidently, say so explicitly.
Always cite which fact document supports each claim.
Format numbers with commas and currency symbols where applicable."""


def ask_question(
    question: str,
    top_k: int = 5,
    extra_context: str | None = None,
) -> dict:
    """
    Answer a financial question using RAG:
      1. Embed the question
      2. Retrieve top-k fact docs from Qdrant
      3. Build grounded prompt
      4. Call OpenAI chat completion
      5. Return answer + sources + confidence metadata

    Returns:
        {
            "answer":   str,
            "sources":  list[dict],   # retrieved fact docs with scores
            "model":    str,
            "configured": bool,
        }
    """
    openai_client = _get_embed_client()
    if openai_client is None:
        return {"answer": _NOT_CONFIGURED_MSG, "sources": [], "model": "none", "configured": False}

    qdrant = _get_qdrant_client()
    if qdrant is None:
        return {"answer": _NOT_CONFIGURED_MSG, "sources": [], "model": "none", "configured": False}

    # Retrieve context
    sources = search_fact_docs(question, top_k=top_k)

    context_blocks = []
    for i, src in enumerate(sources, 1):
        context_blocks.append(f"[Context {i}] (relevance={src['score']:.3f})\n{src['text']}")

    if extra_context:
        context_blocks.append(f"[Live Context]\n{extra_context}")

    context_str = "\n\n---\n\n".join(context_blocks) if context_blocks else "No context documents available."

    user_message = f"""Context documents:

{context_str}

---

Question: {question}"""

    chat_model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
    response = openai_client.chat.completions.create(
        model=chat_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        temperature=0.1,   # low temp for factual financial answers
        max_tokens=1024,
    )

    answer = response.choices[0].message.content or ""
    return {
        "answer":     answer,
        "sources":    sources,
        "model":      chat_model,
        "configured": True,
    }


# ─────────────────────────────────────────────────────────────────────────────
# §13.4 — AI Commentary Generator
# ─────────────────────────────────────────────────────────────────────────────

COMMENTARY_SYSTEM_PROMPT = """You are a senior FP&A analyst writing a concise executive commentary.
Given the financial data provided, write 3–5 sentences of narrative commentary covering:
1. Revenue performance vs budget
2. EBITDA and margin trends
3. Key variance drivers
4. One forward-looking implication

Rules:
- Use only the numbers provided — do not fabricate data
- Use professional finance language
- Keep it under 150 words
- Do NOT use markdown headers; write in flowing paragraphs"""


def generate_commentary(
    pnl: dict[str, float],
    variance_report: dict,
    metadata: dict | None = None,
) -> str:
    """
    Generate executive AI commentary for a given P&L and variance report.
    Returns a graceful message if OpenAI is not configured.
    """
    client = _get_embed_client()
    if client is None:
        return _NOT_CONFIGURED_MSG

    meta   = metadata or {}
    period = meta.get("period", "the current period")
    dept   = meta.get("department", "all departments")

    # Build a compact context string for the commentary prompt
    variance_summary = []
    for m in ["revenue", "ebitda", "gross_profit", "net_income"]:
        if m in variance_report and isinstance(variance_report[m], dict):
            v = variance_report[m]
            variance_summary.append(
                f"{m.replace('_',' ').title()}: actual={v.get('actual',0):,.0f}, "
                f"budget={v.get('budget',0):,.0f}, var={v.get('variance',0):+,.0f} [{v.get('label','')}]"
            )

    user_message = f"""Financial data for {dept} — {period}:

P&L:
- Revenue: ₹{pnl['revenue']:,.0f}K  |  EBITDA: ₹{pnl['ebitda']:,.0f}K  |  Net Income: ₹{pnl['net_income']:,.0f}K
- Gross Margin: {pnl['gross_margin_pct']:.1f}%

Variance Summary:
{chr(10).join(variance_summary)}

Write the executive commentary."""

    chat_model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
    response = client.chat.completions.create(
        model=chat_model,
        messages=[
            {"role": "system", "content": COMMENTARY_SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        temperature=0.3,
        max_tokens=300,
    )
    return response.choices[0].message.content or ""
