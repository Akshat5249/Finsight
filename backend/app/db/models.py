"""
FinSight — SQLAlchemy Models
Phase 1, Prompt 4. Implements all 8 tables per Section 6 of the Blueprint.

Column naming, types, constraints, and enumerations match §6 exactly.
  - NUMERIC(18,2)   for all monetary amount columns
  - UTC timestamps  via server_default=func.now() / DateTime(timezone=True)
  - Integer PK (SERIAL / autoincrement) on every table

Tables:
  6.1 uploads         — audit of every file ingested
  6.2 actuals         — actual financial data rows
  6.3 budgets         — budget / plan data rows
  6.4 forecasts       — forecast outputs
  6.5 scenarios       — scenario definitions and assumptions
  6.6 analysis_runs   — a run linking uploads → engine outputs
  6.7 reports         — generated file paths
  6.8 users           — (Phase 7) JWT auth
"""

import enum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# ─────────────────────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────────────────────

class AccountType(str, enum.Enum):
    revenue  = "revenue"
    cogs     = "cogs"
    opex     = "opex"
    da       = "da"
    interest = "interest"
    tax      = "tax"


class UploadFileType(str, enum.Enum):
    actuals = "actuals"
    budget  = "budget"


class UploadStatus(str, enum.Enum):
    pending   = "pending"
    success   = "success"
    failed    = "failed"


class ForecastModel(str, enum.Enum):
    moving_average        = "moving_average"
    linear_regression     = "linear_regression"
    exponential_smoothing = "exponential_smoothing"
    prophet               = "prophet"


class RunStatus(str, enum.Enum):
    pending   = "pending"
    running   = "running"
    complete  = "complete"
    failed    = "failed"


class ReportFormat(str, enum.Enum):
    excel      = "excel"
    pdf        = "pdf"
    powerpoint = "powerpoint"


# ─────────────────────────────────────────────────────────────────────────────
# §6.1  uploads
# ─────────────────────────────────────────────────────────────────────────────

class Upload(Base):
    """Audit record for every file ingested into the system."""
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[UploadFileType] = mapped_column(
        Enum(UploadFileType, name="upload_file_type"), nullable=False
    )
    status: Mapped[UploadStatus] = mapped_column(
        Enum(UploadStatus, name="upload_status"),
        nullable=False,
        default=UploadStatus.pending,
    )
    rows_processed: Mapped[int | None]     = mapped_column(Integer)
    valid_records:  Mapped[int | None]     = mapped_column(Integer)
    warning_count:  Mapped[int | None]     = mapped_column(Integer)
    error_count:    Mapped[int | None]     = mapped_column(Integer)
    validation_report: Mapped[dict | None] = mapped_column(JSON)   # itemized issues
    uploaded_by: Mapped[int | None]        = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    actuals: Mapped[list["Actual"]] = relationship(back_populates="upload")
    budgets: Mapped[list["Budget"]] = relationship(back_populates="upload")


# ─────────────────────────────────────────────────────────────────────────────
# §6.2  actuals
# ─────────────────────────────────────────────────────────────────────────────

