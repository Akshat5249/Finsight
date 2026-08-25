"""
FinSight — Synthetic Dataset Generator
Phase 1, Prompt 3. Implements Section 7 of the Blueprint exactly.

Generates actuals.xlsx and budget.xlsx for NovaTech Solutions:
  - 30 months of data (configurable via MONTHS constant)
  - 6 departments × 4 regions × 4 products × multiple account categories
  - Injected Q2–Q4 business events per §7.3
  - Seeded data-quality issues per §7.4

Output files match the actuals/budgets schema in §6 exactly so the
ingestion module can load them with zero transformation guesswork.

Usage:
    python data/synthetic/generate_dataset.py
    python data/synthetic/generate_dataset.py --seed 99 --months 36

Column output (matches §6 actuals / §6 budgets schema):
    id, upload_id, date, department, region, product,
    account_category, account_type, amount, created_at
"""

import argparse
import random
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# ── Constants ────────────────────────────────────────────────────────────────

MONTHS: int = 30
DEFAULT_SEED: int = 42
START_DATE: date = date(2024, 1, 1)

DEPARTMENTS = ["Engineering", "Sales", "Marketing", "Operations", "HR", "Finance"]
REGIONS = ["India", "US", "Europe", "APAC"]
PRODUCTS = ["Cloud Platform", "Analytics", "AI Solutions", "Consulting"]

# account_type → literal values that match the §6 enum
ACCOUNT_TYPES = ["revenue", "cogs", "opex", "da", "interest", "tax"]

# Revenue account categories (tagged as account_type='revenue')
REVENUE_CATEGORIES = ["Product Revenue", "Service Revenue", "License Revenue"]

# COGS categories
COGS_CATEGORIES = ["Cost of Goods Sold"]

# Opex categories per §7 — Marketing sub-categories + general opex
MARKETING_OPEX = ["Advertising", "Events", "Social Media", "Agencies", "Software"]
GENERAL_OPEX = ["Salaries", "Infrastructure", "Cloud Hosting", "R&D", "Travel", "Facilities"]

# D&A, Interest, Tax
DA_CATEGORIES = ["Depreciation & Amortization"]
INTEREST_CATEGORIES = ["Interest Expense"]
TAX_CATEGORIES = ["Income Tax"]

# Base monthly revenue band per (department, product) — realistic INR thousands
# Engineering/AI Solutions skew high; Finance/Consulting skew lower
BASE_REVENUE_BANDS: dict[str, dict[str, tuple[float, float]]] = {
    "Engineering":  {"Cloud Platform": (500, 900), "Analytics": (400, 800), "AI Solutions": (600, 900), "Consulting": (150, 400)},
    "Sales":        {"Cloud Platform": (400, 800), "Analytics": (350, 700), "AI Solutions": (450, 850), "Consulting": (200, 500)},
    "Marketing":    {"Cloud Platform": (200, 500), "Analytics": (150, 450), "AI Solutions": (250, 550), "Consulting": (100, 300)},
    "Operations":   {"Cloud Platform": (300, 650), "Analytics": (250, 600), "AI Solutions": (300, 700), "Consulting": (150, 400)},
    "HR":           {"Cloud Platform": (150, 350), "Analytics": (150, 350), "AI Solutions": (200, 400), "Consulting": (100, 250)},
    "Finance":      {"Cloud Platform": (150, 350), "Analytics": (200, 400), "AI Solutions": (200, 400), "Consulting": (100, 250)},
}

# Region multipliers (India is base = 1.0)
REGION_MULTIPLIERS = {"India": 1.0, "US": 1.8, "Europe": 1.5, "APAC": 1.2}

# Monthly growth rate applied to the baseline (1.5% compounding)
MONTHLY_GROWTH_RATE: float = 0.015

# Noise band for actuals (±6%)
NOISE_BAND: float = 0.06

# COGS as % of revenue (randomised per row between these bounds)
COGS_PCT_RANGE = (0.35, 0.45)

