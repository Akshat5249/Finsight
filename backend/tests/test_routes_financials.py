"""
FinSight — API Tests: Financial Routes
Phase 1, Prompt 7. FastAPI TestClient tests for /financials/* endpoints.

Covers:
  - GET /financials/pnl happy path (with data in DB)
  - GET /financials/variance happy path
  - GET /financials/drilldown happy path
  - GET /financials/pnl with invalid date range (no data → 404)
  - GET /financials/drilldown with invalid dimension → 422
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Actual, Budget, Upload, UploadFileType, UploadStatus, AccountType
from app.db.session import get_db
from app.main import app

# ── In-memory SQLite DB for testing ──────────────────────────────────────────
# Use a file-based SQLite so all fixtures share the same connection
SQLALCHEMY_TEST_URL = "sqlite:///./test_financials.db"

engine_test = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Create all tables and seed minimal test data once per session."""
    # SQLite doesn't support native enum types — use native_enum=False workaround
    # We do this by setting create_constraint to False for all enum columns
    Base.metadata.create_all(bind=engine_test)

    db = TestingSessionLocal()
    try:
        # Seed an actuals upload
        upload = Upload(
            filename="test_actuals.xlsx",
            file_type="actuals",
            status="success",
            rows_processed=6,
            valid_records=6,
            warning_count=0,
            error_count=0,
            validation_report={
                "rows_processed": 6, "valid_records": 6,
                "warning_count": 0, "error_count": 0, "issues": []
            },
        )
        db.add(upload)
        db.flush()

        budget_upload = Upload(
            filename="test_budget.xlsx",
            file_type="budget",
            status="success",
            rows_processed=6,
            valid_records=6,
            warning_count=0,
            error_count=0,
            validation_report={
                "rows_processed": 6, "valid_records": 6,
                "warning_count": 0, "error_count": 0, "issues": []
            },
        )
        db.add(budget_upload)
        db.flush()

        # Seed actuals rows (hand-computed P&L: rev=1000, cogs=400, opex=200, da=30, int=20, tax=95)
        actuals_data = [
            ("revenue",  "Product Revenue",             1000.0),
            ("cogs",     "Cost of Goods Sold",          400.0),
            ("opex",     "Salaries",                    200.0),
            ("da",       "Depreciation & Amortization", 30.0),
            ("interest", "Interest Expense",            20.0),
            ("tax",      "Income Tax",                  95.0),
        ]
        for acc_type, acc_cat, amount in actuals_data:
            db.add(Actual(
                upload_id=upload.id,
                date=date(2025, 1, 1),
                department="Engineering",
                region="India",
                product="Cloud Platform",
                account_category=acc_cat,
                account_type=acc_type,
                amount=amount,
            ))

        # Seed budget rows (slightly lower to create positive variance on revenue)
        budget_data = [
            ("revenue",  "Product Revenue",             900.0),
            ("cogs",     "Cost of Goods Sold",          380.0),
            ("opex",     "Salaries",                    210.0),
            ("da",       "Depreciation & Amortization", 30.0),
            ("interest", "Interest Expense",            20.0),
            ("tax",      "Income Tax",                  87.0),
        ]
        for acc_type, acc_cat, amount in budget_data:
            db.add(Budget(
                upload_id=budget_upload.id,
                date=date(2025, 1, 1),
                department="Engineering",
                region="India",
                product="Cloud Platform",
                account_category=acc_cat,
                account_type=acc_type,
                amount=amount,
            ))

        db.commit()
    finally:
        db.close()

    yield

    # Teardown
    Base.metadata.drop_all(bind=engine_test)
    import os
    if os.path.exists("./test_financials.db"):
        os.remove("./test_financials.db")


@pytest.fixture(scope="session")
def client(setup_db):
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ─────────────────────────────────────────────────────────────────────────────
# GET /financials/pnl
# ─────────────────────────────────────────────────────────────────────────────

class TestGetPnl:
    def test_happy_path(self, client):
        r = client.get("/financials/pnl")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["revenue"]      == pytest.approx(1000.0)
        assert body["cogs"]         == pytest.approx(400.0)
        assert body["gross_profit"] == pytest.approx(600.0)
        assert body["ebitda"]       == pytest.approx(430.0)  # EBIT=400 + DA=30

    def test_filter_by_department(self, client):
        r = client.get("/financials/pnl?department=Engineering")
        assert r.status_code == 200

    def test_no_data_returns_404(self, client):
        """No actuals for year 2099 → 404."""
        r = client.get("/financials/pnl?start_date=2099-01-01&end_date=2099-12-31")
        assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# GET /financials/variance
# ─────────────────────────────────────────────────────────────────────────────

class TestGetVariance:
    def test_happy_path(self, client):
        r = client.get("/financials/variance")
        assert r.status_code == 200, r.text
        body = r.json()
        rev = body["revenue"]
        # actual=1000, budget=900 → var=+100 → Favorable
        assert rev["actual"]    == pytest.approx(1000.0)
        assert rev["budget"]    == pytest.approx(900.0)
        assert rev["variance"]  == pytest.approx(100.0)
        assert rev["favorable"] is True
        assert rev["label"]     == "Favorable"

    def test_cogs_overspend_is_unfavorable(self, client):
        r = client.get("/financials/variance")
        assert r.status_code == 200
        cogs = r.json()["cogs"]
        # actual=400 vs budget=380 → +20 → Unfavorable
        assert cogs["variance"]  == pytest.approx(20.0)
        assert cogs["favorable"] is False


# ─────────────────────────────────────────────────────────────────────────────
# GET /financials/drilldown
# ─────────────────────────────────────────────────────────────────────────────

class TestGetDrilldown:
    def test_happy_path_department(self, client):
        r = client.get("/financials/drilldown?dimension=department")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "items" in body
        assert body["total_actual"] > 0

    def test_happy_path_region(self, client):
        r = client.get("/financials/drilldown?dimension=region")
        assert r.status_code == 200

    def test_invalid_dimension_returns_422(self, client):
        r = client.get("/financials/drilldown?dimension=invalid_xyz")
        assert r.status_code == 422
