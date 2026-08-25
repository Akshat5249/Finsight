"""
FinSight — FastAPI Backend Entrypoint
Registers all API routers and exposes a /health liveness probe.
Route implementations are added per-phase as noted in comments below.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging import configure_logging  # Phase 7 (Prompt 22) implements full structured logging

# Phase 1 (Prompt 5)  → routes_uploads
from app.api.routes_uploads import router as uploads_router
# Phase 1 (Prompt 7)  → routes_financials
from app.api.routes_financials import router as financials_router
# Phase 2 (Prompt 10) → routes_analytics
from app.api.routes_analytics import router as analytics_router
# Phase 3 (Prompt 12) → routes_forecast
from app.api.routes_forecast import router as forecast_router
# Phase 4 (Prompt 13) → routes_scenarios
from app.api.routes_scenarios import router as scenarios_router
# Phase 5 (Prompt 16) → routes_ai
from app.api.routes_ai import router as ai_router
# Phase 6 (Prompt 19) → routes_reports
from app.api.routes_reports import router as reports_router
# Phase 7 (Prompt 21) → routes_audit
from app.api.routes_audit import router as audit_router

configure_logging()

app = FastAPI(
    title="FinSight API",
    description="AI-Powered FP&A Platform — FastAPI backend",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",   # Streamlit dev
        "http://frontend:8501",    # Docker internal
        "http://localhost:3000",   # future Next.js
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ── Register routers ─────────────────────────────────────────────────────────
app.include_router(uploads_router)
app.include_router(financials_router)
app.include_router(analytics_router)
app.include_router(forecast_router)
app.include_router(scenarios_router)
app.include_router(ai_router)
app.include_router(reports_router)
app.include_router(audit_router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Enhanced liveness + readiness probe (Phase 7, Prompt 22)."""
    import os
    from datetime import datetime, timezone
    from sqlalchemy import text
    from app.db.session import get_db_direct

    db_status = "ok"
    try:
        db = next(get_db_direct())
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {e}"

    return {
        "status":   "ok" if db_status == "ok" else "degraded",
        "version":  "1.0.0",
        "db":       db_status,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "env":      os.getenv("APP_ENV", "development"),
    }
