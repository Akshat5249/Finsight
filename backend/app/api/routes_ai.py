"""
FinSight — AI Routes
Phase 5, Prompts 16–17.

POST /ai/ask        — Grounded Q&A via RAG (§13.3)
POST /ai/commentary — AI executive commentary for a P&L snapshot (§13.4)
POST /ai/ingest     — Upsert a fact document into Qdrant (§13.2)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.routes_financials import _load_actuals, _load_budgets
from app.db.session import get_db
from app.services.financial_engine import compute_pnl
from app.services.rag_pipeline import (
    ask_question,
    generate_commentary,
    generate_fact_doc,
    generate_variance_fact_doc,
    upsert_fact_doc,
)
from app.services.variance_engine import compute_variance_report

router = APIRouter(prefix="/ai", tags=["ai"])


# ── Request/Response schemas ──────────────────────────────────────────────────

class AskRequest(BaseModel):
    question:   str = Field(..., min_length=3, description="Natural-language financial question")
    top_k:      int = Field(5, ge=1, le=20, description="Number of context docs to retrieve")
    # Optional live-context filters (current P&L is appended to context)
    department:  str | None = None
    region:      str | None = None
    product:     str | None = None
    start_date:  str | None = None
    end_date:    str | None = None


class AskResponse(BaseModel):
    question:    str
    answer:      str
    sources:     list[dict]
    model_used:  str
    configured:  bool

    model_config = {"protected_namespaces": ()}


class CommentaryRequest(BaseModel):
    department:  str | None = None
    region:      str | None = None
    product:     str | None = None
    start_date:  str | None = None
    end_date:    str | None = None


class CommentaryResponse(BaseModel):
    commentary:  str
    configured:  bool


class IngestRequest(BaseModel):
    department:  str | None = None
    region:      str | None = None
    product:     str | None = None
    start_date:  str | None = None
    end_date:    str | None = None


class IngestResponse(BaseModel):
    success:     bool
    message:     str
    docs_upserted: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/ask", response_model=AskResponse)
def ask(
    request: AskRequest,
    db: Session = Depends(get_db),
) -> AskResponse:
    """
    Answer a financial question using RAG over ingested fact docs.
    Optionally appends live P&L context for the specified filter window.
    """
    # Build optional live context string
    extra_context = None
    try:
        actual_df = _load_actuals(
            db, request.department, request.region,
            request.product, request.start_date, request.end_date,
        )
        if not actual_df.empty:
            pnl = compute_pnl(actual_df)
            meta = {
                "department": request.department or "all",
                "period":     f"{request.start_date or 'start'} → {request.end_date or 'now'}",
            }
            extra_context = generate_fact_doc(pnl, metadata=meta)
    except Exception:
        pass  # live context is best-effort; RAG still works without it

    result = ask_question(
        question=request.question,
        top_k=request.top_k,
        extra_context=extra_context,
    )

    return AskResponse(
        question=request.question,
        answer=result["answer"],
        sources=result["sources"],
        model_used=result["model"],
        configured=result["configured"],
    )


@router.post("/commentary", response_model=CommentaryResponse)
def get_commentary(
    request: CommentaryRequest,
    db: Session = Depends(get_db),
) -> CommentaryResponse:
    """
    Generate AI executive commentary for a given P&L snapshot.
    Calls generate_commentary() in rag_pipeline.py — no math here.
    """
    actual_df = _load_actuals(
        db, request.department, request.region,
        request.product, request.start_date, request.end_date,
    )
    if actual_df.empty:
        raise HTTPException(status_code=404, detail="No actuals data for the given filters")

    budget_df = _load_budgets(
        db, request.department, request.region,
        request.product, request.start_date, request.end_date,
    )

    pnl = compute_pnl(actual_df)
    variance_report = compute_variance_report(actual_df, budget_df) if not budget_df.empty else {}

    meta = {
        "department": request.department or "all departments",
        "period":     f"{request.start_date or 'start'} to {request.end_date or 'latest'}",
    }

    commentary = generate_commentary(pnl, variance_report, metadata=meta)
    configured = "not" not in commentary.lower()[:40]  # heuristic check

    return CommentaryResponse(commentary=commentary, configured=configured)


@router.post("/ingest", response_model=IngestResponse)
def ingest_fact_docs(
    request: IngestRequest,
    db: Session = Depends(get_db),
) -> IngestResponse:
    """
    Generate P&L and variance fact documents from the DB and upsert into Qdrant.
    Safe to call repeatedly — documents are deterministically ID'd (idempotent).
    """
    actual_df = _load_actuals(
        db, request.department, request.region,
        request.product, request.start_date, request.end_date,
    )
    if actual_df.empty:
        raise HTTPException(status_code=404, detail="No actuals data for the given filters")

    budget_df = _load_budgets(
        db, request.department, request.region,
        request.product, request.start_date, request.end_date,
    )

    meta = {
        "department": request.department or "all",
        "region":     request.region     or "all",
        "product":    request.product    or "all",
        "period":     f"{request.start_date or 'start'} to {request.end_date or 'latest'}",
    }

    docs_upserted = 0

    pnl      = compute_pnl(actual_df)
    pnl_doc  = generate_fact_doc(pnl, metadata=meta)
    if upsert_fact_doc(pnl_doc, metadata=meta):
        docs_upserted += 1

    if not budget_df.empty:
        variance_report = compute_variance_report(actual_df, budget_df)
        var_doc = generate_variance_fact_doc(variance_report, metadata=meta)
        if upsert_fact_doc(var_doc, metadata=meta):
            docs_upserted += 1

    if docs_upserted == 0:
        return IngestResponse(
            success=False,
            message="AI not configured. Set OPENAI_API_KEY and QDRANT_URL to enable ingestion.",
            docs_upserted=0,
        )

    return IngestResponse(
        success=True,
        message=f"Successfully upserted {docs_upserted} fact document(s) into Qdrant.",
        docs_upserted=docs_upserted,
    )
