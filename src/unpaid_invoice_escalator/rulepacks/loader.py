from __future__ import annotations
#
# First Cairn Digital
# P26003 rulepack selection safety

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from unpaid_invoice_escalator.models import Jurisdiction


@dataclass(frozen=True)
class RulePack:
    rule_id: str
    jurisdiction: Jurisdiction
    rule_version: str
    effective_from: date
    effective_to: date | None
    source_authority: str
    source_reference: str
    fcd_automation_limit: float
    human_approval_required: bool
    workflow: dict[str, object]


class RulePackValidationError(ValueError):
    pass


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


def _select_single_candidate(candidates: list[RulePack], *, label: str) -> RulePack:
    if not candidates:
        raise ValueError(f"No active {label} for the requested date/context")
    best_score = max((candidate.effective_from, _version_sort_key(candidate.rule_version), 1) for candidate in candidates)
    tied = [candidate for candidate in candidates if (candidate.effective_from, _version_sort_key(candidate.rule_version), 1) == best_score]
    if len(tied) > 1:
        names = ", ".join(candidate.rule_id for candidate in tied)
        raise RulePackValidationError(f"Ambiguous {label} selection for the requested date/context: {names}")
    return tied[0]


class RulePackLoader:
    _required_fields = (
        "rule_id",
        "jurisdiction",
        "rule_version",
        "effective_from",
        "effective_to",
        "source_authority",
        "source_reference",
        "fcd_automation_limit",
        "human_approval_required",
        "workflow",
    )

    def __init__(self, base_path: str | None = None) -> None:
        if base_path is None:
            self._base_path = Path(__file__).resolve().parent / "packs"
        else:
            self._base_path = Path(base_path)

    def load_for(self, jurisdiction: Jurisdiction, on_date: date) -> RulePack:
        candidates: list[RulePack] = []
        for path in sorted(self._base_path.glob("*.json")):
            raw = self._load_raw(path)
            if raw["jurisdiction"] != jurisdiction.value:
                continue
            if _candidate_status_rank(raw) < 0:
                continue
            pack = self._to_rule_pack(raw)
            if pack.effective_from <= on_date and (pack.effective_to is None or on_date <= pack.effective_to):
                candidates.append(pack)

        if not candidates:
            raise ValueError(f"No active rule pack for {jurisdiction.value} on {on_date.isoformat()}")
        return _select_single_candidate(candidates, label=f"rule pack for {jurisdiction.value} on {on_date.isoformat()}")

    def describe_active(self, jurisdiction: Jurisdiction, on_date: date) -> dict[str, Any]:
        pack = self.load_for(jurisdiction, on_date)
        return {
            "rule_id": pack.rule_id,
            "jurisdiction": pack.jurisdiction.value,
            "rule_version": pack.rule_version,
            "effective_from": pack.effective_from.isoformat(),
            "effective_to": pack.effective_to.isoformat() if pack.effective_to else None,
            "source_authority": pack.source_authority,
            "source_reference": pack.source_reference,
            "fcd_automation_limit": pack.fcd_automation_limit,
            "human_approval_required": pack.human_approval_required,
        }

    def _load_raw(self, path: Path) -> dict[str, object]:
        raw = json.loads(path.read_text(encoding="utf-8"))
        missing = [field for field in self._required_fields if field not in raw]
        if missing:
            raise RulePackValidationError(f"Rule pack {path.name} missing required fields: {', '.join(missing)}")
        if not isinstance(raw["workflow"], dict):
            raise RulePackValidationError(f"Rule pack {path.name} has invalid workflow structure.")
        return raw

    @staticmethod
    def _to_rule_pack(raw: dict[str, object]) -> RulePack:
        try:
            return RulePack(
                rule_id=str(raw["rule_id"]),
                jurisdiction=Jurisdiction(str(raw["jurisdiction"])),
                rule_version=str(raw["rule_version"]),
                effective_from=date.fromisoformat(str(raw["effective_from"])),
                effective_to=date.fromisoformat(str(raw["effective_to"])) if raw.get("effective_to") else None,
                source_authority=str(raw["source_authority"]),
                source_reference=str(raw["source_reference"]),
                fcd_automation_limit=float(raw["fcd_automation_limit"]),
                human_approval_required=bool(raw["human_approval_required"]),
                workflow=dict(raw["workflow"]),
            )
        except (TypeError, ValueError) as exc:
            raise RulePackValidationError(f"Invalid rule pack payload: {exc}") from exc
