from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
import sys
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore


def _signature(payload: dict[str, object], signing_key: str) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256((signing_key + canonical).encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a Small Business Commissioner bundle for manual offline submission.")
    parser.add_argument("--db-path", default="data/escalator.db")
    parser.add_argument("--invoice-id", required=True)
    parser.add_argument("--output", default="data/sbc-bundle.json")
    args = parser.parse_args()

    store = SQLiteStore(args.db_path)
    invoice = store.get_invoice(args.invoice_id)
    if invoice is None:
        raise SystemExit(f"Invoice not found: {args.invoice_id}")

    events = store.events_for_invoice(args.invoice_id)
    artifacts = store.artifacts_for_invoice(args.invoice_id)
    compliance = store.compliance_entries_for_invoice(args.invoice_id)
    payload = {
        "invoice_id": invoice.invoice_id,
        "jurisdiction": invoice.jurisdiction.value,
        "debtor_type": invoice.debtor_type.value,
        "principal_amount_gbp": str(invoice.principal_amount),
        "event_count": len(events),
        "artifact_count": len(artifacts),
        "compliance_entry_count": len(compliance),
        "manual_submission_needed": True,
        "exported_by": "manual-ops-script",
        "bundle_version": "1.0",
    }
    signing_key = os.getenv("CRYPTO_SIGNING_KEY", "manual-sbc-signing-key")
    payload["signature"] = _signature(payload, signing_key)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"SBC bundle exported to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
