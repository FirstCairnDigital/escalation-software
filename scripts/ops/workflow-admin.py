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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run compliance and retention workflows without a separate API server.")
    parser.add_argument("--db-path", default="data/escalator.db")
    parser.add_argument("--artifacts-dir", default="data/artifacts")
    parser.add_argument("--bundles-dir", default="data/bundles")
    subparsers = parser.add_subparsers(dest="command", required=True)

    retention_queue = subparsers.add_parser("retention-queue", help="Summarise retention queue status.")
    retention_queue.add_argument("--as-of-date")
    retention_queue.add_argument("--upcoming-within-days", type=int, default=45)

    company_status = subparsers.add_parser("company-status-check", help="Record a company-status check.")
    company_status.add_argument("--invoice-id", required=True)
    company_status.add_argument("--checked-by", required=True)
    company_status.add_argument("--company-status", required=True)
    company_status.add_argument("--source", default="COMPANIES_HOUSE")
    company_status.add_argument("--company-number")
    company_status.add_argument("--official-register-url")
    company_status.add_argument("--review-due-date")
    company_status.add_argument("--evidence-summary", required=True)
    company_status.add_argument("--notes", default="")

    breathing_open = subparsers.add_parser("breathing-space-open", help="Open a breathing-space restriction.")
    breathing_open.add_argument("--invoice-id", required=True)
    breathing_open.add_argument("--opened-by", required=True)
    breathing_open.add_argument("--source", required=True)
    breathing_open.add_argument("--reason", required=True)
    breathing_open.add_argument("--reference")
    breathing_open.add_argument("--start-date")
    breathing_open.add_argument("--expected-end-date")
    breathing_open.add_argument("--review-due-date")
    breathing_open.add_argument("--notes", default="")

    breathing_release = subparsers.add_parser("breathing-space-release", help="Release a breathing-space restriction.")
    breathing_release.add_argument("--invoice-id", required=True)
    breathing_release.add_argument("--released-by", required=True)
    breathing_release.add_argument("--release-reason", required=True)
    breathing_release.add_argument("--resolution-notes", required=True)
    breathing_release.add_argument("--resume-state", default="OVERDUE_CHASER")

    insolvency_open = subparsers.add_parser("insolvency-review-open", help="Open an insolvency review.")
    insolvency_open.add_argument("--invoice-id", required=True)
    insolvency_open.add_argument("--opened-by", required=True)
    insolvency_open.add_argument("--source", required=True)
    insolvency_open.add_argument("--reason", required=True)
    insolvency_open.add_argument("--review-due-date")
    insolvency_open.add_argument("--company-status-check-id")
    insolvency_open.add_argument("--notes", default="")

    insolvency_release = subparsers.add_parser("insolvency-review-release", help="Release an insolvency review.")
    insolvency_release.add_argument("--invoice-id", required=True)
    insolvency_release.add_argument("--released-by", required=True)
    insolvency_release.add_argument("--release-reason", required=True)
    insolvency_release.add_argument("--resolution-notes", required=True)
    insolvency_release.add_argument("--resume-state", default="OVERDUE_CHASER")

    restricted_note = subparsers.add_parser("restricted-note", help="Record a restricted case note.")
    restricted_note.add_argument("--invoice-id", required=True)
    restricted_note.add_argument("--created-by", required=True)
    restricted_note.add_argument("--note-category", required=True)
    restricted_note.add_argument("--summary", required=True)
    restricted_note.add_argument("--sensitive-details", required=True)
    restricted_note.add_argument("--related-event-type", default="MANUAL_RESTRICTED_NOTE")

    return parser


def _command_request(args: argparse.Namespace) -> tuple[str, dict[str, object], dict[str, object] | None]:
    if args.command == "retention-queue":
        params: dict[str, object] = {"upcoming_within_days": args.upcoming_within_days}
        if args.as_of_date:
            params["as_of_date"] = args.as_of_date
        return "GET", {"path": "/data-retention-queue", "params": params}, None
    if args.command == "company-status-check":
        return "POST", {"path": f"/invoices/{args.invoice_id}/company-status-checks"}, {
            "checked_by": args.checked_by,
            "company_status": args.company_status,
            "source": args.source,
            "company_number": args.company_number,
            "official_register_url": args.official_register_url,
            "review_due_date": args.review_due_date,
            "evidence_summary": args.evidence_summary,
            "notes": args.notes,
        }
    if args.command == "breathing-space-open":
        return "POST", {"path": f"/invoices/{args.invoice_id}/breathing-space/open"}, {
            "opened_by": args.opened_by,
            "source": args.source,
            "reason": args.reason,
            "reference": args.reference,
            "start_date": args.start_date,
            "expected_end_date": args.expected_end_date,
            "review_due_date": args.review_due_date,
            "notes": args.notes,
        }
    if args.command == "breathing-space-release":
        return "POST", {"path": f"/invoices/{args.invoice_id}/breathing-space/release"}, {
            "released_by": args.released_by,
            "release_reason": args.release_reason,
            "resolution_notes": args.resolution_notes,
            "resume_state": args.resume_state,
        }
    if args.command == "insolvency-review-open":
        return "POST", {"path": f"/invoices/{args.invoice_id}/insolvency-reviews/open"}, {
            "opened_by": args.opened_by,
            "source": args.source,
            "reason": args.reason,
            "review_due_date": args.review_due_date,
            "company_status_check_id": args.company_status_check_id,
            "notes": args.notes,
        }
    if args.command == "insolvency-review-release":
        return "POST", {"path": f"/invoices/{args.invoice_id}/insolvency-reviews/release"}, {
            "released_by": args.released_by,
            "release_reason": args.release_reason,
            "resolution_notes": args.resolution_notes,
            "resume_state": args.resume_state,
        }
    if args.command == "restricted-note":
        return "POST", {"path": f"/invoices/{args.invoice_id}/restricted-notes"}, {
            "created_by": args.created_by,
            "note_category": args.note_category,
            "summary": args.summary,
            "sensitive_details": args.sensitive_details,
            "related_event_type": args.related_event_type,
        }
    raise ValueError(f"Unsupported command: {args.command}")


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    app = create_app(
        db_path=args.db_path,
        artifacts_dir=args.artifacts_dir,
        bundles_dir=args.bundles_dir,
    )
    method, request_meta, payload = _command_request(args)
    with TestClient(app) as client:
        if method == "GET":
            response = client.get(request_meta["path"], params=request_meta["params"])
        else:
            response = client.post(request_meta["path"], json=payload)
    response.raise_for_status()
    print(json.dumps(response.json(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
