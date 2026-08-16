from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore


def _list_invoice_ids(db_path: str, invoice_id: str | None) -> list[str]:
    if invoice_id:
        return [invoice_id]
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT invoice_id FROM invoices ORDER BY invoice_id ASC").fetchall()
    return [str(row[0]) for row in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile a ledger for a case or the whole database.")
    parser.add_argument("--db-path", default="data/escalator.db")
    parser.add_argument("--invoice-id")
    args = parser.parse_args()

    store = SQLiteStore(args.db_path)
    invoice_ids = _list_invoice_ids(args.db_path, args.invoice_id)
    findings: list[dict[str, object]] = []

    for invoice_id in invoice_ids:
        chain_valid = store.verify_chain(invoice_id)
        debtor_entries = store.debtor_ledger_entries_for_invoice(invoice_id)
        client_entries = store.client_fee_entries_for_invoice(invoice_id)
        debtor_balance = sum((entry.amount_gbp for entry in debtor_entries), start=Decimal("0.00"))
        client_balance = sum((entry.fee_amount_gbp + entry.vat_gbp for entry in client_entries), start=Decimal("0.00"))

        if not chain_valid:
            findings.append({
                "invoice_id": invoice_id,
                "status": "drift",
                "message": "Hash chain mismatch detected.",
                "debtor_balance_gbp": str(debtor_balance),
                "client_balance_gbp": str(client_balance),
            })
        elif not debtor_entries and not client_entries:
            findings.append({
                "invoice_id": invoice_id,
                "status": "info",
                "message": "No debtor or client fee entries recorded.",
                "debtor_balance_gbp": "0.00",
                "client_balance_gbp": "0.00",
            })

    print(json.dumps({"invoice_count": len(invoice_ids), "findings": findings}, indent=2, sort_keys=True))
    return 1 if findings and any(item["status"] == "drift" for item in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
