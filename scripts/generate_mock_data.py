#!/usr/bin/env python3
"""Dumps the deterministic MOCK Meta Ads dataset to data/mock/*.json for
human inspection. Not used by the running application at import time (the
app generates this data in-memory via `app.integrations.meta.mock_data`) —
this script exists purely so the mock data is visible/reviewable as files,
per project requirements.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.integrations.meta.mock_data import generate_full_mock_account  # noqa: E402

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "mock"
REFERENCE_DATE = date(2026, 9, 15)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    account = generate_full_mock_account(reference_date=REFERENCE_DATE)

    files = {
        "business_objective.json": account.business_objective.model_dump(mode="json"),
        "campaigns.json": [c.model_dump(mode="json") for c in account.campaigns],
        "ad_sets.json": [a.model_dump(mode="json") for a in account.ad_sets],
        "ads.json": [a.model_dump(mode="json") for a in account.ads],
        "creatives.json": [c.model_dump(mode="json") for c in account.creatives],
        "daily_insights.json": [i.model_dump(mode="json") for i in account.insights],
        "leads.json": [lead.model_dump(mode="json") for lead in account.leads],
        "sales.json": [s.model_dump(mode="json") for s in account.sales],
    }
    for filename, payload in files.items():
        path = OUTPUT_DIR / filename
        path.write_text(json.dumps(payload, indent=2, default=str))
        print(f"Wrote {path} ({len(payload) if isinstance(payload, list) else 1} record(s))")

    print(
        f"\nMOCK DATA — {len(account.campaigns)} campaign(s), {len(account.insights)} daily insight row(s), "
        f"{len(account.leads)} lead(s), {len(account.sales)} sale(s). Reference date: {REFERENCE_DATE}."
    )


if __name__ == "__main__":
    main()
