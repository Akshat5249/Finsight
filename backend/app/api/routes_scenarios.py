"""
FinSight — Scenario Routes
Phase 4, Prompt 13.

POST /scenarios/run:
  1. Load actuals from DB
  2. Apply scenario multipliers via scenario_engine.apply_scenario()
  3. Compare base vs scenario via scenario_engine.compare_scenarios()
  4. Persist to scenarios table
  5. Return ScenarioResponse

GET /scenarios/{id}: Retrieve a persisted scenario.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes_financials import _load_actuals
from app.db.models import Scenario
from app.db.session import get_db
from app.schemas.scenarios import ScenarioRequest, ScenarioResponse
from app.services.scenario_engine import (
    SCENARIO_DEFAULTS,
    apply_scenario,
    compare_scenarios,
)

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

VALID_TYPES = {"base", "upside", "downside", "custom"}


@router.post("/run", response_model=ScenarioResponse, status_code=201)
def run_scenario(
    request: ScenarioRequest,
    db: Session = Depends(get_db),
) -> ScenarioResponse:
    """
    Apply scenario assumptions to actuals and return a full P&L comparison.
    If scenario_name is a preset (base/upside/downside), default multipliers
    are used unless the caller explicitly overrides them.
    """
    if request.name not in VALID_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid scenario name '{request.name}'. Choose from: {sorted(VALID_TYPES)}"
        )

    # Load actuals
    actual_df = _load_actuals(
        db,
        request.department, request.region, request.product,
        request.start_date, request.end_date,
    )
    if actual_df.empty:
        raise HTTPException(status_code=404, detail="No actuals data for the given filters")

    # Resolve assumptions — preset defaults + any caller overrides
    defaults = SCENARIO_DEFAULTS.get(request.name, {})
    rev_pct  = request.revenue_growth_pct   or defaults.get("revenue_growth_pct",   0.0)
    cogs_pct = request.cogs_growth_pct      or defaults.get("cogs_growth_pct",      0.0)
    mkt_pct  = request.marketing_growth_pct or defaults.get("marketing_growth_pct", 0.0)

    # Apply scenario
    scenario_df = apply_scenario(actual_df, rev_pct, cogs_pct, mkt_pct)

    # Compare
    comparison = compare_scenarios(actual_df, scenario_df)

    assumptions = {
        "revenue_growth_pct":   rev_pct,
        "cogs_growth_pct":      cogs_pct,
        "marketing_growth_pct": mkt_pct,
    }

    # Persist to scenarios table (maps to actual §6 Scenario schema)
    row = Scenario(
        name=request.name,
        description=f"Scenario run: rev={rev_pct:+.1f}%, cogs={cogs_pct:+.1f}%, mkt={mkt_pct:+.1f}%",
        revenue_growth_pct=rev_pct,
        cogs_growth_pct=cogs_pct,
        marketing_growth_pct=mkt_pct,
        extra_assumptions={
            "assumptions": assumptions,
            "results":     comparison,
        },
        created_at=datetime.now(tz=timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return ScenarioResponse(
        scenario_name=request.name,
        assumptions=assumptions,
        **comparison,
    )


@router.get("/{scenario_id}", response_model=ScenarioResponse)
def get_scenario(
    scenario_id: int,
    db: Session = Depends(get_db),
) -> ScenarioResponse:
    """Retrieve a persisted scenario by its DB id."""
    row = db.execute(
        select(Scenario).where(Scenario.id == scenario_id)
    ).scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Scenario id={scenario_id} not found")

    extra = row.extra_assumptions or {}
    results    = extra.get("results", {}) if isinstance(extra, dict) else {}
    assumptions = extra.get("assumptions", {
        "revenue_growth_pct":   float(row.revenue_growth_pct or 0),
        "cogs_growth_pct":      float(row.cogs_growth_pct or 0),
        "marketing_growth_pct": float(row.marketing_growth_pct or 0),
    })

    return ScenarioResponse(
        scenario_name=row.name,
        assumptions=assumptions,
        **results,
    )
