from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from decimal import Decimal
from typing import Sequence

from unpaid_invoice_escalator.models import DebtorType, Invoice, InvoiceState, Jurisdiction
from unpaid_invoice_escalator.ops_cli import ADMIN_COMMANDS, run_admin_cli
from unpaid_invoice_escalator.services.escalation_runner import EscalationRunner
from unpaid_invoice_escalator.services.jurisdiction_engine import JurisdictionFacts


def _build_legacy_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unpaid invoice escalation workflow runner.")
    parser.add_argument("--invoice-id", required=True)
    parser.add_argument("--currency", default="GBP")
    parser.add_argument("--principal", required=True, help="Principal amount, e.g. 1250.50")
    parser.add_argument("--issue-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--due-date", required=True, help="YYYY-MM-DD")
    parser.add_argument(
        "--jurisdiction",
        required=True,
        choices=[j.value for j in Jurisdiction],
    )
    parser.add_argument(
        "--debtor-type",
        required=True,
        choices=[d.value for d in DebtorType],
    )
    parser.add_argument(
        "--current-state",
        default=InvoiceState.ISSUED.value,
        choices=[s.value for s in InvoiceState],
    )
    parser.add_argument("--today", required=True, help="YYYY-MM-DD")
    parser.add_argument("--state-entered-on", help="YYYY-MM-DD")
    parser.add_argument("--debtor-feedback", help="e.g. DISPUTE")
    parser.add_argument("--system-flag", help="e.g. BREATHING_SPACE")
    parser.add_argument("--insolvency-flag", action="store_true")
    parser.add_argument("--payment-plan-proposed", action="store_true")
    parser.add_argument("--partially-paid", action="store_true")
    parser.add_argument("--regulated-debt-suspected", action="store_true")
    parser.add_argument(
        "--contract-jurisdiction",
        choices=[j.value for j in Jurisdiction],
        help="Optional contract clause jurisdiction for ambiguity checks.",
    )
    parser.add_argument("--creditor-country-code", help="Optional creditor country code, e.g. GB-ENG")
    parser.add_argument("--debtor-country-code", help="Optional debtor country code, e.g. GB-SCT")
    parser.add_argument("--place-of-supply-country-code", help="Optional place of supply country code, e.g. GB-NIR")
    return parser


def _run_legacy_cli(argv: Sequence[str]) -> int:
    parser = _build_legacy_parser()
    args = parser.parse_args(list(argv))

    invoice = Invoice(
        invoice_id=args.invoice_id,
        currency=args.currency,
        principal_amount=Decimal(args.principal),
        issue_date=date.fromisoformat(args.issue_date),
        due_date=date.fromisoformat(args.due_date),
        jurisdiction=Jurisdiction(args.jurisdiction),
        debtor_type=DebtorType(args.debtor_type),
    )

    runner = EscalationRunner()
    result = runner.run_step(
        invoice=invoice,
        current_state=InvoiceState(args.current_state),
        today=date.fromisoformat(args.today),
        state_entered_on=date.fromisoformat(args.state_entered_on) if args.state_entered_on else None,
        debtor_feedback=args.debtor_feedback,
        system_flag=args.system_flag,
        insolvency_flag=args.insolvency_flag,
        payment_plan_proposed=args.payment_plan_proposed,
        partially_paid=args.partially_paid,
        regulated_debt_suspected=args.regulated_debt_suspected,
        jurisdiction_facts=(
            None
            if (
                args.contract_jurisdiction is None
                and args.creditor_country_code is None
                and args.debtor_country_code is None
                and args.place_of_supply_country_code is None
            )
            else JurisdictionFacts(
                creditor_country_code=args.creditor_country_code,
                debtor_country_code=args.debtor_country_code,
                contract_jurisdiction=(
                    None if args.contract_jurisdiction is None else Jurisdiction(args.contract_jurisdiction)
                ),
                place_of_supply_country_code=args.place_of_supply_country_code,
            )
        ),
    )
    payload = {
        "invoice_id": invoice.invoice_id,
        "next_state": result.decision.next_state.value,
        "outreach_frozen": result.decision.outreach_frozen,
        "instructions": result.decision.instructions,
        "documents_to_generate": list(result.decision.documents_to_generate),
        "wait_until": result.decision.wait_until.isoformat() if result.decision.wait_until else None,
        "recorded_at": result.recorded_at.isoformat(),
    }
    print(json.dumps(payload, indent=2))
    return 0


def _detect_admin_command(argv: Sequence[str]) -> str | None:
    for token in argv:
        if token.startswith("-"):
            continue
        return token if token in ADMIN_COMMANDS else None
    return None


def main(argv: Sequence[str] | None = None) -> int:
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    if _detect_admin_command(effective_argv) is not None:
        return run_admin_cli(effective_argv)
    return _run_legacy_cli(effective_argv)


if __name__ == "__main__":
    raise SystemExit(main())
