from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True)
class BaseRateEntry:
    effective_from: date
    rate: Decimal


class BoEBaseRateProvider:
    def __init__(self, data_path: str | None = None) -> None:
        if data_path is None:
            data_path = str(Path(__file__).resolve().parent.parent / "reference_data" / "boe_base_rates.json")
        self._entries = self._load_entries(Path(data_path))

    def rate_for(self, reference_date: date) -> Decimal:
        eligible = [entry for entry in self._entries if entry.effective_from <= reference_date]
        if not eligible:
            raise ValueError(f"No Bank of England base rate entry available for {reference_date.isoformat()}")
        return eligible[-1].rate

    @staticmethod
    def _load_entries(path: Path) -> list[BaseRateEntry]:
        raw = json.loads(path.read_text(encoding="utf-8"))
        entries = [
            BaseRateEntry(
                effective_from=date.fromisoformat(item["effective_from"]),
                rate=Decimal(str(item["rate"])),
            )
            for item in raw["entries"]
        ]
        entries.sort(key=lambda item: item.effective_from)
        return entries

