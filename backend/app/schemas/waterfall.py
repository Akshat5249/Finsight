"""
FinSight — EBITDA Waterfall Schema
Phase 2, Prompt 9. Typed Pydantic response for the /financials/ebitda-waterfall endpoint.
"""

from pydantic import BaseModel


class EbitdaWaterfallResponse(BaseModel):
    drivers:              dict[str, float]  # Revenue/COGS/Marketing/Infrastructure/Other/Total
    total_ebitda_variance: float
    favorable:            bool
