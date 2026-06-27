#!/usr/bin/env python3
"""Generate privacy-safe published-image deployment evidence assets."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from localhost_diagnostics import redact_diagnostic  # noqa: E402

OUTPUT_DIR = ROOT / "platform" / "generated"
REPORT_PATH = OUTPUT_DIR / "study-anything-published-image-evidence.json"
MARKDOWN_PATH = OUTPUT_DIR / "study-anything-published-image-evidence.md"
ARCHIVE_PATH = OUTPUT_DIR / "study-anything-published-image-evidence.zip"
CHECKSUM_PATH = OUTPUT_DIR / "study-anything-published-image-evidence.sha256"
FIXTURE_DIR = ROOT / "fixtures" / "published-image-evidence"
ARCHIVE_ROOT = "study-anything-published-image-evidence"

SCHEMA_VERSION = "published-image-evidence-v1"
FIXTURE_SCHEMA_VERSION = "published-image-evidence-fixture-v1"
RELEASE_VERSION = "v0.3.29-alpha"
API_IMAGE = f"ghcr.io/jzvcpe-goat/study-anything/api:{RELEASE_VERSION}"
REQUIRED_PLATFORMS = ("linux/amd64", "linux/arm64")

FIXTURES = (
    "manifest-pass-local-pull-timeout",
    "cached-image-missing",
    "compose-up-timeout",
    "manifest-only-runtime-unverified",
    "manifest-missing-platform",
    "docker-images-failed",
    "ghcr-unavailable",
    "remote-smoke-pass",
    "remote-smoke-failed",
)

PUBLIC_ASSET_PATHS = (
    "README.md",
    "docs/adoption.md",
    "docs/self-hosting.md",
    "docs/platform-agent-integrations.md",
    "docs/ecosystem-submission.md",
    "docs/release-checklist.md",
    "docs/roadmap.md",
    "docs/published-image-evidence.md",
    "scripts/verify_published_image_launch.py",
    "scripts/generate_published_image_evidence.py",
    "scripts/verify_published_image_evidence.py",
    "scripts/diagnose_adoption.py",
    "scripts/launch_self_host.sh",
    "scripts/doctor.sh",
    "infra/compose/docker-compose.yml",
    "infra/compose/docker-compose.images.yml",
    "platform/ecosystem-submission.json",
    "platform/packs/codex/pack.json",
    "platform/packs/kimi/pack.json",
    "platform/packs/workbuddy/pack.json",
)

PRIVATE_ANSWER_SENTINEL = "Private " + "answer:"
PRIVATE_SOURCE_TEXT_SENTINEL = "Private " + "source text:"
PRIVATE_PLATFORM_CONTEXT_SENTINEL = "Private platform " + "browser/video context"
PRIVATE_TMP_PREFIX = "/private/" + "tmp/"
TMP_PREFIX = "/" + "tmp/"
FORBIDDEN_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"http://127\.0\.0\.1:8787[^\s\"']*"),
    re.compile(r"/Users/[^\\s\"']+"),
]
FORBIDDEN_LITERALS = [
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    PRIVATE_ANSWER_SENTINEL,
    PRIVATE_SOURCE_TEXT_SENTINEL,
    PRIVATE_PLATFORM_CONTEXT_SENTINEL,
    "raw_source_text=",
    "learner_answer=",
    "AGENT_ENDPOINT=http",
    "full_support_bundle_payload",
]


class PublishedImageEvidenceError(RuntimeError):
    """Readable published-image evidence generation failure."""


def format_cli_failure(exc: BaseException) -> str:
    diagnostic = redact_diagnostic(str(exc))
    return "\n".join(
        [
            f"generate_published_image_evidence failed: {diagnostic}",
            "",
            "Next steps:",
            "  1. Regenerate evidence assets: python3 scripts/generate_published_image_evidence.py",
            "  2. Verify generated assets: python3 scripts/generate_published_image_evidence.py --check",
            "  3. Verify the evidence report: python3 scripts/verify_published_image_evidence.py --check",
            "  4. Refresh the platform pack after evidence changes: python3 scripts/generate_platform_adoption_pack.py && python3 scripts/generate_platform_bundle_manifest.py",
            "  5. For local deployment diagnostics, run: python3 scripts/diagnose_adoption.py",
        ]
    )


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_no_leaks(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if PRIVATE_TMP_PREFIX in serialized or TMP_PREFIX in serialized:
        leaks.append("local temporary path")
    if leaks:
        raise PublishedImageEvidenceError(f"Published-image evidence leaked private data: {leaks}")


def require_file(relative_path: str) -> Path:
    path = ROOT / relative_path
    if not path.is_file():
        raise PublishedImageEvidenceError(f"Published-image evidence file is missing: {relative_path}")
    return path


def public_file_ref(relative_path: str) -> dict[str, Any]:
    path = require_file(relative_path)
    return {
        "path": relative_path,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def fixture_payload(fixture_id: str) -> dict[str, Any]:
    mapping: dict[str, dict[str, Any]] = {
        "manifest-pass-local-pull-timeout": {
            "classification": "local_pull_timeout_with_valid_release_evidence",
            "release_gate": "acceptable_with_manifest_and_ci",
            "manifest": {"status": "ok", "platforms": list(REQUIRED_PLATFORMS)},
            "docker_images_workflow": {"status": "success"},
            "local_smoke": {"status": "blocked_by_local_ghcr_pull"},
            "remote_smoke": {"status": "not_required"},
            "operator_next_step": "Verify manifest platforms and docker-images success, then retry pull from a faster network if needed.",
        },
        "cached-image-missing": {
            "classification": "cached_image_missing",
            "release_gate": "needs_pull_or_manifest_only_recheck",
            "manifest": {"status": "ok", "platforms": list(REQUIRED_PLATFORMS)},
            "docker_images_workflow": {"status": "success"},
            "local_smoke": {"status": "cached_image_missing"},
            "remote_smoke": {"status": "not_attempted"},
            "operator_next_step": "Run docker pull or manifest-only verification; cached-only mode cannot prove runtime without the local image.",
        },
        "compose-up-timeout": {
            "classification": "compose_up_timeout",
            "release_gate": "needs_independent_recheck",
            "manifest": {"status": "ok", "platforms": list(REQUIRED_PLATFORMS)},
            "docker_images_workflow": {"status": "success"},
            "local_smoke": {"status": "compose_up_timeout"},
            "remote_smoke": {"status": "not_attempted"},
            "operator_next_step": "Treat as local Docker startup or implicit pull slowness; pair manifest evidence with CI and retry from another runner.",
        },
        "manifest-only-runtime-unverified": {
            "classification": "manifest_available_runtime_unverified",
            "release_gate": "acceptable_only_with_successful_ci_and_release_check",
            "manifest": {"status": "ok", "platforms": list(REQUIRED_PLATFORMS)},
            "docker_images_workflow": {"status": "success"},
            "local_smoke": {"status": "manifest_available_runtime_unverified"},
            "remote_smoke": {"status": "not_attempted"},
            "operator_next_step": "Use this only when local runtime smoke is impossible; it proves distribution, not container behavior.",
        },
        "manifest-missing-platform": {
            "classification": "published_image_platform_gap",
            "release_gate": "block_release_claim",
            "manifest": {"status": "incomplete", "platforms": ["linux/amd64"]},
            "docker_images_workflow": {"status": "success"},
            "local_smoke": {"status": "not_attempted"},
            "remote_smoke": {"status": "not_attempted"},
            "operator_next_step": "Rebuild and publish the missing platform before telling adopters to use the image.",
        },
        "docker-images-failed": {
            "classification": "ci_image_publish_failed",
            "release_gate": "block_release_claim",
            "manifest": {"status": "unknown", "platforms": []},
            "docker_images_workflow": {"status": "failure"},
            "local_smoke": {"status": "not_attempted"},
            "remote_smoke": {"status": "not_attempted"},
            "operator_next_step": "Fix docker-images CI and publish a fresh tag before external handoff.",
        },
        "ghcr-unavailable": {
            "classification": "registry_or_network_unavailable",
            "release_gate": "needs_independent_recheck",
            "manifest": {"status": "unavailable", "platforms": []},
            "docker_images_workflow": {"status": "unknown"},
            "local_smoke": {"status": "not_attempted"},
            "remote_smoke": {"status": "not_attempted"},
            "operator_next_step": "Check GitHub Actions and retry manifest inspection from another network.",
        },
        "remote-smoke-pass": {
            "classification": "published_image_ready",
            "release_gate": "pass",
            "manifest": {"status": "ok", "platforms": list(REQUIRED_PLATFORMS)},
            "docker_images_workflow": {"status": "success"},
            "local_smoke": {"status": "ok"},
            "remote_smoke": {"status": "ok"},
            "operator_next_step": "Attach this evidence with the release notes and platform adoption pack.",
        },
        "remote-smoke-failed": {
            "classification": "published_image_runtime_failed",
            "release_gate": "block_release_claim",
            "manifest": {"status": "ok", "platforms": list(REQUIRED_PLATFORMS)},
            "docker_images_workflow": {"status": "success"},
            "local_smoke": {"status": "ok"},
            "remote_smoke": {"status": "failed"},
            "operator_next_step": "Treat manifest and CI as insufficient; inspect container logs and health/version output.",
        },
    }
    item = mapping[fixture_id]
    payload = {
        "schema_version": FIXTURE_SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "fixture_id": fixture_id,
        "classification": item["classification"],
        "release_gate": item["release_gate"],
        "signals": {
            "tag": RELEASE_VERSION,
            "api_image": API_IMAGE,
            "manifest": item["manifest"],
            "docker_images_workflow": item["docker_images_workflow"],
            "local_smoke": item["local_smoke"],
            "remote_smoke": item["remote_smoke"],
        },
        "operator_next_step": item["operator_next_step"],
        "privacy": {
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_prompts_included": False,
            "agent_endpoint_secrets_included": False,
            "real_model_keys_included": False,
            "support_bundle_private_payload_included": False,
            "local_absolute_paths_included": False,
            "automatic_upload": False,
        },
    }
    assert_no_leaks(payload)
    return payload


def fixture_refs() -> list[dict[str, Any]]:
    return [
        {"fixture_id": fixture_id, **public_file_ref(f"fixtures/published-image-evidence/{fixture_id}.json")}
        for fixture_id in FIXTURES
    ]


def build_report(include_archive_metadata: bool = False, archive: bytes | None = None) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "purpose": (
            "Give external adopters and platform maintainers a deterministic way to decide "
            "whether a published Study Anything image is ready, blocked, or only limited by "
            "local Docker/GHCR pull conditions."
        ),
        "release_identity": {
            "tag": RELEASE_VERSION,
            "source_ref": "main",
            "api_image": API_IMAGE,
            "release_view_command": f"gh release view {RELEASE_VERSION}",
        },
        "manifest_evidence": {
            "command": f"docker manifest inspect {API_IMAGE}",
            "required_platforms": list(REQUIRED_PLATFORMS),
            "pass_condition": "all required platforms are present",
            "missing_platform_classification": "published_image_platform_gap",
        },
        "ci_evidence": {
            "required_workflows": [
                "docker-images on main",
                f"docker-images on {RELEASE_VERSION}",
            ],
            "verification_commands": [
                "gh run list --workflow docker-images --branch main --limit 1",
                f"gh run list --workflow docker-images --branch {RELEASE_VERSION} --limit 1",
            ],
            "failure_classification": "ci_image_publish_failed",
        },
        "local_smoke_evidence": {
            "command": (
                f"python3 scripts/verify_published_image_launch.py --tag {RELEASE_VERSION} "
                "--pull-timeout-seconds 600 --allow-pull-timeout-report"
            ),
            "success_status": "ok",
            "timeout_status": "blocked_by_local_ghcr_pull",
            "cached_only_missing_status": "cached_image_missing",
            "compose_timeout_status": "compose_up_timeout",
            "manifest_only_status": "manifest_available_runtime_unverified",
            "timeout_is_acceptable_only_when": [
                "manifest inspection shows linux/amd64 and linux/arm64",
                "docker-images workflow succeeded for the release tag",
                "release_check.sh and external adoption proof passed before tagging",
            ],
        },
        "remote_replay": {
            "optional": True,
            "purpose": "Run the same published-image smoke from a network or CI runner with reliable GHCR pulls.",
            "commands": [
                f"python3 scripts/verify_published_image_launch.py --tag {RELEASE_VERSION} --skip-pull",
                f"python3 scripts/verify_published_image_launch.py --tag {RELEASE_VERSION} --manifest-only",
                f"python3 scripts/verify_published_image_launch.py --tag {RELEASE_VERSION} --pull-timeout-seconds 600 --allow-pull-timeout-report",
            ],
            "pass_classification": "published_image_ready",
            "failure_classification": "published_image_runtime_failed",
        },
        "classification_matrix": [
            {
                "classification": "published_image_ready",
                "release_gate": "pass",
                "meaning": "Manifest, CI, and local or remote smoke all passed.",
            },
            {
                "classification": "local_pull_timeout_with_valid_release_evidence",
                "release_gate": "acceptable_with_manifest_and_ci",
                "meaning": "Local Docker/GHCR pull timed out, but independent manifest and CI evidence are valid.",
            },
            {
                "classification": "cached_image_missing",
                "release_gate": "needs_pull_or_manifest_only_recheck",
                "meaning": "Cached-only verification was requested, but the local machine does not have the image.",
            },
            {
                "classification": "compose_up_timeout",
                "release_gate": "needs_independent_recheck",
                "meaning": "docker compose up did not finish within the bounded verifier timeout.",
            },
            {
                "classification": "manifest_available_runtime_unverified",
                "release_gate": "acceptable_only_with_successful_ci_and_release_check",
                "meaning": "Manifest platforms are available, but no local runtime smoke was executed.",
            },
            {
                "classification": "published_image_platform_gap",
                "release_gate": "block_release_claim",
                "meaning": "The manifest is missing linux/amd64 or linux/arm64.",
            },
            {
                "classification": "ci_image_publish_failed",
                "release_gate": "block_release_claim",
                "meaning": "The docker-images workflow failed or did not publish the expected tag.",
            },
            {
                "classification": "registry_or_network_unavailable",
                "release_gate": "needs_independent_recheck",
                "meaning": "GHCR or local network access failed before platform status could be proven.",
            },
            {
                "classification": "published_image_runtime_failed",
                "release_gate": "block_release_claim",
                "meaning": "Image exists, but the container failed health/version or full API smoke.",
            },
        ],
        "fixture_refs": fixture_refs(),
        "public_asset_refs": [public_file_ref(path) for path in PUBLIC_ASSET_PATHS],
        "privacy_assertions": {
            "raw_source_text_in_report": False,
            "learner_answers_in_report": False,
            "agent_prompts_in_report": False,
            "agent_endpoint_secrets_in_report": False,
            "real_model_keys_in_report": False,
            "support_bundle_private_payload_in_report": False,
            "local_absolute_paths_in_report": False,
            "automatic_upload": False,
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_published_image_evidence.py --check",
            "generate_command": "python3 scripts/generate_published_image_evidence.py --check",
            "pack_command": (
                "python3 scripts/verify_published_image_evidence.py "
                "--pack platform/generated/study-anything-platform-adoption-pack.zip"
            ),
            "release_gate": "scripts/release_check.sh",
        },
    }
    if include_archive_metadata:
        if archive is None:
            raise PublishedImageEvidenceError("archive bytes are required for archive metadata")
        report["archive"] = {
            "path": "platform/generated/study-anything-published-image-evidence.zip",
            "sha256_path": "platform/generated/study-anything-published-image-evidence.sha256",
            "bytes": len(archive),
            "sha256": sha256_bytes(archive),
            "archive_root": ARCHIVE_ROOT,
        }
    assert_no_leaks(report)
    return report


def markdown_report(report: dict[str, Any]) -> str:
    commands = "\n".join(f"- `{command}`" for command in report["local_smoke_evidence"]["timeout_is_acceptable_only_when"])
    fixtures = "\n".join(
        f"- `{item['fixture_id']}`: `{item['sha256']}`" for item in report["fixture_refs"]
    )
    matrix = "\n".join(
        f"- `{item['classification']}` -> `{item['release_gate']}`: {item['meaning']}"
        for item in report["classification_matrix"]
    )
    archive = report.get("archive") or {}
    archive_line = (
        f"- Archive: `{archive.get('path')}` sha256 `{archive.get('sha256')}`"
        if archive
        else "- Archive: generated during packaging"
    )
    return f"""# Study Anything Published Image Evidence

