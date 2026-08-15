from __future__ import annotations

import json
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
            pack = self._to_rule_pack(raw)
            if pack.effective_from <= on_date and (pack.effective_to is None or on_date <= pack.effective_to):
                candidates.append(pack)

        if not candidates:
            raise ValueError(f"No active rule pack for {jurisdiction.value} on {on_date.isoformat()}")
        return candidates[-1]

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
