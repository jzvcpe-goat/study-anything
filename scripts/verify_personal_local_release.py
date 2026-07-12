#!/usr/bin/env python3
"""Verify the Delivery Clearance Personal Local Alpha release candidate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tomllib
from typing import Literal

from pydantic import BaseModel, ConfigDict


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.cbb.protocol.canonical import (  # type: ignore[import-untyped]  # noqa: E402
    pretty_json,
    schema_text,
)


SCHEMA_VERSION = "delivery-clearance.personal-local-release-v1"
PACKAGE_VERSION = "0.3.32-alpha"
RELEASE_TAG = "v0.3.32-alpha"
RELEASE_TITLE = "Delivery Clearance Personal Local Alpha"
WHEEL_FILENAME = "study_anything-0.3.32a0-py3-none-any.whl"
REPORT_PATH = ROOT / "platform/generated/delivery-clearance-personal-local-release.json"
SCHEMA_PATH = ROOT / f"platform/schemas/cbb/{SCHEMA_VERSION}.schema.json"


class ReleaseIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_name: Literal["Delivery Clearance"] = "Delivery Clearance"
    protocol_name: Literal["AI Delivery Clearance Protocol"] = "AI Delivery Clearance Protocol"
    release_title: Literal["Delivery Clearance Personal Local Alpha"] = (
        "Delivery Clearance Personal Local Alpha"
    )
    tag: Literal["v0.3.32-alpha"] = "v0.3.32-alpha"
    package_version: Literal["0.3.32-alpha"] = "0.3.32-alpha"
    python_distribution: Literal["study-anything"] = "study-anything"
    wheel_filename: Literal["study_anything-0.3.32a0-py3-none-any.whl"] = (
        "study_anything-0.3.32a0-py3-none-any.whl"
    )
    repository_slug_compatibility: Literal["study-anything"] = "study-anything"


class ReleaseClaimBoundary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    maximum_scope: Literal["personal_local"] = "personal_local"
    self_attested: Literal[True] = True
    customer_delivery_authorized: Literal[False] = False
    production_authorized: Literal[False] = False
    external_write_authorized: Literal[False] = False
    independent_audit_completed: Literal[False] = False
    published_image_claimed: Literal[False] = False
    not_claimed: list[str]


class PersonalLocalReleaseReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["delivery-clearance.personal-local-release-v1"] = (
        "delivery-clearance.personal-local-release-v1"
    )
    status: Literal["pass"] = "pass"
    identity: ReleaseIdentity
    entrypoints: list[str]
    checks: dict[str, bool]
    required_before_tag: list[str]
    claim_boundary: ReleaseClaimBoundary
    privacy: dict[str, bool]


def _contains(path: str, *needles: str) -> bool:
    text = (ROOT / path).read_text(encoding="utf-8")
    return all(needle in text for needle in needles)


def build_receipt() -> PersonalLocalReleaseReceipt:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    scripts = project.get("scripts", {})
    checks = {
        "package_version_matches": project.get("version") == PACKAGE_VERSION,
        "compatibility_distribution_preserved": project.get("name") == "study-anything",
        "personal_cli_declared": (
            scripts.get("delivery-clearance") == "study_anything.cbb.personal.cli:main"
        ),
        "plugin_evidence_cli_declared": (
            scripts.get("delivery-clearance-plugin-evidence")
            == "study_anything.cbb.plugin_evidence.cli:main"
        ),
        "readme_uses_delivery_clearance_identity": _contains(
            "README.md",
            "# Delivery Clearance",
            "**未经放行，不得交付。**",
            RELEASE_TAG,
            RELEASE_TITLE,
        ),
        "release_notes_are_claim_bounded": _contains(
            "docs/release-notes/v0.3.32-alpha.md",
            RELEASE_TITLE,
            "maximum clearance scope is `personal_local`",
            "does not authorize external writes",
        ),
        "release_checklist_covers_both_clis": _contains(
            "docs/release-checklist.md",
            "verify_personal_clearance_mvp.py --check",
            "verify_plugin_evidence_adapter.py --check",
            "verify_personal_local_release.py --check",
            WHEEL_FILENAME,
        ),
        "tag_workflow_is_bounded": _contains(
            ".github/workflows/delivery-clearance-personal-release.yml",
            RELEASE_TAG,
            "uv build --wheel --out-dir dist",
            "delivery-clearance-plugin-evidence --help",
            "gh release create",
            RELEASE_TITLE,
        ),
        "release_gate_runs_personal_release_verifier": _contains(
            "scripts/release_check.sh",
            "verify_personal_local_release.py --check",
            "personal_local_release_verifier_passed",
        ),
        "github_guide_requires_full_clean_clone": _contains(
            "docs/github-launch.md",
            "complete clean-clone release receipt",
            "cannot authorize the tag",
        ),
        "repository_slug_is_documented_as_compatibility": _contains(
            "docs/naming-and-compatibility.md",
            "repository slug and Python distribution retain",
            "personal-local release",
        ),
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise RuntimeError("personal-local release checks failed: " + ", ".join(failed))

    return PersonalLocalReleaseReceipt(
        identity=ReleaseIdentity(),
        entrypoints=["delivery-clearance", "delivery-clearance-plugin-evidence"],
        checks=checks,
        required_before_tag=[
            "merge release candidate to main",
            "all required GitHub checks pass",
            "full release_check.sh completes on the exact merge commit",
            "clean_clone_completed is true",
            "dependency_install_completed is true",
            "wheel installs and both public CLIs run outside the checkout",
        ],
        claim_boundary=ReleaseClaimBoundary(
            not_claimed=[
                "AI or plugin correctness",
                "independent review",
                "customer delivery authority",
                "production approval",
                "external write authority",
                "legal, security, compliance, or professional-domain certification",
                "OS-level containment of configured project checks",
                "a new published-image release line",
            ]
        ),
        privacy={
            "metadata_only": True,
            "raw_source_text_included": False,
            "raw_check_output_included": False,
            "local_absolute_paths_included": False,
            "model_credentials_included": False,
            "automatic_external_delivery_performed": False,
        },
    )


def expected_outputs() -> dict[Path, str]:
    receipt = build_receipt()
    return {
        SCHEMA_PATH: schema_text(PersonalLocalReleaseReceipt),
        REPORT_PATH: pretty_json(receipt),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check == args.write:
        raise SystemExit("Choose exactly one of --check or --write.")

    outputs = expected_outputs()
    if args.write:
        for path, content in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    else:
        stale = [
            path.relative_to(ROOT).as_posix()
            for path, expected in outputs.items()
            if not path.is_file() or path.read_text(encoding="utf-8") != expected
        ]
        if stale:
            raise SystemExit(
                "Personal Local Alpha release artifacts are stale. Run: "
                "python3 scripts/verify_personal_local_release.py --write\n" + "\n".join(stale)
            )

    print(json.dumps(build_receipt().model_dump(mode="json"), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
