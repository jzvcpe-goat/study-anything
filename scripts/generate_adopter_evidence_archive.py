#!/usr/bin/env python3
"""Generate a public adopter evidence archive and maintainer handoff pack."""

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


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "platform" / "generated"
REPORT_PATH = OUTPUT_DIR / "study-anything-adopter-evidence-archive.json"
MARKDOWN_PATH = OUTPUT_DIR / "study-anything-adopter-evidence-archive.md"
ARCHIVE_PATH = OUTPUT_DIR / "study-anything-adopter-evidence-archive.zip"
CHECKSUM_PATH = OUTPUT_DIR / "study-anything-adopter-evidence-archive.sha256"
FIXTURE_DIR = ROOT / "fixtures" / "adopter-evidence-archive"
ARCHIVE_ROOT = "study-anything-adopter-evidence-archive"

SCHEMA_VERSION = "adopter-evidence-archive-v1"
FIXTURE_SCHEMA_VERSION = "adopter-evidence-fixture-v1"
RELEASE_VERSION = "v0.3.26-alpha"
PUBLIC_STATUS_SCHEMA_VERSION = "public-support-status-v1"
PUBLIC_DASHBOARD_SCHEMA_VERSION = "public-maintainer-dashboard-v1"
ADOPTION_PACK_SCHEMA_VERSION = "study-anything-platform-adoption-pack-v1"
ECOSYSTEM_SUBMISSION_SCHEMA_VERSION = "ecosystem-submission-v1"
PUBLISHED_IMAGE_EVIDENCE_SCHEMA_VERSION = "published-image-evidence-v1"
RELEASE_ASSET_ADOPTION_SCHEMA_VERSION = "release-asset-adoption-v1"

FIXTURES = (
    "successful-release",
    "local-ghcr-pull-timeout",
    "needs-repro-issue",
    "release-blocker",
    "platform-blocked",
    "resolved-support-case",
)

PUBLIC_ASSET_PATHS = (
    "README.md",
    "docs/adoption.md",
    "docs/adopter-evidence-archive.md",
    "docs/published-image-evidence.md",
    "docs/platform-agent-integrations.md",
    "docs/support-desk.md",
    "docs/adopter-onboarding.md",
    "docs/maintainer-rotation.md",
    "docs/ecosystem-submission.md",
    "docs/release-checklist.md",
    "docs/roadmap.md",
    "docs/release-notes/v0.3.26-alpha.md",
    "platform/ecosystem-submission.json",
    "platform/generated/study-anything-public-support-status.json",
    "platform/generated/study-anything-public-maintainer-dashboard.json",
    "platform/generated/study-anything-public-maintainer-dashboard.md",
    "platform/generated/study-anything-published-image-evidence.json",
    "platform/generated/study-anything-published-image-evidence.md",
    "platform/generated/study-anything-published-image-evidence.zip",
    "platform/generated/study-anything-published-image-evidence.sha256",
    "platform/generated/study-anything-release-asset-adoption.json",
    "platform/generated/study-anything-release-asset-adoption.md",
    "platform/generated/study-anything-release-asset-adoption.zip",
    "platform/generated/study-anything-release-asset-adoption.sha256",
    "platform/generated/study-anything-operator-drill-transcript.json",
    "platform/generated/study-anything-platform-manual-submission-rehearsal.json",
    "platform/packs/codex/pack.json",
    "platform/packs/kimi/pack.json",
    "platform/packs/workbuddy/pack.json",
)

FORBIDDEN_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"http://127\.0\.0\.1:8787[^\s\"']*"),
]
FORBIDDEN_LITERALS = [
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "Private answer:",
    "Private source text:",
    "Private platform browser/video context",
    "raw_source_text=",
    "learner_answer=",
    "AGENT_ENDPOINT=http",
    "full_support_bundle_payload",
]


