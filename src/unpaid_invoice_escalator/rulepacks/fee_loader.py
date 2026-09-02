from __future__ import annotations
#
# First Cairn Digital
# P26003 rulepack selection safety

import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from unpaid_invoice_escalator.models import ClientFeeAction, Jurisdiction


def _version_sort_key(value: str) -> tuple[tuple[int, object], ...]:
    tokens: list[tuple[int, object]] = []
    for fragment in re.split(r"[^0-9A-Za-z]+", str(value).strip()):
        if not fragment:
            continue
        if fragment.isdigit():
            tokens.append((0, int(fragment)))
        else:
            tokens.append((1, fragment.lower()))
    return tuple(tokens)


def _candidate_status_rank(raw: dict[str, object]) -> int:
    if raw.get("active") is False:
        return -1
    if raw.get("approved") is False:
        return -1
    status = str(raw.get("status", "ACTIVE")).upper()
    if status not in {"ACTIVE", "APPROVED"}:
        return -1
    return 1


def _select_single_candidate(candidates: list[object], *, label: str) -> object:
    if not candidates:
        raise ValueError(f"No active {label} for the requested date/context")
    best_rank = max((candidate.effective_from, _version_sort_key(candidate.version if hasattr(candidate, "version") else candidate.rule_version), 1) for candidate in candidates)
    tied = [
        candidate
        for candidate in candidates
        if (candidate.effective_from, _version_sort_key(candidate.version if hasattr(candidate, "version") else candidate.rule_version), 1) == best_rank
    ]
    if len(tied) > 1:
        names = ", ".join(getattr(candidate, "schedule_id", getattr(candidate, "rule_id", "unknown")) for candidate in tied)
        raise ValueError(f"Ambiguous {label} selection for the requested date/context: {names}")
    return tied[0]


@dataclass(frozen=True)
class PricingSchedule:
    schedule_id: str
    version: str
    effective_from: date
    effective_to: date | None
    source_reference: str
    vat_rate: Decimal
    action_fees: dict[ClientFeeAction, Decimal]


@dataclass(frozen=True)
class CourtFeeBand:
    min_claim: Decimal
    max_claim: Decimal | None
    fixed_fee: Decimal | None
    percentage_rate: Decimal | None


@dataclass(frozen=True)
class CourtFeeSchedule:
    schedule_id: str
    jurisdiction: Jurisdiction
    version: str
    effective_from: date
    effective_to: date | None
    source_reference: str
    fee_bands: tuple[CourtFeeBand, ...]


class FeePackLoader:
    def __init__(self, base_path: str | None = None) -> None:
        if base_path is None:
            self._base_path = Path(__file__).resolve().parent / "fee_packs"
        else:
            self._base_path = Path(base_path)

    def load_pricing_schedule(self, on_date: date) -> PricingSchedule:
        schedules: list[PricingSchedule] = []
        for path in sorted(self._base_path.glob("pricing_schedule*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            if _candidate_status_rank(raw) < 0:
                continue
            effective_from = date.fromisoformat(raw["effective_from"])
            effective_to = date.fromisoformat(raw["effective_to"]) if raw.get("effective_to") else None
            if not (effective_from <= on_date and (effective_to is None or on_date <= effective_to)):
                continue
            schedules.append(
                PricingSchedule(
                    schedule_id=raw["schedule_id"],
                    version=raw["version"],
                    effective_from=effective_from,
                    effective_to=effective_to,
                    source_reference=raw["source_reference"],
                    vat_rate=Decimal(str(raw["vat_rate"])),
                    action_fees={ClientFeeAction(key): Decimal(str(value)) for key, value in raw["action_fees"].items()},
                )
            )
        if not schedules:
            raise ValueError(f"No active pricing schedule for {on_date.isoformat()}")
        return _select_single_candidate(schedules, label=f"pricing schedule on {on_date.isoformat()}")

    def load_court_fee_schedule(self, jurisdiction: Jurisdiction, on_date: date) -> CourtFeeSchedule:
        schedules: list[CourtFeeSchedule] = []
        for path in sorted(self._base_path.glob("court_fees*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            if raw["jurisdiction"] != jurisdiction.value:
                continue
            if _candidate_status_rank(raw) < 0:
                continue
            effective_from = date.fromisoformat(raw["effective_from"])
            effective_to = date.fromisoformat(raw["effective_to"]) if raw.get("effective_to") else None
            if not (effective_from <= on_date and (effective_to is None or on_date <= effective_to)):
                continue
            schedules.append(
                CourtFeeSchedule(
                    schedule_id=raw["schedule_id"],
                    jurisdiction=Jurisdiction(raw["jurisdiction"]),
                    version=raw["version"],
                    effective_from=effective_from,
                    effective_to=effective_to,
                    source_reference=raw["source_reference"],
                    fee_bands=tuple(
                        CourtFeeBand(
                            min_claim=Decimal(str(band["min_claim"])),
                            max_claim=Decimal(str(band["max_claim"])) if band.get("max_claim") is not None else None,
                            fixed_fee=Decimal(str(band["fixed_fee"])) if band.get("fixed_fee") is not None else None,
                            percentage_rate=(
                                Decimal(str(band["percentage_rate"])) if band.get("percentage_rate") is not None else None
                            ),
                        )
                        for band in raw["fee_bands"]
                    ),
                )
            )
        if not schedules:
            raise ValueError(f"No active court fee schedule for {jurisdiction.value} on {on_date.isoformat()}")
        return _select_single_candidate(schedules, label=f"court fee schedule for {jurisdiction.value} on {on_date.isoformat()}")

    def quote_court_fee(self, jurisdiction: Jurisdiction, claim_value: Decimal, on_date: date) -> Decimal:
        schedule = self.load_court_fee_schedule(jurisdiction, on_date)
        for band in schedule.fee_bands:
            in_min = claim_value >= band.min_claim
            in_max = band.max_claim is None or claim_value <= band.max_claim
            if not (in_min and in_max):
                continue
            if band.fixed_fee is not None:
                return band.fixed_fee
            if band.percentage_rate is not None:
                return (claim_value * band.percentage_rate).quantize(Decimal("0.01"))
        raise ValueError(f"No matching fee band for claim value {claim_value}")