# Opex as % of revenue per category (rough bands)
OPEX_PCT_BANDS: dict[str, tuple[float, float]] = {
    # Marketing opex
    "Advertising":   (0.04, 0.07),
    "Events":        (0.02, 0.04),
    "Social Media":  (0.01, 0.03),
    "Agencies":      (0.03, 0.06),
    "Software":      (0.01, 0.02),
    # General opex
    "Salaries":      (0.08, 0.14),
    "Infrastructure":(0.03, 0.06),
    "Cloud Hosting": (0.02, 0.04),
    "R&D":           (0.03, 0.07),
    "Travel":        (0.01, 0.03),
    "Facilities":    (0.01, 0.03),
}

DA_PCT: float = 0.03           # D&A ≈ 3% of revenue
INTEREST_FIXED: float = 25.0   # Fixed monthly interest (₹K) per dept/region/product
TAX_RATE: float = 0.25         # Applied to pre-tax income if positive


# ── Helper functions ─────────────────────────────────────────────────────────

def month_offset(start: date, n: int) -> date:
    """Return the first day of the month n months after start."""
    month = (start.month - 1 + n) % 12 + 1
    year = start.year + (start.month - 1 + n) // 12
    return date(year, month, 1)


def quarter_of(d: date) -> int:
    return (d.month - 1) // 3 + 1


def build_rows(
    rng: np.random.Generator,
    months: int,
    noise_band: float,
    budget_mode: bool,
) -> list[dict]:
    """
    Core generation loop. Returns a list of row dicts matching the §6 schema.

    budget_mode=True  → smooth plan without injected events / full noise
    budget_mode=False → actuals with injected events + random noise
    """
    rows: list[dict] = []
    now_utc = datetime.now(tz=timezone.utc)

    for m in range(months):
        period = month_offset(START_DATE, m)
        q = quarter_of(period)
        growth_factor = (1 + MONTHLY_GROWTH_RATE) ** m

        for dept in DEPARTMENTS:
            for region in REGIONS:
                for product in PRODUCTS:

                    # ── Base revenue for this cell ───────────────────────────
                    lo, hi = BASE_REVENUE_BANDS[dept][product]
                    base_rev = rng.uniform(lo, hi) * REGION_MULTIPLIERS[region]
                    base_rev *= growth_factor

                    # Budget has tiny noise (±1%); actuals get full noise
                    if budget_mode:
                        rev_noise = rng.uniform(-0.01, 0.01)
                    else:
                        rev_noise = rng.uniform(-noise_band, noise_band)

                    # ── Inject Q3 revenue event (actuals only, §7.3) ─────────
                    # Q3: AI Solutions in US/Europe up 10–15%
                    rev_event = 0.0
                    if (
                        not budget_mode
                        and q == 3
                        and product == "AI Solutions"
                        and region in ("US", "Europe")
                    ):
                        rev_event = rng.uniform(0.10, 0.15)

                    # ── Q4 revenue growth slowdown (actuals only, §7.3) ──────
                    # Q4: actual revenue grows at ~half the normal monthly rate
                    q4_slowdown = 0.0
                    if not budget_mode and q == 4:
                        q4_slowdown = -MONTHLY_GROWTH_RATE * 0.5

                    revenue = base_rev * (1 + rev_noise + rev_event + q4_slowdown)

                    # Emit revenue row (single category per cell for simplicity)
                    rows.append(dict(
                        date=period,
                        department=dept,
                        region=region,
                        product=product,
                        account_category="Product Revenue",
                        account_type="revenue",
                        amount=round(revenue, 2),
                        created_at=now_utc,
                    ))

                    # ── COGS ─────────────────────────────────────────────────
                    cogs_pct = rng.uniform(*COGS_PCT_RANGE)
                    # Q3 COGS pressure (actuals only, §7.3)
                    cogs_event = 0.0
                    if not budget_mode and q == 3:
                        cogs_event = rng.uniform(0.08, 0.14)
                    cogs = revenue * cogs_pct * (1 + cogs_event)
                    rows.append(dict(
                        date=period,
                        department=dept,
                        region=region,
                        product=product,
                        account_category="Cost of Goods Sold",
                        account_type="cogs",
                        amount=round(cogs, 2),
                        created_at=now_utc,
                    ))

                    # ── Opex ─────────────────────────────────────────────────
                    opex_categories = (
                        MARKETING_OPEX if dept == "Marketing" else GENERAL_OPEX
                    )
                    for cat in opex_categories:
                        lo_p, hi_p = OPEX_PCT_BANDS[cat]
                        opex_amount = revenue * rng.uniform(lo_p, hi_p)

                        # Q2 Marketing overspend (actuals only, §7.3)
                        mkt_event = 0.0
                        if (
                            not budget_mode
                            and q == 2
                            and dept == "Marketing"
                            and cat in ("Advertising", "Agencies")
                        ):
                            mkt_event = rng.uniform(0.35, 0.45)

                        # Q4 Salary increase — Engineering & Sales (actuals, §7.3)
                        salary_event = 0.0
                        if (
                            not budget_mode
                            and q == 4
                            and dept in ("Engineering", "Sales")
                            and cat == "Salaries"
                        ):
                            salary_event = rng.uniform(0.08, 0.10)

                        opex_amount *= (1 + mkt_event + salary_event)

                        if not budget_mode:
                            opex_amount *= (1 + rng.uniform(-noise_band, noise_band))

                        rows.append(dict(
                            date=period,
                            department=dept,
                            region=region,
                            product=product,
                            account_category=cat,
                            account_type="opex",
                            amount=round(opex_amount, 2),
                            created_at=now_utc,
                        ))

                    # ── D&A ──────────────────────────────────────────────────
                    da = revenue * DA_PCT
                    rows.append(dict(
                        date=period,
                        department=dept,
                        region=region,
                        product=product,
                        account_category="Depreciation & Amortization",
                        account_type="da",
                        amount=round(da, 2),
                        created_at=now_utc,
                    ))

                    # ── Interest ─────────────────────────────────────────────
                    rows.append(dict(
                        date=period,
                        department=dept,
                        region=region,
                        product=product,
                        account_category="Interest Expense",
                        account_type="interest",
                        amount=round(INTEREST_FIXED, 2),
                        created_at=now_utc,
                    ))

                    # ── Tax (25% of pre-tax income if positive) ───────────────
                    gross_profit = revenue - cogs
                    total_opex = sum(
                        revenue * rng.uniform(*OPEX_PCT_BANDS[cat])
                        for cat in opex_categories
                    )
                    ebit = gross_profit - total_opex
                    pre_tax = ebit - INTEREST_FIXED
                    tax = max(pre_tax * TAX_RATE, 0.0)
                    rows.append(dict(
                        date=period,
                        department=dept,
                        region=region,
                        product=product,
                        account_category="Income Tax",
                        account_type="tax",
                        amount=round(tax, 2),
                        created_at=now_utc,
                    ))

    return rows