class Actual(Base):
    """One row of actual financial data after ingestion and validation."""
    __tablename__ = "actuals"

    id: Mapped[int]            = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[int]     = mapped_column(Integer, ForeignKey("uploads.id"), nullable=False, index=True)
    date: Mapped[DateTime]     = mapped_column(DateTime(timezone=False), nullable=False, index=True)
    department: Mapped[str | None]       = mapped_column(String(128))
    region: Mapped[str | None]           = mapped_column(String(128))
    product: Mapped[str | None]          = mapped_column(String(128))
    account_category: Mapped[str | None] = mapped_column(String(256))
    account_type: Mapped[AccountType]    = mapped_column(
        Enum(AccountType, name="account_type"), nullable=False
    )
    amount: Mapped[Numeric]  = mapped_column(Numeric(18, 2), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    upload: Mapped["Upload"] = relationship(back_populates="actuals")


# ─────────────────────────────────────────────────────────────────────────────
# §6.3  budgets
# ─────────────────────────────────────────────────────────────────────────────

class Budget(Base):
    """One row of budget / plan data after ingestion and validation."""
    __tablename__ = "budgets"

    id: Mapped[int]            = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[int]     = mapped_column(Integer, ForeignKey("uploads.id"), nullable=False, index=True)
    date: Mapped[DateTime]     = mapped_column(DateTime(timezone=False), nullable=False, index=True)
    department: Mapped[str | None]       = mapped_column(String(128))
    region: Mapped[str | None]           = mapped_column(String(128))
    product: Mapped[str | None]          = mapped_column(String(128))
    account_category: Mapped[str | None] = mapped_column(String(256))
    account_type: Mapped[AccountType]    = mapped_column(
        Enum(AccountType, name="account_type"), nullable=False
    )
    amount: Mapped[Numeric]  = mapped_column(Numeric(18, 2), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    upload: Mapped["Upload"] = relationship(back_populates="budgets")


# ─────────────────────────────────────────────────────────────────────────────
# §6.5  scenarios  (defined before forecasts — forecasts FK to scenarios)
# ─────────────────────────────────────────────────────────────────────────────

class Scenario(Base):
    """Named set of assumption multipliers for what-if scenario planning (§11)."""
    __tablename__ = "scenarios"

    id: Mapped[int]          = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str]        = mapped_column(String(256), nullable=False)          # "base" | "upside" | "downside" | custom
    description: Mapped[str | None] = mapped_column(Text)
    revenue_growth_pct:   Mapped[float | None] = mapped_column(Numeric(10, 4))
    cogs_growth_pct:      Mapped[float | None] = mapped_column(Numeric(10, 4))
    marketing_growth_pct: Mapped[float | None] = mapped_column(Numeric(10, 4))
    extra_assumptions: Mapped[dict | None]     = mapped_column(JSON)               # extensible bag
    created_by: Mapped[int | None]             = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    forecasts:     Mapped[list["Forecast"]]    = relationship(back_populates="scenario")
    analysis_runs: Mapped[list["AnalysisRun"]] = relationship(back_populates="scenario")


# ─────────────────────────────────────────────────────────────────────────────
# §6.4  forecasts
# ─────────────────────────────────────────────────────────────────────────────

class Forecast(Base):
    """One forecasted metric value for a given period, model, and scenario."""
    __tablename__ = "forecasts"

    id: Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_run_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("analysis_runs.id"), nullable=True, index=True)
    scenario_id: Mapped[int | None]     = mapped_column(Integer, ForeignKey("scenarios.id"), nullable=True, index=True)
    metric: Mapped[str]       = mapped_column(String(128), nullable=False)         # "revenue" | "ebitda" | …
    period: Mapped[DateTime]  = mapped_column(DateTime(timezone=False), nullable=False, index=True)
    forecast_value: Mapped[Numeric]  = mapped_column(Numeric(18, 2), nullable=False)
    model_used: Mapped[ForecastModel] = mapped_column(
        Enum(ForecastModel, name="forecast_model"), nullable=False
    )
    # Accuracy metrics — populated when the forecasted period becomes actual
    actual_value: Mapped[Numeric | None]  = mapped_column(Numeric(18, 2))
    mae:  Mapped[Numeric | None]          = mapped_column(Numeric(18, 4))
    mape: Mapped[Numeric | None]          = mapped_column(Numeric(10, 4))
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    scenario:     Mapped["Scenario | None"]    = relationship(back_populates="forecasts")
    analysis_run: Mapped["AnalysisRun | None"] = relationship(back_populates="forecasts")


# ─────────────────────────────────────────────────────────────────────────────
# §6.6  analysis_runs
# ─────────────────────────────────────────────────────────────────────────────

class AnalysisRun(Base):
    """
    Links source uploads → engine outputs → AI commentary → reports.
    Every number shown in the UI can be traced back to its analysis_run_id,
    and from there to the exact upload(s) and code path that produced it.
    """
    __tablename__ = "analysis_runs"

    id: Mapped[int]                 = mapped_column(Integer, primary_key=True, autoincrement=True)
    actuals_upload_id: Mapped[int | None]  = mapped_column(Integer, ForeignKey("uploads.id"), nullable=True)
    budget_upload_id:  Mapped[int | None]  = mapped_column(Integer, ForeignKey("uploads.id"), nullable=True)
    scenario_id: Mapped[int | None]        = mapped_column(Integer, ForeignKey("scenarios.id"), nullable=True)
    status: Mapped[RunStatus]              = mapped_column(
        Enum(RunStatus, name="run_status"),
        nullable=False,
        default=RunStatus.pending,
    )
    # Serialised computed metrics (stored once, read by all downstream consumers)
    metrics_json:     Mapped[dict | None]  = mapped_column(JSON)
    commentary_json:  Mapped[dict | None]  = mapped_column(JSON)   # AI commentary (§13.2)
    created_by: Mapped[int | None]         = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[DateTime]           = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[DateTime | None]  = mapped_column(DateTime(timezone=True))

    forecasts: Mapped[list["Forecast"]] = relationship(back_populates="analysis_run")
    reports:   Mapped[list["Report"]]   = relationship(back_populates="analysis_run")
    scenario:  Mapped["Scenario | None"]  = relationship(back_populates="analysis_runs")


# ─────────────────────────────────────────────────────────────────────────────
# §6.7  reports
# ─────────────────────────────────────────────────────────────────────────────

class Report(Base):
    """Generated report file (Excel / PDF / PPTX) linked to an analysis run."""
    __tablename__ = "reports"

    id: Mapped[int]              = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("analysis_runs.id"), nullable=False, index=True)
    format: Mapped[ReportFormat] = mapped_column(
        Enum(ReportFormat, name="report_format"), nullable=False
    )
    file_path: Mapped[str]       = mapped_column(String(1024), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    analysis_run: Mapped["AnalysisRun"] = relationship(back_populates="reports")


# ─────────────────────────────────────────────────────────────────────────────
# §6.8  users  (Phase 7 — JWT auth, passlib + python-jose)
# ─────────────────────────────────────────────────────────────────────────────

class User(Base):
    """Application user for JWT-based auth (Phase 7, Prompt 21)."""
    __tablename__ = "users"

    id: Mapped[int]             = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str]          = mapped_column(String(512), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str]= mapped_column(String(1024), nullable=False)
    is_active: Mapped[bool]     = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool]  = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[DateTime]= mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
