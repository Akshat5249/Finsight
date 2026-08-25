"""
FinSight — Unit Tests: Reporting Service
Phase 6, Prompt 19. Tests for reporting.py.

All tests are pure (no DB, no API) — reporting functions take dicts and return bytes.

Covers:
  - generate_excel_report: returns bytes, valid xlsx magic bytes
  - generate_pdf_report: returns bytes, valid %PDF header
  - generate_pptx_report: returns bytes, valid PPTX magic bytes (ZIP)
  - All three: handle empty variance dict without crashing
  - All three: handle metadata injection without crashing
"""

from __future__ import annotations

import pytest

from app.services.reporting import (
    generate_excel_report,
    generate_pdf_report,
    generate_pptx_report,
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
        "revenue":      {"actual": 1000, "budget": 900, "variance": 100,  "variance_pct": 11.1,  "favorable": True,  "label": "Favorable"},
        "cogs":         {"actual": 400,  "budget": 380, "variance": 20,   "variance_pct": 5.3,   "favorable": False, "label": "Unfavorable"},
        "gross_profit": {"actual": 600,  "budget": 520, "variance": 80,   "variance_pct": 15.4,  "favorable": True,  "label": "Favorable"},
        "ebitda":       {"actual": 430,  "budget": 500, "variance": -70,  "variance_pct": -14.0, "favorable": False, "label": "Unfavorable"},
        "net_income":   {"actual": 285,  "budget": 300, "variance": -15,  "variance_pct": -5.0,  "favorable": False, "label": "Unfavorable"},
    }


@pytest.fixture
def meta() -> dict:
    return {"title": "Test Report", "department": "Engineering", "period": "2024-Q1"}


# ─────────────────────────────────────────────────────────────────────────────
# Excel
# ─────────────────────────────────────────────────────────────────────────────

class TestExcelReport:
    def test_returns_bytes(self, sample_pnl, sample_variance):
        result = generate_excel_report(sample_pnl, sample_variance)
        assert isinstance(result, bytes)

    def test_xlsx_magic_bytes(self, sample_pnl, sample_variance):
        """XLSX files are ZIP archives — start with PK magic bytes."""
        result = generate_excel_report(sample_pnl, sample_variance)
        assert result[:4] == b"PK\x03\x04", "Not a valid ZIP/XLSX file"

    def test_non_empty_output(self, sample_pnl, sample_variance):
        result = generate_excel_report(sample_pnl, sample_variance)
        assert len(result) > 1000  # any real workbook is >1KB

    def test_with_metadata(self, sample_pnl, sample_variance, meta):
        result = generate_excel_report(sample_pnl, sample_variance, metadata=meta)
        assert isinstance(result, bytes)

    def test_empty_variance_no_crash(self, sample_pnl):
        """Empty variance dict must not crash — just produces P&L sheet only."""
        result = generate_excel_report(sample_pnl, {})
        assert isinstance(result, bytes)


# ─────────────────────────────────────────────────────────────────────────────
# PDF
# ─────────────────────────────────────────────────────────────────────────────

class TestPdfReport:
    def test_returns_bytes(self, sample_pnl, sample_variance):
        result = generate_pdf_report(sample_pnl, sample_variance)
        assert isinstance(result, bytes)

    def test_pdf_header(self, sample_pnl, sample_variance):
        """Valid PDF files start with %PDF."""
        result = generate_pdf_report(sample_pnl, sample_variance)
        assert result[:4] == b"%PDF", "Not a valid PDF file"

    def test_non_empty_output(self, sample_pnl, sample_variance):
        result = generate_pdf_report(sample_pnl, sample_variance)
        assert len(result) > 1000

    def test_with_metadata(self, sample_pnl, sample_variance, meta):
        result = generate_pdf_report(sample_pnl, sample_variance, metadata=meta)
        assert isinstance(result, bytes)

    def test_empty_variance_no_crash(self, sample_pnl):
        result = generate_pdf_report(sample_pnl, {})
        assert isinstance(result, bytes)


# ─────────────────────────────────────────────────────────────────────────────
# PPTX
# ─────────────────────────────────────────────────────────────────────────────

class TestPptxReport:
    def test_returns_bytes(self, sample_pnl, sample_variance):
        result = generate_pptx_report(sample_pnl, sample_variance)
        assert isinstance(result, bytes)

    def test_pptx_magic_bytes(self, sample_pnl, sample_variance):
        """PPTX files are ZIP archives — start with PK magic bytes."""
        result = generate_pptx_report(sample_pnl, sample_variance)
        assert result[:4] == b"PK\x03\x04", "Not a valid ZIP/PPTX file"

    def test_non_empty_output(self, sample_pnl, sample_variance):
        result = generate_pptx_report(sample_pnl, sample_variance)
        assert len(result) > 5000  # any real PPTX is >5KB

    def test_with_metadata(self, sample_pnl, sample_variance, meta):
        result = generate_pptx_report(sample_pnl, sample_variance, metadata=meta)
        assert isinstance(result, bytes)

    def test_empty_variance_no_crash(self, sample_pnl):
        result = generate_pptx_report(sample_pnl, {})
        assert isinstance(result, bytes)
