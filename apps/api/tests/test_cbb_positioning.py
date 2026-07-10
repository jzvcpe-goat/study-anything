from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


REPO = Path(__file__).resolve().parents[3]
VERIFIER = REPO / "scripts" / "verify_cbb_positioning.py"


def load_verifier() -> ModuleType:
    spec = importlib.util.spec_from_file_location("verify_cbb_positioning", VERIFIER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cbb_positioning_report_matches_protocol_first_contract() -> None:
    module = load_verifier()
    report = module.build_report()

    assert report["status"] == "pass"
    assert report["canonical_name"] == "Cognitive Black Box Protocol"
    assert report["reference_implementation"] == "CBB Reference Harness"
    assert report["study_anything_role"] == "Human Reconstruction / Learning Adapter"
    assert report["legacy_leakage"]["findings"] == []
    assert report["package_metadata"]["distribution_name"] == "study-anything"
    assert report["package_metadata"]["distribution_name_is_compatibility_only"] is True


def test_positioning_contract_keeps_obsolete_brand_out_of_current_sources() -> None:
    module = load_verifier()

    assert "Cognitive Loop System" in module.BANNED_CURRENT_FRAMING
    assert "docs/naming-and-compatibility.md" in module.ALLOWED_BANNED_TERM_FILES
    assert "platform/generated" in module.SCAN_ROOTS
