#!/usr/bin/env python3
"""Generate controlled-adoption, external-attestation, and audit-intake assets."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.cbb.adoption.fixtures import (  # noqa: E402
    asset_outputs as adoption_outputs,
)
from study_anything.cbb.adoption.attestation_fixtures import (  # noqa: E402
    asset_outputs as adoption_attestation_outputs,
)
from study_anything.cbb.audit.fixtures import (  # noqa: E402
    asset_outputs as audit_outputs,
)


def expected_outputs() -> dict[Path, str]:
    return {
        **adoption_outputs(ROOT),
        **adoption_attestation_outputs(ROOT),
        **audit_outputs(ROOT),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = expected_outputs()
    if args.write:
        for path, content in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)}")
        return 0
    stale = [
        path.relative_to(ROOT).as_posix()
        for path, content in outputs.items()
        if not path.is_file() or path.read_text(encoding="utf-8") != content
    ]
    if stale:
        raise SystemExit(
            "CBB adoption/audit assets are stale; run "
            f"generate_cbb_adoption_audit_assets.py --write: {stale}"
        )
    print(
        f"ok    {len(outputs)} controlled-adoption, external-attestation, "
        "and audit-intake assets are current"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