Schema: `{report['schema_version']}`
Version: `{report['version']}`
Status: `{report['status']}`

This evidence bundle helps an external operator decide whether published GHCR
images are deployable or whether a failure belongs to the local pull path,
registry access, CI publishing, manifest platforms, or runtime health.

## Archive

{archive_line}

## Manifest And Smoke

- API image: `{report['release_identity']['api_image']}`
- Manifest: `{report['manifest_evidence']['command']}`
- Local smoke: `{report['local_smoke_evidence']['command']}`
- Timeout status: `{report['local_smoke_evidence']['timeout_status']}`

## Local Pull Timeout Acceptance

{commands}

## Classification Matrix

{matrix}

## Fixture Hashes

{fixtures}

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
"""


def archive_readme() -> str:
    return f"""# Study Anything Published Image Evidence

Version: {RELEASE_VERSION}
Schema: {SCHEMA_VERSION}

Run `python3 scripts/verify_published_image_evidence.py --check` in the repo, or
`python3 scripts/verify_published_image_evidence.py --pack platform/generated/study-anything-platform-adoption-pack.zip`
against the adoption pack.
"""


def archive_bytes(base_report: dict[str, Any], markdown: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        records: list[tuple[str, bytes]] = [
            (f"{ARCHIVE_ROOT}/EVIDENCE_README.md", archive_readme().encode("utf-8")),
            (f"{ARCHIVE_ROOT}/manifest.json", dump_json(base_report).encode("utf-8")),
            (f"{ARCHIVE_ROOT}/study-anything-published-image-evidence.md", markdown.encode("utf-8")),
        ]
        for fixture_id in FIXTURES:
            records.append(
                (
                    f"{ARCHIVE_ROOT}/fixtures/published-image-evidence/{fixture_id}.json",
                    dump_json(fixture_payload(fixture_id)).encode("utf-8"),
                )
            )
        for relative_path in PUBLIC_ASSET_PATHS:
            records.append((f"{ARCHIVE_ROOT}/{relative_path}", require_file(relative_path).read_bytes()))
        for name, content in sorted(records, key=lambda item: item[0]):
            info = zipfile.ZipInfo(name)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
    return buffer.getvalue()


def build_outputs() -> tuple[str, str, bytes, str]:
    base_report = build_report()
    base_markdown = markdown_report(base_report)
    archive = archive_bytes(base_report, base_markdown)
    report = build_report(include_archive_metadata=True, archive=archive)
    markdown = markdown_report(report)
    checksum = f"{sha256_bytes(archive)}  {ARCHIVE_PATH.name}\n"
    return dump_json(report), markdown, archive, checksum


def write_outputs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for fixture_id in FIXTURES:
        (FIXTURE_DIR / f"{fixture_id}.json").write_text(
            dump_json(fixture_payload(fixture_id)),
            encoding="utf-8",
        )
    report_text, markdown, archive, checksum = build_outputs()
    REPORT_PATH.write_text(report_text, encoding="utf-8")
    MARKDOWN_PATH.write_text(markdown, encoding="utf-8")
    ARCHIVE_PATH.write_bytes(archive)
    CHECKSUM_PATH.write_text(checksum, encoding="utf-8")
    print(f"wrote {REPORT_PATH.relative_to(ROOT)}")
    print(f"wrote {MARKDOWN_PATH.relative_to(ROOT)}")
    print(f"wrote {ARCHIVE_PATH.relative_to(ROOT)}")
    print(f"wrote {CHECKSUM_PATH.relative_to(ROOT)}")
    print(f"wrote {FIXTURE_DIR.relative_to(ROOT)}/*.json")


def check_outputs() -> None:
    expected_fixtures = {
        FIXTURE_DIR / f"{fixture_id}.json": dump_json(fixture_payload(fixture_id))
        for fixture_id in FIXTURES
    }
    report_text, markdown, archive, checksum = build_outputs()
    expected = {
        REPORT_PATH: report_text,
        MARKDOWN_PATH: markdown,
        ARCHIVE_PATH: archive,
        CHECKSUM_PATH: checksum,
        **expected_fixtures,
    }
    missing: list[str] = []
    stale: list[str] = []
    for path, content in expected.items():
        if not path.exists():
            missing.append(str(path.relative_to(ROOT)))
            continue
        if isinstance(content, bytes):
            if path.read_bytes() != content:
                stale.append(str(path.relative_to(ROOT)))
        elif path.read_text(encoding="utf-8") != content:
            stale.append(str(path.relative_to(ROOT)))
    if missing or stale:
        raise PublishedImageEvidenceError(
            "Published-image evidence assets are stale. Run "
            "`python3 scripts/generate_published_image_evidence.py`. "
            f"missing={missing} stale={stale}"
        )
    print("ok    generated published-image evidence assets are up to date")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check_outputs()
    else:
        write_outputs()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(format_cli_failure(exc), file=sys.stderr)
        sys.exit(1)
