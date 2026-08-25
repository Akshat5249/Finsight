"""
FinSight — Upload Schemas
Pydantic models for upload request/response — §6.1, §15.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ValidationIssue(BaseModel):
    level:  str   # "error" | "warning"
    type:   str
    detail: str
    rows:   list[int] = []


class ValidationReport(BaseModel):
    rows_processed: int
    valid_records:  int
    warning_count:  int
    error_count:    int
    issues:         list[ValidationIssue] = []


class UploadResponse(BaseModel):
    id:                int
    filename:          str
    file_type:         str
    status:            str
    rows_processed:    int | None
    valid_records:     int | None
    warning_count:     int | None
    error_count:       int | None
    validation_report: ValidationReport | None
    created_at:        datetime

    model_config = {"from_attributes": True}
