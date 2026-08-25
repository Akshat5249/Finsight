"""
FinSight — Ingestion & Validation Service
Phase 1, Prompt 5. Implements §5, §6.1, §15 of the Blueprint.

Loads an actuals or budget Excel/CSV file, validates it against the §6 schema,
persists clean rows to the database, and returns a structured validation report
in the §15 format:
  {
    "rows_processed": int,
    "valid_records":  int,
    "warning_count":  int,
    "error_count":    int,
    "issues": [
      {"level": "error"|"warning", "type": str, "detail": str, "rows": [...]}
    ]
  }

Ground rule: no financial arithmetic here. This service only validates shape
and persists data. All financial calculations happen in financial_engine.py.
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.db.models import (
    Actual,
    Budget,
    Upload,
    UploadFileType,
    UploadStatus,
    AccountType,
)

logger = logging.getLogger(__name__)

# ── Valid values per §6 / §7 ─────────────────────────────────────────────────

VALID_DEPARTMENTS = {
    "Engineering", "Sales", "Marketing", "Operations", "HR", "Finance"
}
VALID_REGIONS = {"India", "US", "Europe", "APAC"}
VALID_PRODUCTS = {"Cloud Platform", "Analytics", "AI Solutions", "Consulting"}
VALID_ACCOUNT_TYPES = {at.value for at in AccountType}

# Required columns in every uploaded file (id and upload_id are optional in the
# upload file — they are assigned during ingestion)
REQUIRED_COLUMNS = {
    "date",
    "account_type",
    "amount",
}
# Columns that carry meaningful financial dimensions — missing is a warning not error
DIMENSION_COLUMNS = {"department", "region", "product", "account_category"}


# ─────────────────────────────────────────────────────────────────────────────
# Public interface
# ─────────────────────────────────────────────────────────────────────────────

def ingest_file(
    file_bytes: bytes,
    filename: str,
    file_type: UploadFileType,
    db: Session,
) -> tuple[Upload, dict[str, Any]]:
    """
    Main entry point.
    Validates and ingests an actuals or budget Excel/CSV file.

    Returns:
        (upload_record, validation_report)
    """
    logger.info("Starting ingestion: %s (%s)", filename, file_type.value)

    # 1. Parse the file
    df, parse_error = _parse_file(file_bytes, filename)
    if parse_error:
        upload = _create_upload_record(
            db, filename, file_type,
            status=UploadStatus.failed,
            report=_error_report(0, 0, 0, 1, [{"level": "error", "type": "parse_error", "detail": parse_error, "rows": []}]),
        )
        return upload, upload.validation_report  # type: ignore[return-value]

    rows_processed = len(df)
    issues: list[dict[str, Any]] = []

    # 2. Check required columns
    missing_cols = REQUIRED_COLUMNS - set(df.columns)
    if missing_cols:
        report = _error_report(
            rows_processed, 0, 0, 1,
            [{"level": "error", "type": "missing_required_columns",
              "detail": f"Missing columns: {sorted(missing_cols)}", "rows": []}]
        )
        upload = _create_upload_record(db, filename, file_type, UploadStatus.failed, report)
        return upload, report

    # 3. Duplicate-row detection (before any other cleaning)
    dup_mask = df.duplicated(keep="first")
    dup_count = int(dup_mask.sum())
    if dup_count:
        dup_idx = df[dup_mask].index.tolist()
        issues.append({
            "level": "error",
            "type": "duplicate_rows",
            "detail": f"{dup_count} duplicate row(s) detected and removed",
            "rows": dup_idx[:50],  # cap to 50 for report size
        })
    df_clean = df[~dup_mask].copy()

    # 4. Date parsing / malformed dates
    df_clean["date"] = pd.to_datetime(df_clean["date"], errors="coerce")
    bad_date_mask = df_clean["date"].isna()
    bad_date_count = int(bad_date_mask.sum())
    if bad_date_count:
        issues.append({
            "level": "error",
            "type": "invalid_dates",
            "detail": f"{bad_date_count} row(s) with malformed or missing date values — rows excluded",
            "rows": df_clean[bad_date_mask].index.tolist()[:50],
        })
    df_clean = df_clean[~bad_date_mask].copy()

    # 5. Non-numeric amount
    df_clean["amount"] = pd.to_numeric(df_clean["amount"], errors="coerce")
    bad_amount_mask = df_clean["amount"].isna()
    bad_amount_count = int(bad_amount_mask.sum())
    if bad_amount_count:
        issues.append({
            "level": "error",
            "type": "invalid_amount",
            "detail": f"{bad_amount_count} row(s) with non-numeric amount values — rows excluded",
            "rows": df_clean[bad_amount_mask].index.tolist()[:50],
        })
    df_clean = df_clean[~bad_amount_mask].copy()

    # 6. Missing department (warning — dimension gap)
    if "department" in df_clean.columns:
        missing_dept_mask = df_clean["department"].isna() | (df_clean["department"] == "")
        missing_dept_count = int(missing_dept_mask.sum())
        if missing_dept_count:
            issues.append({
                "level": "warning",
                "type": "missing_department",
                "detail": f"{missing_dept_count} row(s) with missing department value",
                "rows": df_clean[missing_dept_mask].index.tolist()[:50],
            })

    # 7. Missing region / product (warnings)
    for col in ("region", "product"):
        if col in df_clean.columns:
            missing_mask = df_clean[col].isna() | (df_clean[col] == "")
            cnt = int(missing_mask.sum())
            if cnt:
                issues.append({
                    "level": "warning",
                    "type": f"missing_{col}",
                    "detail": f"{cnt} row(s) with missing {col} value",
                    "rows": df_clean[missing_mask].index.tolist()[:50],
                })

    # 8. Invalid account_type values
    if "account_type" in df_clean.columns:
        bad_at_mask = ~df_clean["account_type"].isin(VALID_ACCOUNT_TYPES)
        bad_at_count = int(bad_at_mask.sum())
        if bad_at_count:
            bad_vals = df_clean.loc[bad_at_mask, "account_type"].unique().tolist()
            issues.append({
                "level": "error",
                "type": "invalid_account_type",
                "detail": f"{bad_at_count} row(s) with unknown account_type: {bad_vals}",
                "rows": df_clean[bad_at_mask].index.tolist()[:50],
            })
            df_clean = df_clean[~bad_at_mask].copy()

    # 9. Summary counts
    error_count   = sum(1 for i in issues if i["level"] == "error")
    warning_count = sum(1 for i in issues if i["level"] == "warning")
    valid_records = len(df_clean)

    # 10. Persist upload record (before inserting rows — we need the upload.id)
    report = {
        "rows_processed": rows_processed,
        "valid_records":  valid_records,
        "warning_count":  warning_count,
        "error_count":    error_count,
        "issues":         issues,
    }
    status = UploadStatus.success if error_count == 0 or valid_records > 0 else UploadStatus.failed
    upload = _create_upload_record(db, filename, file_type, status, report,
                                   rows_processed=rows_processed,
                                   valid_records=valid_records,
                                   warning_count=warning_count,
                                   error_count=error_count)

    # 11. Persist rows to actuals or budgets table
    _persist_rows(df_clean, file_type, upload.id, db)

    logger.info(
        "Ingestion complete: %s | rows=%d valid=%d warnings=%d errors=%d",
        filename, rows_processed, valid_records, warning_count, error_count,
    )
    return upload, report


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_file(
    file_bytes: bytes, filename: str
) -> tuple[pd.DataFrame | None, str | None]:
    """Parse bytes into a DataFrame; return (df, None) or (None, error_msg)."""
    fn_lower = filename.lower()
    try:
        if fn_lower.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes))
        elif fn_lower.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
        else:
            return None, f"Unsupported file format: {filename}. Use .xlsx or .csv"
        return df, None
    except Exception as exc:
        return None, f"Failed to parse file: {exc}"


def _create_upload_record(
    db: Session,
    filename: str,
    file_type: UploadFileType,
    status: UploadStatus,
    report: dict[str, Any],
    rows_processed: int = 0,
    valid_records: int = 0,
    warning_count: int = 0,
    error_count: int = 0,
) -> Upload:
    upload = Upload(
        filename=filename,
        file_type=file_type,
        status=status,
        rows_processed=rows_processed,
        valid_records=valid_records,
        warning_count=warning_count,
        error_count=error_count,
        validation_report=report,
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)
    return upload


def _persist_rows(
    df: pd.DataFrame,
    file_type: UploadFileType,
    upload_id: int,
    db: Session,
) -> None:
    """Bulk-insert validated rows into actuals or budgets table."""
    now_utc = datetime.now(tz=timezone.utc)
    Model = Actual if file_type == UploadFileType.actuals else Budget

    rows_to_insert = []
    for _, row in df.iterrows():
        obj = Model(
            upload_id=upload_id,
            date=row["date"].to_pydatetime() if hasattr(row["date"], "to_pydatetime") else row["date"],
            department=row.get("department") or None,
            region=row.get("region") or None,
            product=row.get("product") or None,
            account_category=row.get("account_category") or None,
            account_type=AccountType(row["account_type"]),
            amount=round(float(row["amount"]), 2),
            created_at=now_utc,
        )
        rows_to_insert.append(obj)

    # Bulk insert in batches of 5000 to avoid memory spikes
    batch_size = 5_000
    for i in range(0, len(rows_to_insert), batch_size):
        db.bulk_save_objects(rows_to_insert[i : i + batch_size])
        db.commit()

    logger.info("Persisted %d rows to %s", len(rows_to_insert), Model.__tablename__)


def _error_report(
    rows_processed: int,
    valid_records: int,
    warning_count: int,
    error_count: int,
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "rows_processed": rows_processed,
        "valid_records":  valid_records,
        "warning_count":  warning_count,
        "error_count":    error_count,
        "issues":         issues,
    }
