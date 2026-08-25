"""
FinSight — Upload Routes
Phase 1, Prompt 5.

Endpoints:
  POST /uploads/actuals          — ingest actuals Excel/CSV
  POST /uploads/budget           — ingest budget Excel/CSV
  GET  /uploads/{id}/validation-report — retrieve stored validation report
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Upload, UploadFileType
from app.schemas.uploads import UploadResponse, ValidationReport
from app.services.ingestion import ingest_file

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/actuals", response_model=UploadResponse, status_code=201)
async def upload_actuals(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> UploadResponse:
    """
    Ingest an actuals Excel/CSV file.
    Validates per §15 and persists clean rows to the actuals table.
    """
    contents = await file.read()
    upload, _ = ingest_file(
        file_bytes=contents,
        filename=file.filename or "actuals_upload",
        file_type=UploadFileType.actuals,
        db=db,
    )
    return UploadResponse.model_validate(upload)


@router.post("/budget", response_model=UploadResponse, status_code=201)
async def upload_budget(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> UploadResponse:
    """
    Ingest a budget Excel/CSV file.
    Validates per §15 and persists clean rows to the budgets table.
    """
    contents = await file.read()
    upload, _ = ingest_file(
        file_bytes=contents,
        filename=file.filename or "budget_upload",
        file_type=UploadFileType.budget,
        db=db,
    )
    return UploadResponse.model_validate(upload)


@router.get("/{upload_id}/validation-report", response_model=ValidationReport)
def get_validation_report(
    upload_id: int,
    db: Session = Depends(get_db),
) -> ValidationReport:
    """
    Retrieve the stored validation report for a previous upload.
    """
    upload = db.get(Upload, upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail=f"Upload {upload_id} not found")
    if upload.validation_report is None:
        raise HTTPException(status_code=404, detail="Validation report not available for this upload")
    return ValidationReport(**upload.validation_report)
