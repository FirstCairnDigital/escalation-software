from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from unpaid_invoice_escalator.production_config import validate_production_config


def main() -> int:
    env = dict(os.environ)
    result = validate_production_config(env)
    if not result["valid"]:
        print("Production configuration validation failed.")
        for err in result["errors"]:
            print(f" - {err}")
        return 1
    print("Production configuration validation passed.")
    print(json.dumps({"checks": result["checks"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
