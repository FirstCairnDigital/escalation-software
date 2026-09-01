from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from unpaid_invoice_escalator.ops_cli import run_admin_cli


def main() -> int:
    return run_admin_cli()


if __name__ == "__main__":
    raise SystemExit(main())
