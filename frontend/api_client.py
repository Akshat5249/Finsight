"""
FinSight — Frontend API Client
Phase 1, Prompt 8. Thin wrapper around all backend REST calls.

Reads BACKEND_API_URL from environment (defaults to http://localhost:8000).
No financial calculations are performed here — all numbers come from the backend.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

BACKEND_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = 120.0  # seconds — increased for Render free-tier processing


def _get(path: str, params: dict | None = None) -> dict | list:
    """GET request to the backend. Raises on HTTP errors."""
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.get(f"{BACKEND_URL}{path}", params=params or {})
        r.raise_for_status()
        return r.json()


def _post_file(path: str, file_bytes: bytes, filename: str) -> dict:
    """POST a file (multipart) to the backend."""
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.post(
            f"{BACKEND_URL}{path}",
            files={"file": (filename, file_bytes, "application/octet-stream")},
        )
        r.raise_for_status()
        return r.json()


def _post_json(path: str, payload: dict) -> dict:
    """POST JSON to the backend."""
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.post(f"{BACKEND_URL}{path}", json=payload)
        r.raise_for_status()
        return r.json()


# ── Upload endpoints ──────────────────────────────────────────────────────────

def upload_actuals(file_bytes: bytes, filename: str) -> dict:
    return _post_file("/uploads/actuals", file_bytes, filename)


def upload_budget(file_bytes: bytes, filename: str) -> dict:
    return _post_file("/uploads/budget", file_bytes, filename)


def get_validation_report(upload_id: int) -> dict:
    return _get(f"/uploads/{upload_id}/validation-report")


# ── Financial endpoints ───────────────────────────────────────────────────────

def get_pnl(
    department: str | None = None,
    region: str | None = None,
    product: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    params: dict[str, Any] = {}
    if department: params["department"] = department
    if region:     params["region"]     = region
    if product:    params["product"]    = product
    if start_date: params["start_date"] = start_date
    if end_date:   params["end_date"]   = end_date
    return _get("/financials/pnl", params)


def get_variance(
    department: str | None = None,
    region: str | None = None,
    product: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    params: dict[str, Any] = {}
    if department: params["department"] = department
    if region:     params["region"]     = region
    if product:    params["product"]    = product
    if start_date: params["start_date"] = start_date
    if end_date:   params["end_date"]   = end_date
    return _get("/financials/variance", params)


def get_drilldown(
    dimension: str = "department",
    department: str | None = None,
    region: str | None = None,
    product: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    params: dict[str, Any] = {"dimension": dimension}
    if department: params["department"] = department
    if region:     params["region"]     = region
    if product:    params["product"]    = product
    if start_date: params["start_date"] = start_date
    if end_date:   params["end_date"]   = end_date
    return _get("/financials/drilldown", params)


def _download(path: str, params: dict | None = None) -> bytes:
    """GET request that returns raw bytes (for file downloads)."""
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.get(f"{BACKEND_URL}{path}", params=params or {})
        r.raise_for_status()
        return r.content


# ── Forecast endpoints (Phase 3) ──────────────────────────────────────────────

def create_forecast(payload: dict) -> dict:
    return _post_json("/forecasts", payload)


def get_forecast(run_id: int) -> dict:
    return _get(f"/forecasts/{run_id}")


# ── Scenario endpoints (Phase 4) ──────────────────────────────────────────────

def run_scenario(payload: dict) -> dict:
    return _post_json("/scenarios/run", payload)


def get_scenario(scenario_id: int) -> dict:
    return _get(f"/scenarios/{scenario_id}")


# ── AI endpoints (Phase 5) ────────────────────────────────────────────────────

def ask_ai(payload: dict) -> dict:
    return _post_json("/ai/ask", payload)


def get_commentary(payload: dict) -> dict:
    return _post_json("/ai/commentary", payload)


def ingest_facts(payload: dict) -> dict:
    return _post_json("/ai/ingest", payload)


# ── Report endpoints (Phase 6) ────────────────────────────────────────────────

def download_report(
    fmt: str,
    department: str | None = None,
    region: str | None = None,
    product: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> bytes:
    params: dict = {"format": fmt}
    if department: params["department"] = department
    if region:     params["region"]     = region
    if product:    params["product"]    = product
    if start_date: params["start_date"] = start_date
    if end_date:   params["end_date"]   = end_date
    return _download("/reports/download", params)


def get_ebitda_waterfall(
    department: str | None = None,
    region: str | None = None,
    product: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    params: dict = {}
    if department: params["department"] = department
    if region:     params["region"]     = region
    if product:    params["product"]    = product
    if start_date: params["start_date"] = start_date
    if end_date:   params["end_date"]   = end_date
    return _get("/financials/ebitda-waterfall", params)


def get_growth(
    metric: str = "revenue",
    department: str | None = None,
    region: str | None = None,
    product: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    params: dict = {"metric": metric}
    if department: params["department"] = department
    if region:     params["region"]     = region
    if product:    params["product"]    = product
    if start_date: params["start_date"] = start_date
    if end_date:   params["end_date"]   = end_date
    return _get("/analytics/growth", params)
