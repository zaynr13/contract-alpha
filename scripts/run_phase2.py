#!/usr/bin/env python3
"""Build the scoped Contract Alpha research dataset and model outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from contract_alpha.analysis import run_phase2  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--public-output-dir",
        type=Path,
        default=ROOT / "data" / "processed" / "phase2",
    )
    parser.add_argument(
        "--private-output-dir",
        type=Path,
        default=ROOT / "data" / "processed" / "private",
    )
    args = parser.parse_args()
    summary = run_phase2(args.public_output_dir, args.private_output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
