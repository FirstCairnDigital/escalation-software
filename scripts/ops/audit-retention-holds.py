from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from unpaid_invoice_escalator.ops_cli import run_admin_cli


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarise active legal holds and disposal readiness.")
    parser.add_argument("--db-path", default="data/escalator.db")
    parser.add_argument("--artifacts-dir", default="data/artifacts")
    parser.add_argument("--bundles-dir", default="data/bundles")
    parser.add_argument("--as-of-date")
    parser.add_argument("--upcoming-within-days", type=int, default=45)
    args = parser.parse_args()

    forwarded = [
        "retention-queue",
        "--db-path",
        args.db_path,
        "--artifacts-dir",
        args.artifacts_dir,
        "--bundles-dir",
        args.bundles_dir,
        "--upcoming-within-days",
        str(args.upcoming_within_days),
    ]
    if args.as_of_date:
        forwarded.extend(["--as-of-date", args.as_of_date])
    return run_admin_cli(forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