def inject_data_quality_issues(
    df: pd.DataFrame, rng: np.random.Generator
) -> pd.DataFrame:
    """
    Seeds intentional data-quality issues per §7.4 so the ingestion validator
    has something real to catch:
      - Missing department on ~1–2% of rows
      - ~0.5% duplicate rows
      - A handful of malformed dates
    """
    n = len(df)

    # 1. Missing department (~1.5% of rows)
    missing_dept_idx = rng.choice(
        df.index, size=max(1, int(n * 0.015)), replace=False
    )
    df.loc[missing_dept_idx, "department"] = None

    # 2. Duplicate rows (~0.5%)
    dup_count = max(1, int(n * 0.005))
    dup_rows = df.sample(n=dup_count, random_state=int(rng.integers(0, 9999)))
    df = pd.concat([df, dup_rows], ignore_index=True)

    # 3. Malformed dates (5 rows)
    mal_idx = rng.choice(df.index, size=5, replace=False)
    df = df.copy()
    df["date"] = df["date"].astype(object)
    for i in mal_idx:
        df.at[i, "date"] = "not-a-date"

    return df


def generate(seed: int = DEFAULT_SEED, months: int = MONTHS) -> None:
    rng = np.random.default_rng(seed)
    # Also seed Python random (used nowhere else but kept consistent)
    random.seed(seed)

    out_dir = Path(__file__).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating {months} months of data for NovaTech Solutions (seed={seed})…")

    # ── Build clean actuals & budget ─────────────────────────────────────────
    actuals_rows = build_rows(rng, months, noise_band=NOISE_BAND, budget_mode=False)
    budget_rows  = build_rows(rng, months, noise_band=NOISE_BAND, budget_mode=True)

    actuals_df = pd.DataFrame(actuals_rows)
    budget_df  = pd.DataFrame(budget_rows)

    # Add a placeholder id column (ingestion service will ignore / overwrite)
    actuals_df.insert(0, "id", range(1, len(actuals_df) + 1))
    budget_df.insert(0,  "id", range(1, len(budget_df) + 1))

    # Add upload_id placeholder (0 = not yet ingested)
    actuals_df.insert(1, "upload_id", 0)
    budget_df.insert(1,  "upload_id", 0)

    # ── Inject data-quality issues into actuals only ──────────────────────────
    dirty_rng = np.random.default_rng(seed + 1)
    actuals_dirty = inject_data_quality_issues(actuals_df.copy(), dirty_rng)

    # ── Write output files ────────────────────────────────────────────────────
    actuals_path = out_dir / "actuals.xlsx"
    budget_path  = out_dir / "budget.xlsx"

    # Excel (openpyxl) does not support tz-aware datetimes — strip tzinfo for the file.
    # The DB ingestion layer stores UTC regardless.
    def strip_tz(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(df["created_at"]).dt.tz_localize(None)
        return df

    strip_tz(actuals_dirty).to_excel(actuals_path, index=False, engine="openpyxl")
    strip_tz(budget_df).to_excel(budget_path, index=False, engine="openpyxl")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"actuals.xlsx — {len(actuals_dirty):,} rows (incl. duplicates + quality issues)")
    print(f"budget.xlsx  — {len(budget_df):,} rows (clean)")

    print("\n── Actuals sample (10 rows) ──")
    print(actuals_dirty.sample(10, random_state=seed).to_string(index=False))

    print("\n── Budget sample (10 rows) ──")
    print(budget_df.sample(10, random_state=seed).to_string(index=False))

    # ── Verify injected events are present ───────────────────────────────────
    clean_actuals = pd.DataFrame(actuals_rows)
    clean_actuals["date"] = pd.to_datetime(clean_actuals["date"])
    clean_actuals["quarter"] = clean_actuals["date"].dt.quarter

    # Q2 marketing overspend
    q2_mkt = clean_actuals[
        (clean_actuals["quarter"] == 2)
        & (clean_actuals["department"] == "Marketing")
        & (clean_actuals["account_category"].isin(["Advertising", "Agencies"]))
    ]["amount"].mean()
    print(f"\n── Injected events verification ──")
    print(f"Q2 Marketing Advertising+Agencies avg amount : ₹{q2_mkt:,.0f}K")

    # Q3 AI Solutions revenue in US/Europe
    q3_ai_rev = clean_actuals[
        (clean_actuals["quarter"] == 3)
        & (clean_actuals["product"] == "AI Solutions")
        & (clean_actuals["region"].isin(["US", "Europe"]))
        & (clean_actuals["account_type"] == "revenue")
    ]["amount"].mean()
    print(f"Q3 AI Solutions US+Europe avg revenue        : ₹{q3_ai_rev:,.0f}K")

    # ── Verify data-quality seeds ─────────────────────────────────────────────
    missing_dept = actuals_dirty["department"].isna().sum()
    malformed_dates = pd.to_datetime(actuals_dirty["date"], errors="coerce").isna().sum()
    original_size = len(actuals_df)
    dup_count = len(actuals_dirty) - original_size

    print(f"\n── Data-quality seeds verification ──")
    print(f"Missing department values : {missing_dept}")
    print(f"Duplicate rows injected   : {dup_count}")
    print(f"Malformed date values     : {malformed_dates}")
    print(f"\nFiles written to: {out_dir.resolve()}")
    print("Done ✓")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate NovaTech Solutions synthetic dataset")
    parser.add_argument("--seed",   type=int, default=DEFAULT_SEED, help="Random seed (default: 42)")
    parser.add_argument("--months", type=int, default=MONTHS,       help="Number of months (default: 30)")
    args = parser.parse_args()
    generate(seed=args.seed, months=args.months)