class AdopterEvidenceArchiveError(RuntimeError):
    """Readable adopter evidence archive generation failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AdopterEvidenceArchiveError(f"Cannot read {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AdopterEvidenceArchiveError(f"JSON object expected: {path.relative_to(ROOT)}")
    return payload


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
    if leaks:
        raise AdopterEvidenceArchiveError(f"Adopter evidence archive leaked private data: {leaks}")


def require_file(relative_path: str) -> Path:
    path = ROOT / relative_path
    if not path.is_file():
        raise AdopterEvidenceArchiveError(f"Evidence archive file is missing: {relative_path}")
    return path


def public_file_ref(relative_path: str) -> dict[str, Any]:
    path = require_file(relative_path)
    return {
        "path": relative_path,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def fixture_payload(fixture_id: str) -> dict[str, Any]:
    mapping: dict[str, tuple[str, str, str]] = {
        "successful-release": (
            "release_ready",
            "scripts/release_check.sh",
            "CI, docker-images, manifest, and adoption-pack checks passed.",
        ),
        "local-ghcr-pull-timeout": (
            "local_environment_limit",
            "python3 scripts/verify_published_image_launch.py --tag v0.3.26-alpha --pull-timeout-seconds 600 --allow-pull-timeout-report",
            "Local GHCR pull timed out while manifest and docker-images evidence remained valid.",
        ),
        "needs-repro-issue": (
            "waiting_for_reproduction",
            "python3 scripts/diagnose_adoption.py",
            "Issue needs a copyable command, diagnostic code, and redacted logs.",
        ),
        "release-blocker": (
            "release_blocked_until_fixed",
            "python3 scripts/verify_platform_public_support_status.py --check",
            "A documented first-adopter path is failing and blocks release claims.",
        ),
        "platform-blocked": (
            "blocked_by_platform_runtime",
            "python3 scripts/verify_platform_manual_submission_rehearsal.py --check",
            "The platform cannot reach localhost or import tools without a user-side bridge.",
        ),
        "resolved-support-case": (
            "resolved_with_public_evidence",
            "python3 scripts/verify_external_adoption.py --pack platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree",
            "Closing evidence includes a passing command or documented platform limitation.",
        ),
    }
    public_status, command, note = mapping[fixture_id]
    payload = {
        "schema_version": FIXTURE_SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "fixture_id": fixture_id,
        "public_status": public_status,
        "public_note": note,
        "evidence_mapping": {
            "required_public_command": command,
            "linked_archive_schema": SCHEMA_VERSION,
            "allowed_public_fields": [
                "schema_version",
                "version",
                "fixture_id",
                "public_status",
                "required_public_command",
                "file_hashes",
                "known_limitation",
            ],
        },
        "privacy": {
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_prompts_included": False,
            "agent_endpoint_secrets_included": False,
            "real_model_keys_included": False,
            "browser_video_private_context_included": False,
            "personal_profile_data_included": False,
            "support_bundle_private_payload_included": False,
            "automatic_upload": False,
        },
    }
    assert_no_leaks(payload)
    return payload


def fixture_refs() -> list[dict[str, Any]]:
    return [
        {"fixture_id": fixture_id, **public_file_ref(f"fixtures/adopter-evidence-archive/{fixture_id}.json")}
        for fixture_id in FIXTURES
    ]


def schema_source_refs() -> dict[str, Any]:
    public_status = read_json(ROOT / "platform/generated/study-anything-public-support-status.json")
    public_dashboard = read_json(ROOT / "platform/generated/study-anything-public-maintainer-dashboard.json")
    published_image_evidence = read_json(
        ROOT / "platform/generated/study-anything-published-image-evidence.json"
    )
    release_asset_adoption = read_json(
        ROOT / "platform/generated/study-anything-release-asset-adoption.json"
    )
    adoption_pack = read_json(ROOT / "platform/generated/study-anything-platform-adoption-pack.json")
    ecosystem_submission = read_json(ROOT / "platform/ecosystem-submission.json")
    return {
        "public_support_status": {
            "schema_version": public_status.get("schema_version"),
            "ref": public_file_ref("platform/generated/study-anything-public-support-status.json"),
        },
        "public_maintainer_dashboard": {
            "schema_version": public_dashboard.get("schema_version"),
            "ref": public_file_ref("platform/generated/study-anything-public-maintainer-dashboard.json"),
        },
        "published_image_evidence": {
            "schema_version": published_image_evidence.get("schema_version"),
            "ref": public_file_ref("platform/generated/study-anything-published-image-evidence.json"),
            "verification_command": "python3 scripts/verify_published_image_evidence.py --check",
        },
        "release_asset_adoption": {
            "schema_version": release_asset_adoption.get("schema_version"),
            "ref": public_file_ref("platform/generated/study-anything-release-asset-adoption.json"),
            "verification_command": (
                "python3 scripts/verify_release_asset_adoption.py "
                "--fixture fixtures/release-asset-adoption/asset-only-pass.json "
                "--asset-dir platform/generated --runtime metadata-only"
            ),
        },
        "platform_adoption_pack": {
            "schema_version": adoption_pack.get("schema_version"),
            "verification_command": (
                "python3 scripts/verify_external_adoption.py "
                "--pack platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree"
            ),
            "generation_command": "python3 scripts/generate_platform_adoption_pack.py --check",
            "note": (
                "The adoption pack includes this evidence archive, so its manifest and zip "
                "hashes are verified by command instead of embedded here."
            ),
        },
        "ecosystem_submission": {
            "schema_version": ecosystem_submission.get("schema_version"),
            "ref": public_file_ref("platform/ecosystem-submission.json"),
        },
    }


def build_report(include_archive_metadata: bool = False, archive: bytes | None = None) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "purpose": (
            "Give external adopters and platform maintainers a single privacy-safe proof bundle "
            "for reproducing Study Anything platform-Agent launch evidence."
        ),
        "release_identity": {
            "tag": RELEASE_VERSION,
            "source_ref": "main",
            "package_version": RELEASE_VERSION.removeprefix("v"),
            "commit_verification_command": "git rev-parse HEAD",
            "release_view_command": f"gh release view {RELEASE_VERSION}",
        },
        "source_schemas": schema_source_refs(),
        "ci_evidence": {
            "required_workflows": [
                "ci on main",
                "docker-images on main",
                f"docker-images on {RELEASE_VERSION}",
            ],
            "verification_commands": [
                "gh run list --workflow ci --branch main --limit 1",
                "gh run list --workflow docker-images --branch main --limit 1",
                f"gh run list --workflow docker-images --branch {RELEASE_VERSION} --limit 1",
            ],
        },
        "docker_image_evidence": {
            "api_image": f"ghcr.io/jzvcpe-goat/study-anything/api:{RELEASE_VERSION}",
            "manifest_command": f"docker manifest inspect ghcr.io/jzvcpe-goat/study-anything/api:{RELEASE_VERSION}",
            "required_platforms": ["linux/amd64", "linux/arm64"],
            "published_image_smoke": (
                f"python3 scripts/verify_published_image_launch.py --tag {RELEASE_VERSION} "
                "--pull-timeout-seconds 600 --allow-pull-timeout-report"
            ),
            "published_image_evidence": "python3 scripts/verify_published_image_evidence.py --check",
            "local_pull_timeout_fallback_allowed": True,
        },
        "platform_pack_checksums": [
            public_file_ref("platform/packs/codex/pack.json"),
            public_file_ref("platform/packs/kimi/pack.json"),
            public_file_ref("platform/packs/workbuddy/pack.json"),
        ],
        "operator_reproduction": {
            "minimum_commands": [
                "python3 scripts/verify_adopter_evidence_archive.py --check",
                "python3 scripts/generate_adopter_evidence_archive.py --check",
                "python3 scripts/verify_published_image_evidence.py --check",
                "python3 scripts/generate_published_image_evidence.py --check",
                "python3 scripts/verify_release_asset_adoption.py --fixture fixtures/release-asset-adoption/asset-only-pass.json --asset-dir platform/generated --runtime metadata-only",
                "python3 scripts/generate_release_asset_adoption.py --check",
                "python3 scripts/verify_external_adoption.py --pack platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree",
                "python3 scripts/verify_platform_public_support_status.py --check",
                "scripts/release_check.sh",
            ],
            "target_minutes": 15,
        },
        "known_limitations": [
            "Localhost access depends on the host platform.",
            "Real model credentials stay inside the user's own Agent or platform runtime.",
            "Local GHCR pulls can be slower than CI and may need manifest-backed timeout evidence.",
        ],
        "handoff_checklist": [
            "Confirm generated evidence archive checksum and platform pack manifests.",
            "Run the archive verifier before publishing a release or platform submission.",
            "Attach the archive JSON, Markdown, zip checksum, and release URL to maintainer handoff.",
            "Do not paste raw learning data, private support bundles, Agent endpoints, or model keys.",
            "Close adoption issues only with a passing command or documented platform limitation.",
        ],
        "fixture_refs": fixture_refs(),
        "public_asset_refs": [public_file_ref(path) for path in PUBLIC_ASSET_PATHS],
        "privacy_assertions": {
            "raw_source_text_in_archive": False,
            "learner_answers_in_archive": False,
            "agent_prompts_in_archive": False,
            "agent_endpoint_secrets_in_archive": False,
            "real_model_keys_in_archive": False,
            "browser_video_private_context_in_archive": False,
            "personal_profile_data_in_archive": False,
            "support_bundle_private_payload_in_archive": False,
            "automatic_upload": False,
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_adopter_evidence_archive.py --check",
            "generate_command": "python3 scripts/generate_adopter_evidence_archive.py --check",
            "pack_command": "python3 scripts/verify_adopter_evidence_archive.py --pack platform/generated/study-anything-platform-adoption-pack.zip",
            "release_gate": "scripts/release_check.sh",
        },
    }
    if include_archive_metadata:
        if archive is None:
            raise AdopterEvidenceArchiveError("archive bytes are required for archive metadata")
        report["archive"] = {
            "path": "platform/generated/study-anything-adopter-evidence-archive.zip",
            "sha256_path": "platform/generated/study-anything-adopter-evidence-archive.sha256",
            "bytes": len(archive),
            "sha256": sha256_bytes(archive),
            "archive_root": ARCHIVE_ROOT,
        }
    assert_no_leaks(report)
    return report


def markdown_report(report: dict[str, Any]) -> str:
    commands = "\n".join(f"- `{command}`" for command in report["operator_reproduction"]["minimum_commands"])
    limitations = "\n".join(f"- {item}" for item in report["known_limitations"])
    fixtures = "\n".join(
        f"- `{item['fixture_id']}`: `{item['sha256']}`" for item in report["fixture_refs"]
    )
    archive = report.get("archive") or {}
    archive_line = (
        f"- Archive: `{archive.get('path')}` sha256 `{archive.get('sha256')}`"
        if archive
        else "- Archive: generated during packaging"
    )
    return f"""# Study Anything Adopter Evidence Archive

