#!/usr/bin/env python3
"""Verify Cognitive Loop Personal Plugin Mode Lite."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "cognitive_loop_personal_mode.py"
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-personal-plugin-mode.json"
SCHEMA_VERSION = "cognitive-loop-personal-plugin-mode-verification-v1"


def run_json(command: list[str], *, cwd: Path = ROOT, required: bool = True) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if required and completed.returncode != 0:
        raise RuntimeError(
            f"Command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    if completed.returncode != 0:
        return {"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Command did not emit JSON: {' '.join(command)}\n{completed.stdout}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_no_forbidden_text(text: str, *, label: str) -> None:
    forbidden = [
        "sk-proj-",
        "bearer ",
        "raw source text",
        "raw diff",
        "learner answer:",
        "diff --git",
        "api_key",
        "agent endpoint:",
        "http://127.0.0.1:8787",
        "OPENAI_API_KEY",
        "MOONSHOT_API_KEY",
    ]
    lowered = text.lower()
    leaked = [needle for needle in forbidden if needle.lower() in lowered]
    if leaked:
        raise RuntimeError(f"{label} leaked forbidden text: {leaked}")


def write_fixture(root: Path) -> dict[str, Path]:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(parents=True, exist_ok=True)
    readme = root / "README.md"
    source = root / "src" / "learning_loop.py"
    readme.write_text(
        "# Study Anything Fixture\n\n"
        "This fixture describes a local-first learning project and its verification path.\n",
        encoding="utf-8",
    )
    source.write_text(
        "def run_learning_loop(stage: str) -> str:\n"
        "    return f'learning-stage:{stage}'\n",
        encoding="utf-8",
    )
    return {"readme": readme, "source": source}


def run_personal(root: Path, args: list[str]) -> tuple[dict[str, Any], str, str]:
    report = run_json(
        [
            sys.executable,
            str(CLI),
            "--root",
            str(root),
            "explain",
            "--html",
            "--markdown",
            "--json",
            "--generated-at",
            "2026-01-01T00:00:00Z",
            *args,
        ]
    )
    refs = report["outputs"]
    html = (root / refs["html_ref"]).read_text(encoding="utf-8")
    markdown = (root / refs["markdown_ref"]).read_text(encoding="utf-8")
    assert_no_forbidden_text(json.dumps(report, ensure_ascii=False), label="personal report")
    assert_no_forbidden_text(html, label="personal html")
    assert_no_forbidden_text(markdown, label="personal markdown")
    if "Cognitive Loop Personal Plugin Mode Lite" not in html:
        raise RuntimeError("HTML report missed product title.")
    if "Study Cards" not in html or "Quiz" not in html:
        raise RuntimeError("HTML report missed learning sections.")
    if "## Study Cards" not in markdown or "## Quiz" not in markdown:
        raise RuntimeError("Markdown report missed learning sections.")
    if report["privacy"]["read_only"] is not True:
        raise RuntimeError("Personal mode must stay read-only.")
    if report["privacy"]["source_text_included"] is not False:
        raise RuntimeError("Personal mode leaked source text flag.")
    if report["privacy"]["raw_diff_included"] is not False:
        raise RuntimeError("Personal mode leaked raw diff flag.")
    return report, html, markdown


def verify_success_modes() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-personal-mode-") as tmp:
        root = Path(tmp)
        fixtures = write_fixture(root)
        before_hash = sha256_file(fixtures["source"])
        reports = {
            "file": run_personal(root, ["--file", "src/learning_loop.py"])[0],
            "readme": run_personal(root, ["--readme", "README.md"])[0],
            "webpage": run_personal(
                root,
                [
                    "--web-url",
                    "https://example.com/learning",
                    "--web-title",
                    "Learning reference",
                    "--web-summary",
                    "A bounded public summary for a learning reference.",
                ],
            )[0],
            "diff_summary": run_personal(
                root,
                [
                    "--diff-summary",
                    "Learning adapter boundary changed with tests updated.",
                    "--changed-path",
                    "src/learning_loop.py",
                    "--changed-path",
                    "README.md",
                ],
            )[0],
        }
        after_hash = sha256_file(fixtures["source"])
        if before_hash != after_hash:
            raise RuntimeError("Personal mode modified the source file.")
        output_files = sorted((root / ".cognitive-loop" / "artifacts" / "personal-mode").glob("*"))
        kinds = sorted(report["target"]["kind"] for report in reports.values())
    return {
        "target_kinds": kinds,
        "artifact_file_count": len(output_files),
        "source_hash_unchanged": True,
        "html_markdown_created": True,
        "study_card_count": sum(len(report["outputs"]["study_cards"]) for report in reports.values()),
        "quiz_item_count": sum(len(report["outputs"]["quiz_items"]) for report in reports.values()),
        "privacy_flags": {
            "all_read_only": all(report["privacy"]["read_only"] for report in reports.values()),
            "source_text_included": any(report["privacy"]["source_text_included"] for report in reports.values()),
            "raw_diff_included": any(report["privacy"]["raw_diff_included"] for report in reports.values()),
            "real_model_keys_stored": any(report["privacy"]["real_model_keys_stored"] for report in reports.values()),
        },
    }


def verify_failure_modes() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-personal-mode-failures-") as tmp:
        root = Path(tmp)
        write_fixture(root)
        secret_file = root / "src" / "secret.py"
        secret_file.write_text("OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz\n", encoding="utf-8")
        missing = run_json(
            [sys.executable, str(CLI), "--root", str(root), "explain", "--file", "missing.py", "--json"],
            required=False,
        )
        secret = run_json(
            [sys.executable, str(CLI), "--root", str(root), "explain", "--file", "src/secret.py", "--json"],
            required=False,
        )
        raw_diff = run_json(
            [
                sys.executable,
                str(CLI),
                "--root",
                str(root),
                "explain",
                "--diff-summary",
                "diff --git a/src/learning_loop.py b/src/learning_loop.py",
                "--json",
            ],
            required=False,
        )
    if missing["returncode"] == 0:
        raise RuntimeError("Missing target should fail.")
    if secret["returncode"] == 0:
        raise RuntimeError("Secret target should fail.")
    if raw_diff["returncode"] == 0:
        raise RuntimeError("Raw diff summary should fail.")
    return {
        "missing_target_rejected": True,
        "secret_target_rejected": True,
        "raw_diff_rejected": True,
    }


def build_report() -> dict[str, Any]:
    success = verify_success_modes()
    failures = verify_failure_modes()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "version": "v0.3.31-alpha",
        "cli": "scripts/cognitive_loop_personal_mode.py",
        "artifact_schema": "cognitive-loop-personal-plugin-mode-v1",
        "success_modes": success,
        "failure_modes": failures,
        "acceptance": {
            "minimum_command": "python3 scripts/verify_cognitive_loop_personal_plugin_mode.py --check",
            "example_file_command": "python3 scripts/cognitive_loop_personal_mode.py explain --file README.md --html --markdown --json",
            "release_gate": "scripts/release_check.sh",
        },
        "privacy": {
            "read_only": True,
            "source_text_included": False,
            "raw_diff_included": False,
            "learner_answers_included": False,
            "agent_endpoint_included": False,
            "agent_metadata_included": False,
            "prompt_text_included": False,
            "real_model_keys_stored": False,
            "daemon_started": False,
            "model_called": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report()
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    assert_no_forbidden_text(text, label="verification report")
    if args.write:
        REPORT.write_text(text, encoding="utf-8")
        return 0
    if args.check:
        if not REPORT.exists():
            raise SystemExit("Personal Plugin Mode report is missing. Run: python3 scripts/verify_cognitive_loop_personal_plugin_mode.py --write")
        current = REPORT.read_text(encoding="utf-8")
        if current != text:
            raise SystemExit("Personal Plugin Mode report is stale. Run: python3 scripts/verify_cognitive_loop_personal_plugin_mode.py --write")
        print("ok    Cognitive Loop Personal Plugin Mode report is up to date")
        return 0
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
