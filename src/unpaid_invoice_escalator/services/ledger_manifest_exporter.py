from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore


class LedgerManifestExporter:
    def __init__(self, *, store: SQLiteStore, signing_key: str, key_id: str = "fcd-local-key") -> None:
        self._store = store
        self._signing_key = signing_key
        self._key_id = key_id

    def export_invoice_manifest(self, *, invoice_id: str, output_path: str) -> dict[str, Any]:
        manifest = self._build_manifest(invoice_id=invoice_id)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    def export_invoice_manifest_pdf(self, *, invoice_id: str, output_path: str) -> dict[str, Any]:
        manifest = self._build_manifest(invoice_id=invoice_id)
        lines = self._manifest_lines(manifest)
        pdf_bytes = self._render_single_page_pdf(lines)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pdf_bytes)
        return manifest

    def verify_invoice_manifest(self, *, invoice_id: str, manifest_path: str) -> dict[str, Any]:
        path = Path(manifest_path)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        signature = manifest.get("signature", {})
        signature_value = str(signature.get("value", ""))

        manifest_core = dict(manifest)
        manifest_core.pop("signature", None)
        computed_signature = self._sign_manifest_core(manifest_core)
        signature_valid = hmac.compare_digest(signature_value, computed_signature)

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
            "core_matches_current_ledger": core_matches_current_ledger,
            "chain_valid": chain_valid,
            "overall_valid": signature_valid and core_matches_current_ledger and chain_valid,
        }

    def _build_manifest(self, *, invoice_id: str) -> dict[str, Any]:
        events = self._store.events_for_invoice(invoice_id)
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

    def _sign_manifest_core(self, manifest_core: dict[str, Any]) -> str:
        canonical = json.dumps(manifest_core, sort_keys=True, separators=(",", ":"), default=str)
        return hmac.new(self._signing_key.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()

    def _manifest_lines(self, manifest: dict[str, Any]) -> list[str]:
        lines: list[str] = [
            "Tamper-Evident Ledger Manifest",
            "",
            f"Invoice ID: {manifest['invoice_id']}",
            f"Generated At: {manifest['generated_at']}",
            f"Manifest Version: {manifest['manifest_version']}",
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

    def _render_single_page_pdf(self, lines: list[str]) -> bytes:
        safe_lines = [self._escape_pdf_text(line) for line in lines]
        y_start = 780
        line_height = 12
        commands = ["BT", "/F1 10 Tf", f"48 {y_start} Td"]
        for i, line in enumerate(safe_lines):
            if i > 0:
                commands.append(f"0 -{line_height} Td")
            commands.append(f"({line}) Tj")
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1", errors="replace")

        objects: list[bytes] = []
        objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
        objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        )
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream")

        pdf = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for idx, obj in enumerate(objects, start=1):
            offsets.append(len(pdf))
            pdf.extend(f"{idx} 0 obj\n".encode("latin-1"))
            pdf.extend(obj)
            pdf.extend(b"\nendobj\n")

        xref_start = len(pdf)
        pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
        pdf.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
        pdf.extend(
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode("latin-1")
        )
        return bytes(pdf)

    @staticmethod
    def _escape_pdf_text(value: str) -> str:
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
