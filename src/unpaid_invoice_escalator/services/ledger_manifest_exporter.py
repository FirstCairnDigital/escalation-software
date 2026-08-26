from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore
from unpaid_invoice_escalator.services.pdf_text_renderer import TextPdfRenderer


class LedgerManifestExporter:
    def __init__(
        self,
        *,
        store: SQLiteStore,
        signing_key: str,
        key_id: str = "fcd-local-key",
        verification_keys: dict[str, str] | None = None,
    ) -> None:
        self._store = store
        self._signing_key = signing_key
        self._key_id = key_id
        self._pdf_renderer = TextPdfRenderer(margin_left=48, font_size=10, line_height=12)
        keys = dict(verification_keys or {})
        keys.setdefault(key_id, signing_key)
        self._verification_keys = keys

    def export_invoice_manifest(self, *, invoice_id: str, output_path: str) -> dict[str, Any]:
        manifest = self._build_manifest(invoice_id=invoice_id)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    def export_invoice_manifest_pdf(self, *, invoice_id: str, output_path: str) -> dict[str, Any]:
        manifest = self._build_manifest(invoice_id=invoice_id)
        lines = self._manifest_lines(manifest)
        pdf_bytes = self._pdf_renderer.render(lines)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pdf_bytes)
        return manifest

    def verify_invoice_manifest(self, *, invoice_id: str, manifest_path: str) -> dict[str, Any]:
        path = Path(manifest_path)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        signature = manifest.get("signature", {})
        signature_key_id = str(signature.get("key_id", ""))
        signature_value = str(signature.get("value", ""))

        manifest_core = dict(manifest)
        manifest_core.pop("signature", None)
        verification_candidates: list[tuple[str, str]] = []
        selected_key = self._verification_keys.get(signature_key_id)
        if selected_key is not None:
            verification_candidates.append((signature_key_id, selected_key))
        for candidate_key_id, candidate_key in self._verification_keys.items():
            if candidate_key_id == signature_key_id:
                continue
            verification_candidates.append((candidate_key_id, candidate_key))

        verified_with_key_id: str | None = None
        signature_valid = False
        for candidate_key_id, candidate_key in verification_candidates:
            computed_signature = self._sign_manifest_core(manifest_core, candidate_key)
            if hmac.compare_digest(signature_value, computed_signature):
                signature_valid = True
                verified_with_key_id = candidate_key_id
                break

        expected_manifest = self._build_manifest(invoice_id=invoice_id)
        expected_core = dict(expected_manifest)
        expected_core.pop("signature", None)
        manifest_core_for_compare = dict(manifest_core)
        expected_core_for_compare = dict(expected_core)
        manifest_core_for_compare.pop("generated_at", None)
        expected_core_for_compare.pop("generated_at", None)

        core_matches_current_ledger = manifest_core_for_compare == expected_core_for_compare
        chain_valid = bool(manifest.get("chain_valid")) and core_matches_current_ledger
        return {
            "signature_valid": signature_valid,
            "signature_key_id": signature_key_id or None,
            "verified_with_key_id": verified_with_key_id,
            "core_matches_current_ledger": core_matches_current_ledger,
            "chain_valid": chain_valid,
            "overall_valid": signature_valid and core_matches_current_ledger and chain_valid,
        }

    def _build_manifest(self, *, invoice_id: str) -> dict[str, Any]:
        invoice = self._store.get_invoice(invoice_id)
        if invoice is None:
            raise ValueError("Invoice not found.")
        events = self._store.events_for_invoice(invoice_id)
        outstanding_balance_gbp = self._store.debtor_ledger_balance_for_invoice(invoice_id)
        nodes: list[dict[str, Any]] = []
        previous_hash = "GENESIS"
        for idx, event in enumerate(events, start=1):
            payload = json.dumps(event.data_payload, sort_keys=True, separators=(",", ":"), default=str)
            chain_input = "|".join(
                [
                    event.event_id,
                    event.invoice_id,
                    event.timestamp.isoformat(),
                    event.actor.value,
                    event.event_type,
                    payload,
                    previous_hash,
                ]
            )
            expected_hash = hashlib.sha256(chain_input.encode("utf-8")).hexdigest()
            node_valid = event.previous_hash == previous_hash and event.hash == expected_hash
            nodes.append(
                {
                    "index": idx,
                    "event_id": event.event_id,
                    "timestamp": event.timestamp.isoformat(),
                    "actor": event.actor.value,
                    "event_type": event.event_type,
                    "previous_hash": event.previous_hash,
                    "expected_previous_hash": previous_hash,
                    "event_hash": event.hash,
                    "expected_event_hash": expected_hash,
                    "node_valid": node_valid,
                }
            )
            previous_hash = event.hash

        manifest_core: dict[str, Any] = {
            "manifest_version": "1.0",
            "invoice_id": invoice_id,
            "principal_amount_gbp": str(invoice.principal_amount),
            "outstanding_balance_gbp": str(outstanding_balance_gbp),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "events_count": len(events),
            "chain_valid": all(node["node_valid"] for node in nodes),
            "root_hash": previous_hash if nodes else "GENESIS",
            "hash_validation_tree": nodes,
        }
        signature = self._sign_manifest_core(manifest_core)
        manifest = {
            **manifest_core,
            "signature": {
                "algorithm": "HMAC-SHA256",
                "key_id": self._key_id,
                "value": signature,
            },
        }
        return manifest

    def _sign_manifest_core(self, manifest_core: dict[str, Any], signing_key: str | None = None) -> str:
        canonical = json.dumps(manifest_core, sort_keys=True, separators=(",", ":"), default=str)
        key = self._signing_key if signing_key is None else signing_key
        return hmac.new(key.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()

    def _manifest_lines(self, manifest: dict[str, Any]) -> list[str]:
        lines: list[str] = [
            "Tamper-Evident Ledger Manifest",
            "",
            f"Invoice ID: {manifest['invoice_id']}",
            f"Generated At: {manifest['generated_at']}",
            f"Manifest Version: {manifest['manifest_version']}",
            f"Original Principal: GBP {manifest['principal_amount_gbp']}",
            f"Current Outstanding Balance: GBP {manifest['outstanding_balance_gbp']}",
            f"Events Count: {manifest['events_count']}",
            f"Chain Valid: {manifest['chain_valid']}",
            f"Root Hash: {manifest['root_hash']}",
            "",
            "Signature:",
            f"- Algorithm: {manifest['signature']['algorithm']}",
            f"- Key ID: {manifest['signature']['key_id']}",
            f"- Value: {manifest['signature']['value']}",
            "",
            "Hash Validation Tree:",
        ]
        for node in manifest["hash_validation_tree"]:
            lines.append(
                f"- #{node['index']} {node['event_type']} valid={node['node_valid']} hash={node['event_hash']}"
            )
        return lines
