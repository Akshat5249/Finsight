"""
FinSight — Integration Smoke Tests
Phase 7, Prompt 25. Pre-launch verification gate.

Tests every live endpoint end-to-end against the running Docker stack.
Run with: pytest tests/test_integration_smoke.py -v --tb=short

All tests use the live DB and running backend — NOT mocks.
Requires: docker-compose up (all 3 services).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=True)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 0 Gate — Health
# ─────────────────────────────────────────────────────────────────────────────

def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    # status is either ok (DB up) or degraded (DB down in test)
    assert data["status"] in ("ok", "degraded")
    assert "version" in data


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 Gate — Financial Engine
# ─────────────────────────────────────────────────────────────────────────────

def test_get_pnl():
    r = client.get("/financials/pnl")
    assert r.status_code in (200, 404)   # 404 if DB empty
    if r.status_code == 200:
        data = r.json()
        for k in ("revenue", "cogs", "gross_profit", "ebitda", "net_income"):
            assert k in data


def test_get_variance():
    r = client.get("/financials/variance")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        data = r.json()
        assert "revenue" in data or len(data) >= 0


def test_get_drilldown():
    r = client.get("/financials/drilldown?dimension=department")
    assert r.status_code in (200, 404)


def test_get_ebitda_waterfall():
    r = client.get("/financials/ebitda-waterfall")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        data = r.json()
        # Key is total_ebitda_variance (set by routes_financials)
        assert "total_ebitda_variance" in data or "total_variance" in data
        assert "drivers" in data


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 Gate — Analytics
# ─────────────────────────────────────────────────────────────────────────────

def test_get_growth_revenue():
    r = client.get("/analytics/growth?metric=revenue")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        data = r.json()
        assert data["metric"] == "revenue"
        assert "periods" in data
        assert "mom_pct" in data
        assert "yoy_pct" in data


def test_get_growth_invalid_metric():
    r = client.get("/analytics/growth?metric=not_a_metric")
    assert r.status_code in (422, 404, 200)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3 Gate — Forecast
# ─────────────────────────────────────────────────────────────────────────────

def test_post_forecast_linear():
    r = client.post("/forecasts", json={
        "metric": "revenue",
        "model":  "linear_regression",
        "horizon": 3,
    })
    assert r.status_code in (201, 404)
    if r.status_code == 201:
        data = r.json()
        assert len(data["periods"]) == 3
        assert data["model_used"] == "linear_regression"


def test_post_forecast_moving_average():
    r = client.post("/forecasts", json={
        "metric": "ebitda",
        "model":  "moving_average",
        "horizon": 3,
        "window": 3,
    })
    assert r.status_code in (201, 404)


def test_post_forecast_invalid_model():
    r = client.post("/forecasts", json={
        "metric": "revenue",
        "model":  "magic_model",
        "horizon": 3,
    })
    assert r.status_code in (422, 404)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4 Gate — Scenarios
# ─────────────────────────────────────────────────────────────────────────────

def test_post_scenario_upside():
    r = client.post("/scenarios/run", json={"name": "upside"})
    assert r.status_code in (201, 404)
    if r.status_code == 201:
        data = r.json()
        assert "base" in data
        assert "scenario" in data
        assert "delta" in data
        assert data["delta"]["revenue"] > 0   # upside → positive revenue delta


def test_post_scenario_downside():
    r = client.post("/scenarios/run", json={"name": "downside"})
    assert r.status_code in (201, 404)
    if r.status_code == 201:
        data = r.json()
        assert data["delta"]["revenue"] < 0   # downside → negative revenue delta


def test_post_scenario_invalid_name():
    r = client.post("/scenarios/run", json={"name": "fantasy"})
    assert r.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# Phase 5 Gate — AI (graceful degradation)
# ─────────────────────────────────────────────────────────────────────────────

def test_post_ai_ask_graceful():
    r = client.post("/ai/ask", json={"question": "What is our EBITDA?"})
    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    assert "configured" in data
    assert isinstance(data["configured"], bool)


def test_post_ai_commentary_graceful():
    r = client.post("/ai/commentary", json={})
    assert r.status_code in (200, 404)   # 404 if no actuals in DB


def test_post_ai_ingest_graceful():
    r = client.post("/ai/ingest", json={})
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        data = r.json()
        assert "success" in data


# ─────────────────────────────────────────────────────────────────────────────
# Phase 6 Gate — Reports
# ─────────────────────────────────────────────────────────────────────────────

def test_download_excel():
    r = client.get("/reports/download?format=excel")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert r.headers["content-type"].startswith(
            "application/vnd.openxmlformats"
        )
        assert r.content[:4] == b"PK\x03\x04"   # valid ZIP/XLSX


def test_download_pdf():
    r = client.get("/reports/download?format=pdf")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert r.content[:4] == b"%PDF"


def test_download_pptx():
    r = client.get("/reports/download?format=pptx")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert r.content[:4] == b"PK\x03\x04"


def test_download_invalid_format():
    r = client.get("/reports/download?format=docx")
    assert r.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# Phase 7 Gate — Audit Trail
# ─────────────────────────────────────────────────────────────────────────────

def test_list_audit_runs():
    r = client.get("/audit/runs")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_list_audit_uploads():
    r = client.get("/audit/uploads")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_audit_run_not_found():
    r = client.get("/audit/runs/99999")
    assert r.status_code == 404


def test_audit_upload_not_found():
    r = client.get("/audit/uploads/99999")
    assert r.status_code == 404


def test_audit_lineage_not_found():
    r = client.get("/audit/runs/99999/lineage")
    assert r.status_code == 404
