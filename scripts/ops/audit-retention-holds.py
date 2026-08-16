from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
import sys
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarise active legal holds and disposal readiness.")
    parser.add_argument("--db-path", default="data/escalator.db")
    parser.add_argument("--as-of-date", default=date.today().isoformat())
    args = parser.parse_args()

    store = SQLiteStore(args.db_path)
    with sqlite3.connect(args.db_path) as conn:
        rows = conn.execute(
            "SELECT invoice_id FROM invoices ORDER BY invoice_id ASC"
        ).fetchall()

    active_holds: list[dict[str, object]] = []
    upcoming_purges: list[dict[str, object]] = []
    expired_cases: list[dict[str, object]] = []
    as_of = date.fromisoformat(args.as_of_date)

    for (invoice_id,) in rows:
        compliance_entries = store.compliance_entries_for_invoice(invoice_id)
        latest_open_hold = None
        for entry in reversed(compliance_entries):
            if entry.event_type == "DATA_RETENTION_LEGAL_HOLD_OPENED":
                latest_open_hold = entry.details
                break
        if latest_open_hold:
            status = str(latest_open_hold.get("status") or "ACTIVE").upper()
            if status in {"ACTIVE", "LEGAL_HOLD_ACTIVE"}:
                active_holds.append({"invoice_id": invoice_id, "details": latest_open_hold})

        events = store.events_for_invoice(invoice_id)
        if events:
            last_activity = events[-1].timestamp.date()
            age_days = max(0, (as_of - last_activity).days)
            if age_days >= 2190:
                upcoming_purges.append({"invoice_id": invoice_id, "age_days": age_days, "last_activity": last_activity.isoformat()})

        if not latest_open_hold and events:
            last_activity = events[-1].timestamp.date()
            if (as_of - last_activity).days >= 2190:
                expired_cases.append({"invoice_id": invoice_id, "last_activity": last_activity.isoformat()})

    report = {
        "as_of_date": as_of.isoformat(),
        "active_holds": active_holds,
        "upcoming_purges": upcoming_purges,
        "expired_cases_ready_for_soft_delete": expired_cases,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
