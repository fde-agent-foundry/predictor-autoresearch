"""JSON file interface used by the FDE Foundry bundle adapter."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .policy import PolicyContractError, build_policy


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        request = json.loads(args.contract.read_text(encoding="utf-8"))
        result = build_policy(request)
    except (OSError, json.JSONDecodeError, PolicyContractError) as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
