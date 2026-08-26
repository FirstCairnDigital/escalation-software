from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from unpaid_invoice_escalator.api import create_app


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarise retention queue state using the live API workflow.")
    parser.add_argument("--db-path", default="data/escalator.db")
    parser.add_argument("--artifacts-dir", default="data/artifacts")
    parser.add_argument("--bundles-dir", default="data/bundles")
    parser.add_argument("--as-of-date")
    parser.add_argument("--upcoming-within-days", type=int, default=45)
    args = parser.parse_args()

    app = create_app(
        db_path=args.db_path,
        artifacts_dir=args.artifacts_dir,
        bundles_dir=args.bundles_dir,
    )
    params: dict[str, object] = {"upcoming_within_days": args.upcoming_within_days}
    if args.as_of_date:
        params["as_of_date"] = args.as_of_date

    with TestClient(app) as client:
        response = client.get("/data-retention-queue", params=params)
    response.raise_for_status()
    payload = response.json()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
