"""Write scanner results to the canonical output locations.

  output/scanner_latest.csv                    — always overwritten, last scan wins
  output/scanner_cache.json                    — dashboard reads this
  output/scanner_archive/scanner_<date>_close.csv — only when close_of_day=True

The dashboard's contract is the JSON cache: it MUST contain a `generated_at`
ISO timestamp and a `results` list of row dicts. CSV is for ad-hoc Excel use.
"""
from __future__ import annotations

import json
import math
import os
from datetime import date, datetime, timezone

import pandas as pd

LATEST_CSV = "scanner_latest.csv"
CACHE_JSON = "scanner_cache.json"
ARCHIVE_DIR = "scanner_archive"


def _to_json_safe(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (bool,)):
        return value
    if hasattr(value, "item"):  # numpy scalars
        return value.item()
    return value


def write_scan_results(
    results: pd.DataFrame,
    output_dir: str,
    close_of_day: bool = False,
) -> None:
    os.makedirs(output_dir, exist_ok=True)

    # CSV — always overwritten
    csv_path = os.path.join(output_dir, LATEST_CSV)
    results.to_csv(csv_path, index=False)

    # JSON cache — schema: {generated_at, results: [...]}
    rows = [
        {k: _to_json_safe(v) for k, v in row.items()}
        for row in results.to_dict(orient="records")
    ]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "results": rows,
    }
    cache_path = os.path.join(output_dir, CACHE_JSON)
    with open(cache_path, "w") as f:
        json.dump(payload, f, indent=2, default=_to_json_safe)

    # Dated archive (close-of-day runs only)
    if close_of_day:
        archive_path = os.path.join(output_dir, ARCHIVE_DIR)
        os.makedirs(archive_path, exist_ok=True)
        dated_name = f"scanner_{date.today().isoformat()}_close.csv"
        results.to_csv(os.path.join(archive_path, dated_name), index=False)