Schema: `{report['schema_version']}`
Version: `{report['version']}`
Status: `{report['status']}`

This archive is a public, metadata-only handoff bundle for external adopters and
platform maintainers. It links release commands, CI expectations, Docker image
manifest checks, platform pack checksums, public support status, and maintainer
handoff steps without copying private learning data.

## Archive

{archive_line}

## Reproduction Commands

{commands}

## Known Limitations

{limitations}

## Fixture Hashes

{fixtures}

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, personal profile data, support bundle private payloads, or private
browser/video/app context are included. Real model credentials remain inside the
user-owned Agent or platform runtime.
"""


def archive_readme() -> str:
    return f"""# Study Anything Adopter Evidence Archive

Version: {RELEASE_VERSION}
Schema: {SCHEMA_VERSION}

Run `python3 scripts/verify_adopter_evidence_archive.py --check` in the repo, or
`python3 scripts/verify_adopter_evidence_archive.py --pack platform/generated/study-anything-platform-adoption-pack.zip`
against the adoption pack.
"""


def archive_bytes(base_report: dict[str, Any], markdown: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        records: list[tuple[str, bytes]] = [
            (f"{ARCHIVE_ROOT}/EVIDENCE_README.md", archive_readme().encode("utf-8")),
            (f"{ARCHIVE_ROOT}/manifest.json", dump_json(base_report).encode("utf-8")),
            (f"{ARCHIVE_ROOT}/study-anything-adopter-evidence-archive.md", markdown.encode("utf-8")),
        ]
        for fixture_id in FIXTURES:
            records.append(
                (
                    f"{ARCHIVE_ROOT}/fixtures/adopter-evidence-archive/{fixture_id}.json",
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
        raise AdopterEvidenceArchiveError(
            "Adopter evidence archive assets are stale. Run "
            "`python3 scripts/generate_adopter_evidence_archive.py`. "
            f"missing={missing} stale={stale}"
        )
    print("ok    generated adopter evidence archive assets are up to date")


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
        print(f"generate_adopter_evidence_archive failed: {exc}", file=sys.stderr)
        sys.exit(1)
