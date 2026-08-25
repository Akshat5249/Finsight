"""
FinSight — Unit Tests: RAG Pipeline
Phase 5, Prompt 15. Tests for rag_pipeline.py.

Strategy: All tests run without real API credentials.
  - Fact-doc generators tested purely on output format/content
  - Embed/Qdrant/LLM functions tested via mocking
  - Graceful degradation (not-configured path) tested without mocks

Covers:
  - generate_fact_doc: correct field rendering, metadata injection
  - generate_variance_fact_doc: correct format, all metrics present
  - _doc_id: deterministic, hex string
  - embed_text: returns None when OPENAI_API_KEY not set
  - search_fact_docs: returns [] when not configured
  - upsert_fact_doc: returns False when not configured
  - ask_question: returns configured=False + graceful message when not configured
  - generate_commentary: returns graceful message when not configured
  - ask_question: mocked path returns structured response
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from app.services.rag_pipeline import (
    _doc_id,
    ask_question,
    embed_text,
    generate_commentary,
    generate_fact_doc,
    generate_variance_fact_doc,
    search_fact_docs,
    upsert_fact_doc,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_pnl() -> dict:
    return {
        "revenue": 1000.0, "cogs": 400.0, "gross_profit": 600.0,
        "gross_margin_pct": 60.0, "opex": 200.0, "operating_income": 400.0,
        "da": 30.0, "ebitda": 430.0, "interest": 20.0,
        "pretax_income": 380.0, "tax": 95.0, "net_income": 285.0,
    }


@pytest.fixture
def sample_variance() -> dict:
    return {
        "revenue":     {"actual": 1000, "budget": 900, "variance": 100,  "variance_pct": 11.1,  "favorable": True,  "label": "Favorable"},
        "ebitda":      {"actual": 430,  "budget": 500, "variance": -70,  "variance_pct": -14.0, "favorable": False, "label": "Unfavorable"},
        "gross_profit":{"actual": 600,  "budget": 520, "variance": 80,   "variance_pct": 15.4,  "favorable": True,  "label": "Favorable"},
        "net_income":  {"actual": 285,  "budget": 300, "variance": -15,  "variance_pct": -5.0,  "favorable": False, "label": "Unfavorable"},
    }


# ─────────────────────────────────────────────────────────────────────────────
# generate_fact_doc
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateFactDoc:
    def test_contains_revenue(self, sample_pnl):
        doc = generate_fact_doc(sample_pnl)
        assert "1,000.00" in doc or "Revenue" in doc

    def test_contains_ebitda(self, sample_pnl):
        doc = generate_fact_doc(sample_pnl)
        assert "EBITDA" in doc
        assert "430" in doc

    def test_metadata_injected(self, sample_pnl):
        doc = generate_fact_doc(sample_pnl, metadata={"department": "Engineering", "period": "2024-Q2"})
        assert "Engineering" in doc
        assert "2024-Q2" in doc

    def test_default_metadata_placeholders(self, sample_pnl):
        """Without metadata, should use 'all departments' etc."""
        doc = generate_fact_doc(sample_pnl)
        assert "all departments" in doc

    def test_returns_string(self, sample_pnl):
        doc = generate_fact_doc(sample_pnl)
        assert isinstance(doc, str)
        assert len(doc) > 100


# ─────────────────────────────────────────────────────────────────────────────
# generate_variance_fact_doc
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateVarianceFactDoc:
    def test_contains_favorable_label(self, sample_variance):
        doc = generate_variance_fact_doc(sample_variance)
        assert "Favorable" in doc

    def test_contains_unfavorable_label(self, sample_variance):
        doc = generate_variance_fact_doc(sample_variance)
        assert "Unfavorable" in doc

    def test_contains_revenue_metric(self, sample_variance):
        doc = generate_variance_fact_doc(sample_variance)
        assert "Revenue" in doc

    def test_variance_fact_doc_is_string(self, sample_variance):
        doc = generate_variance_fact_doc(sample_variance)
        assert isinstance(doc, str)

    def test_metadata_period_in_doc(self, sample_variance):
        doc = generate_variance_fact_doc(sample_variance, metadata={"period": "2024-01", "department": "Sales"})
        assert "2024-01" in doc
        assert "Sales" in doc


# ─────────────────────────────────────────────────────────────────────────────
# _doc_id
# ─────────────────────────────────────────────────────────────────────────────

class TestDocId:
    def test_deterministic(self):
        assert _doc_id("hello") == _doc_id("hello")

    def test_different_inputs_different_ids(self):
        assert _doc_id("hello") != _doc_id("world")

    def test_length_32_chars(self):
        assert len(_doc_id("any text")) == 32

    def test_is_hex_string(self):
        doc_id = _doc_id("test")
        int(doc_id, 16)   # raises if not valid hex


# ─────────────────────────────────────────────────────────────────────────────
# Graceful degradation (no credentials)
# ─────────────────────────────────────────────────────────────────────────────

class TestGracefulDegradation:
    """All these must work cleanly with no OPENAI_API_KEY / QDRANT_URL set."""

    def test_embed_text_returns_none_without_key(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "")
        monkeypatch.setenv("OPENROUTER_API_KEY", "")
        result = embed_text("test query")
        assert result is None

    def test_search_returns_empty_without_qdrant(self, monkeypatch):
        monkeypatch.setenv("QDRANT_URL", "")
        result = search_fact_docs("what is revenue?")
        assert result == []

    def test_upsert_returns_false_without_qdrant(self, monkeypatch):
        monkeypatch.setenv("QDRANT_URL", "")
        result = upsert_fact_doc("some fact doc")
        assert result is False

    def test_ask_question_not_configured(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "")
        monkeypatch.setenv("OPENROUTER_API_KEY", "")
        result = ask_question("What is our revenue?")
        assert result["configured"] is False
        assert len(result["answer"]) > 10
        assert result["sources"] == []

    def test_generate_commentary_not_configured(self, monkeypatch, sample_pnl, sample_variance):
        monkeypatch.setenv("OPENAI_API_KEY", "")
        monkeypatch.setenv("OPENROUTER_API_KEY", "")
        msg = generate_commentary(sample_pnl, sample_variance)
        assert "not" in msg.lower() or "configure" in msg.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Mocked LLM path
# ─────────────────────────────────────────────────────────────────────────────

class TestMockedLLMPath:
    def test_ask_question_returns_structured_response(self, monkeypatch):
        """Mock OpenAI + Qdrant to test the happy path without real creds."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("QDRANT_URL", "http://localhost:6333")

        mock_openai = MagicMock()
        mock_openai.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=[0.1] * 1536)]
        )
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Revenue was ₹1,000K."))]
        )

        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = [
            MagicMock(payload={"text": "Revenue: ₹1,000K", "metadata": {}}, score=0.95)
        ]
        mock_qdrant.get_collections.return_value = MagicMock(collections=[])

        with patch("app.services.rag_pipeline._get_embed_client", return_value=mock_openai), \
             patch("app.services.rag_pipeline._get_qdrant_client", return_value=mock_qdrant):
            result = ask_question("What is our revenue?")

        assert result["configured"] is True
        assert "Revenue" in result["answer"]
        assert isinstance(result["sources"], list)
