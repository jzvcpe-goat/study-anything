#!/usr/bin/env python3
"""Bootstrap Study Anything adoption from public GitHub Release assets.

This is the operator-friendly entrypoint for external platform agents. It
reuses the stricter release-asset verifier, then adds platform import preflight,
recovery commands, and a redacted adoption transcript.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VERIFIER_PATH = ROOT / "scripts" / "verify_release_asset_adoption.py"
SCHEMA_VERSION = "release-asset-bootstrap-transcript-v1"
DEFAULT_REPO = "jzvcpe-goat/study-anything"
DEFAULT_TAG = "v0.3.30-alpha"

PLATFORM_PACKS = {
    "kimi": {
        "display": "Kimi Work / Kimi-compatible Agent",
        "entrypoints": [
            "platform/generated/study-anything-openai-tools.json",
            "platform/generated/study-anything-platform-openapi.json",
            "platform/packs/kimi/README.md",
        ],
    },
    "codex": {
        "display": "Codex Skill / terminal Agent",
        "entrypoints": [
            "skills/study-anything/SKILL.md",
            "platform/packs/codex/README.md",
            "scripts/study_anything_cli.py",
        ],
    },
    "workbuddy": {
        "display": "WorkBuddy-style HTTP workspace",
        "entrypoints": [
            "platform/generated/study-anything-platform-openapi.json",
            "platform/generated/study-anything-tool-catalog.md",
            "platform/packs/workbuddy/README.md",
        ],
    },
}

RECOVERY_PLAN = {
    "release_asset_missing": [
        "Open the GitHub release page and confirm all required public zip assets are attached.",
        "Run `python3 scripts/bootstrap_from_release.py --tag <tag> --runtime metadata-only` after assets are uploaded.",
    ],
    "release_asset_digest_mismatch": [
        "Delete the downloaded asset directory and re-run the bootstrap command.",
        "If the mismatch repeats, recreate the GitHub release asset from the matching main commit.",
    ],
    "release_asset_pack_corrupted": [
        "Re-download `study-anything-platform-adoption-pack.zip` from the release page.",
        "Run `python3 scripts/verify_release_asset_adoption.py --tag <tag> --runtime metadata-only` for the lower-level error.",
    ],
    "release_asset_published_evidence_missing": [
        "Regenerate published-image evidence and platform adoption pack before publishing the release.",
        "Run `python3 scripts/generate_published_image_evidence.py --check` and `python3 scripts/generate_platform_adoption_pack.py --check`.",
    ],
    "release_asset_network_unavailable": [
        "Retry from another network or CI runner that can reach GitHub release assets.",
        "Use an already downloaded asset directory with `--asset-dir <dir>` if the files were mirrored safely.",
    ],
    "tool_manifest_invalid": [
        "Regenerate platform tools and adoption pack.",
        "Run `python3 scripts/generate_platform_agent_assets.py --check` and `python3 scripts/generate_platform_adoption_pack.py --check`.",
    ],
    "local_api_unavailable": [
        "Run `./scripts/launch_skill_mode.sh` for local Skill Mode.",
        "For Docker, run `./scripts/launch_self_host.sh` and then `API_BASE=http://127.0.0.1:8000 python3 scripts/verify_full_api_flow.py`.",
    ],
    "published_image_unavailable": [
        "Run `docker manifest inspect ghcr.io/jzvcpe-goat/study-anything/api:<tag>`.",
        "If local pulls are slow, run `python3 scripts/verify_published_image_launch.py --tag <tag> --manifest-only`.",
    ],
    "non_ascii_path_risk": [
        "Prefer an ASCII-only checkout path for local Docker source builds.",
        "Use published images or Skill Mode when the workspace path contains non-ASCII characters.",
    ],
    "bootstrap_failed": [
        "Run the lower-level verifier with `python3 scripts/verify_release_asset_adoption.py --tag <tag> --runtime metadata-only`.",
        "Attach the redacted bootstrap transcript to a GitHub issue if the failure repeats.",
    ],
}

FORBIDDEN_LITERALS = [
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "Private answer:",
    "Private source text:",
    "raw_source_text=",
    "learner_answer=",
    "AGENT_ENDPOINT=http",
    "full_support_bundle_payload",
]


class BootstrapError(RuntimeError):
    """Readable bootstrap failure."""


def load_release_verifier() -> Any:
    spec = importlib.util.spec_from_file_location("study_anything_release_asset_verifier", VERIFIER_PATH)
    if spec is None or spec.loader is None:
        raise BootstrapError("Could not load release asset verifier.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise BootstrapError(f"Cannot read JSON: {path.name}") from exc
    if not isinstance(payload, dict):
        raise BootstrapError(f"JSON object expected: {path.name}")
    return payload


def tool_names_from_openai_tools(path: Path) -> set[str]:
    try:
        tools = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise BootstrapError("OpenAI tool manifest is not readable JSON.") from exc
    if not isinstance(tools, list):
        raise BootstrapError("OpenAI tool manifest must be a list.")
    names: set[str] = set()
    malformed: list[str] = []
    for item in tools:
        function = item.get("function") if isinstance(item, dict) else None
        if not isinstance(function, dict):
            malformed.append("<missing function>")
            continue
        name = str(function.get("name") or "")
        parameters = function.get("parameters")
        if item.get("type") != "function" or not name.startswith("study_anything_") or not isinstance(parameters, dict):
            malformed.append(name or "<unnamed>")
        names.add(name)
    if malformed:
        raise BootstrapError(f"Malformed OpenAI tool definitions: {malformed[:5]}")
    return names


def operation_ids_from_openapi(path: Path) -> tuple[set[str], int]:
    openapi = read_json(path)
    if openapi.get("openapi") != "3.1.0":
        raise BootstrapError("OpenAPI manifest must be version 3.1.0.")
    if (openapi.get("components") or {}).get("securitySchemes"):
        raise BootstrapError("OpenAPI manifest must not declare API-key security schemes.")
    operations: set[str] = set()
    paths = openapi.get("paths") or {}
    if not isinstance(paths, dict):
        raise BootstrapError("OpenAPI paths must be an object.")
    for methods in paths.values():
        if not isinstance(methods, dict):
            continue
        for operation in methods.values():
            if isinstance(operation, dict) and operation.get("operationId"):
                operations.add(str(operation["operationId"]))
    return operations, len(paths)


def platform_import_preflight(pack_root: Path, pack: dict[str, Any]) -> dict[str, Any]:
    required_tools = set(str(item) for item in pack.get("required_tool_names", []))
    if not required_tools:
        raise BootstrapError("Adoption pack manifest has no required tool names.")
    openai_names = tool_names_from_openai_tools(pack_root / "platform/generated/study-anything-openai-tools.json")
    openapi_operations, openapi_path_count = operation_ids_from_openapi(
        pack_root / "platform/generated/study-anything-platform-openapi.json"
    )
    missing_openai = sorted(required_tools - openai_names)
    missing_openapi = sorted(required_tools - openapi_operations)
    if missing_openai or missing_openapi:
        raise BootstrapError(f"Tool manifest invalid: openai={missing_openai} openapi={missing_openapi}")

    platform_status: dict[str, Any] = {}
    for platform_id, config in PLATFORM_PACKS.items():
        missing = [path for path in config["entrypoints"] if not (pack_root / path).is_file()]
        platform_status[platform_id] = {
            "display": config["display"],
            "status": "ready" if not missing else "missing_entrypoint",
            "entrypoints": config["entrypoints"],
            "missing": missing,
        }
    if any(item["missing"] for item in platform_status.values()):
        raise BootstrapError("One or more platform pack entrypoints are missing.")

    return {
        "status": "ready",
        "openai_tool_count": len(openai_names),
        "openapi_path_count": openapi_path_count,
        "required_tool_count": len(required_tools),
        "required_tools_present": sorted(required_tools),
        "platforms": platform_status,
        "security": {
            "openapi_api_key_security_schemes": False,
            "real_model_keys_stored_by_study_anything": False,
        },
    }


def recovery_matrix() -> dict[str, list[str]]:
    return {key: list(value) for key, value in RECOVERY_PLAN.items()}


def operator_steps(tag: str, runtime: str) -> list[dict[str, str]]:
    return [
        {
            "step_id": "download_release_assets",
            "operator_action": f"Download Study Anything release assets for {tag}.",
            "acceptance": "All required zip assets are present and sha256 digests match GitHub metadata.",
        },
        {
            "step_id": "import_platform_tools",
            "operator_action": "Import OpenAI tools or OpenAPI from the adoption pack into Kimi, Codex, WorkBuddy, or another platform Agent.",
            "acceptance": "Tool counts match the adoption pack manifest and no API-key security scheme is declared.",
        },
        {
            "step_id": "start_runtime",
            "operator_action": f"Use the selected runtime path: {runtime}.",
            "acceptance": "Metadata-only skips runtime; Skill Mode or published image emits a bounded verifier result.",
        },
        {
            "step_id": "run_learning_tool",
            "operator_action": "Call Study Anything platform tools from the host Agent while keeping real model credentials inside the user's own Agent.",
            "acceptance": "Study Anything returns source-bound learning state and redacted eval/audit evidence.",
        },
    ]


def command_set(tag: str) -> dict[str, str]:
    return {
        "bootstrap_metadata_only": f"python3 scripts/bootstrap_from_release.py --tag {tag} --runtime metadata-only",
        "bootstrap_skill_mode": f"python3 scripts/bootstrap_from_release.py --tag {tag} --runtime skill-mode",
        "bootstrap_published_image": f"python3 scripts/bootstrap_from_release.py --tag {tag} --runtime published-image",
        "lower_level_release_asset_verifier": f"python3 scripts/verify_release_asset_adoption.py --tag {tag} --runtime metadata-only",
        "platform_agent_release_replay": f"python3 scripts/replay_platform_agent_from_release.py --tag {tag} --platform kimi --runtime metadata-only",
        "published_image_manifest_only": f"python3 scripts/verify_published_image_launch.py --tag {tag} --manifest-only",
    }


def assert_redacted(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    if re.search(r"/Users/[^\s\"']+", serialized):
        leaks.append("local absolute path")
    if leaks:
        raise BootstrapError(f"Bootstrap transcript leaked private data: {leaks}")


def sanitize_error(message: str) -> str:
    first_line = (message or "Bootstrap failed.").splitlines()[0]
    first_line = re.sub(r"/Users/[^\s\"']+", "<local-path>", first_line)
    first_line = re.sub(r"/private/var/folders/[^\s\"']+", "<temp-path>", first_line)
    first_line = re.sub(r"/var/folders/[^\s\"']+", "<temp-path>", first_line)
    return first_line[:800]


def classify_error(message: str) -> str:
    lowered = message.lower()
    if "missing required assets" in lowered:
        return "release_asset_missing"
    if "digest mismatch" in lowered:
        return "release_asset_digest_mismatch"
    if "zip is corrupted" in lowered or "badzipfile" in lowered:
        return "release_asset_pack_corrupted"
    if "published image evidence" in lowered:
        return "release_asset_published_evidence_missing"
    if "could not fetch release metadata" in lowered or "could not download" in lowered:
        return "release_asset_network_unavailable"
    if "tool manifest" in lowered or "openapi" in lowered or "openai tool" in lowered:
        return "tool_manifest_invalid"
    if "api_unreachable" in lowered or "localhost" in lowered:
        return "local_api_unavailable"
    if "published image manifest" in lowered or "docker manifest" in lowered:
        return "published_image_unavailable"
    return "bootstrap_failed"


def build_failure_transcript(
    *,
    args: argparse.Namespace,
    classification: str,
    diagnostic: str,
    status: str = "blocked",
) -> dict[str, Any]:
    transcript = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "classification": classification,
        "tag": args.tag,
        "repo": args.repo,
        "diagnostic": sanitize_error(diagnostic),
        "recovery_plan": {classification: RECOVERY_PLAN.get(classification, RECOVERY_PLAN["bootstrap_failed"])},
        "commands": command_set(args.tag),
        "privacy": privacy_assertions(),
    }
    assert_redacted(transcript)
    return transcript


def privacy_assertions() -> dict[str, bool]:
    return {
        "raw_source_text_included": False,
        "learner_answers_included": False,
        "agent_prompts_included": False,
        "agent_endpoint_secrets_included": False,
        "real_model_keys_included": False,
        "support_bundle_private_payload_included": False,
        "local_absolute_paths_included": False,
        "automatic_upload": False,
    }


def build_success_transcript(
    *,
    args: argparse.Namespace,
    proof: dict[str, Any],
    preflight: dict[str, Any],
    elapsed: float,
) -> dict[str, Any]:
    pack = proof.get("pack") or {}
    assets = proof.get("assets") or {}
    transcript = {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "classification": "release_asset_bootstrap_ready",
        "tag": args.tag,
        "repo": args.repo,
        "release_url": proof.get("release_url") or f"https://github.com/{args.repo}/releases/tag/{args.tag}",
        "elapsed_seconds": round(elapsed, 3),
        "runtime": {
            "requested": args.runtime,
            "proof_status": proof.get("status"),
            "proof_classification": proof.get("classification"),
            "runtime_result": (proof.get("verifiers") or {}).get("runtime"),
        },
        "release_assets": {
            "required_assets": sorted(assets),
            "asset_count": len(assets),
            "github_digest_verified_count": sum(1 for item in assets.values() if item.get("github_digest_verified")),
        },
        "adoption_pack": {
            "schema_version": pack.get("schema_version"),
            "version": pack.get("version"),
            "file_count": pack.get("file_count"),
            "tool_count": pack.get("tool_count"),
            "no_frontend_required": pack.get("no_frontend_required"),
            "real_model_keys_stored_by_study_anything": pack.get("real_model_keys_stored_by_study_anything"),
            "published_image_evidence_schema": pack.get("published_image_evidence_schema"),
        },
        "platform_import_preflight": preflight,
        "operator_steps": operator_steps(args.tag, args.runtime),
        "commands": command_set(args.tag),
        "recovery_plan": recovery_matrix(),
        "privacy": privacy_assertions(),
        "acceptance": {
            "release_asset_proof_schema": "release-asset-adoption-proof-v1",
            "bootstrap_schema": SCHEMA_VERSION,
            "safe_for_external_platform_agent": True,
        },
    }
    assert_redacted(transcript)
    return transcript


def make_verifier_namespace(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        repo=args.repo,
        tag=args.tag,
        asset_dir=args.asset_dir,
        release_json=args.release_json,
        fixture=args.fixture,
        runtime=args.runtime,
        skip_pull=args.skip_pull,
        expect_failure=args.expect_failure,
        keep=args.keep,
        include_asset_dir=False,
        python=args.python,
        timeout_seconds=args.timeout_seconds,
        network_timeout_seconds=args.network_timeout_seconds,
        pull_timeout_seconds=args.pull_timeout_seconds,
    )


def run_bootstrap(args: argparse.Namespace) -> dict[str, Any]:
    verifier = load_release_verifier()
    fixture_classification = verifier.classification_from_fixture(make_verifier_namespace(args))
    if fixture_classification and args.expect_failure and fixture_classification != "release_asset_adoption_ready":
        return build_failure_transcript(
            args=args,
            classification=str(fixture_classification),
            diagnostic=f"Expected failure fixture: {fixture_classification}",
            status="expected_failure",
        )

    started = time.monotonic()
    work_root = Path(tempfile.mkdtemp(prefix="study-anything-release-bootstrap-"))
    asset_dir = Path(args.asset_dir).resolve() if args.asset_dir else work_root / "assets"
    try:
        verifier_args = make_verifier_namespace(args)
        release = verifier.load_release_metadata(verifier_args)
        assets = verifier.materialize_assets(verifier_args, release, asset_dir)
        pack_root = verifier.extract_adoption_pack(asset_dir, work_root)
        pack = verifier.validate_pack(pack_root, asset_dir)
        preflight = platform_import_preflight(pack_root, read_json(pack_root / "manifest.json"))
        verifiers = verifier.run_pack_verifiers(pack_root, asset_dir, verifier_args)
        proof = verifier.build_proof(
            args=verifier_args,
            release=release,
            assets=assets,
            pack=pack,
            verifiers=verifiers,
            elapsed=time.monotonic() - started,
            asset_dir=asset_dir,
        )
        return build_success_transcript(
            args=args,
            proof=proof,
            preflight=preflight,
            elapsed=time.monotonic() - started,
        )
    finally:
        if not args.keep and not args.asset_dir:
            shutil.rmtree(work_root, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--tag", default=DEFAULT_TAG)
    parser.add_argument("--asset-dir")
    parser.add_argument("--release-json")
    parser.add_argument("--fixture")
    parser.add_argument("--runtime", choices=["metadata-only", "published-image", "skill-mode"], default="metadata-only")
    parser.add_argument("--skip-pull", action="store_true")
    parser.add_argument("--expect-failure", action="store_true")
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--python")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--network-timeout-seconds", type=int, default=60)
    parser.add_argument("--pull-timeout-seconds", type=int, default=600)
    args = parser.parse_args()

    try:
        transcript = run_bootstrap(args)
        print(json.dumps(transcript, ensure_ascii=False, sort_keys=True))
    except Exception as exc:
        classification = classify_error(str(exc))
        transcript = build_failure_transcript(
            args=args,
            classification=classification,
            diagnostic=str(exc),
            status="expected_failure" if args.expect_failure else "blocked",
        )
        print(json.dumps(transcript, ensure_ascii=False, sort_keys=True))
        if not args.expect_failure:
            sys.exit(1)


if __name__ == "__main__":
    main()
