#!/usr/bin/env python3
"""Generate deterministic platform plugin import packs."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "platform" / "generated"
SCHEMA_VERSION = "study-anything-platform-plugin-pack-v1"
PACKAGE_ROOT_PREFIX = "study-anything"
PLATFORMS = ("codex", "kimi", "workbuddy", "hermes")


class PluginPackError(RuntimeError):
    """Readable plugin-pack generation failure."""


@dataclass(frozen=True)
class PackSpec:
    platform_id: str
    package_type: str
    title: str
    summary: str
    files: tuple[tuple[str, str, str], ...]
    import_assets: tuple[str, ...]
    verification_commands: tuple[str, ...]
    known_limitations: tuple[str, ...]

    @property
    def package_name(self) -> str:
        return f"study-anything-{self.platform_id}-plugin-pack"

    @property
    def archive_root(self) -> str:
        return self.package_name

    @property
    def sidecar_json(self) -> Path:
        return OUTPUT_DIR / f"{self.package_name}.json"

    @property
    def archive_path(self) -> Path:
        return OUTPUT_DIR / f"{self.package_name}.zip"

    @property
    def sha256_path(self) -> Path:
        return OUTPUT_DIR / f"{self.package_name}.sha256"


COMMON_FILES: tuple[tuple[str, str, str], ...] = (
    ("README.md", "root_doc", "Project positioning and local-first adoption overview."),
    ("QUICKSTART.md", "quickstart", "Beginner-friendly quickstart entrypoint."),
    ("START_HERE.command", "launcher", "Double-click macOS beginner launcher."),
    ("docs/getting-started.md", "operator_doc", "Step-by-step first-run guide."),
    ("docs/operator-drill.md", "operator_doc", "External platform operator drill."),
    ("platform/study-anything-platform-tools.json", "tool_manifest", "Source platform tool contract."),
    ("platform/generated/study-anything-tool-catalog.md", "tool_catalog", "Human-readable platform tool catalog."),
    ("scripts/start_here.sh", "launcher", "One-command local runtime launcher."),
    ("scripts/launch_skill_mode.sh", "runtime", "Local Skill Mode API launcher."),
    ("scripts/stop_skill_mode.sh", "runtime", "Local Skill Mode API stop helper."),
    ("scripts/run_skill_mode_demo.sh", "verification", "One-command local demo and smoke check."),
    ("scripts/study_anything_cli.py", "cli", "CLI for learning loop and evidence commands."),
    ("scripts/localhost_diagnostics.py", "diagnostics", "Shared localhost diagnostics and redaction helpers."),
    ("scripts/verify_platform_agent_tools.py", "verification", "Live local API tool-surface verifier."),
    ("scripts/verify_external_adoption.py", "verification", "Extracted adoption-pack verifier."),
)


SPECS: dict[str, PackSpec] = {
    "codex": PackSpec(
        platform_id="codex",
        package_type="terminal_skill",
        title="Study Anything Codex Plugin Pack",
        summary=(
            "Install the repo-local Skill in Codex or another terminal-capable Agent "
            "and let that Agent call the local Study Anything runtime."
        ),
        files=COMMON_FILES
        + (
            ("docs/skill-mode.md", "operator_doc", "Skill Mode startup and CLI guide."),
            ("platform/packs/codex/README.md", "platform_pack", "Codex-specific import guide."),
            ("platform/packs/codex/pack.json", "platform_pack", "Codex platform pack source descriptor."),
            ("skills/study-anything/SKILL.md", "skill", "Codex Skill entrypoint."),
            (
                "skills/study-anything/agents/openai.yaml",
                "skill_metadata",
                "OpenAI-compatible Skill agent metadata.",
            ),
        ),
        import_assets=(
            "skills/study-anything/SKILL.md",
            "skills/study-anything/agents/openai.yaml",
            "platform/packs/codex/pack.json",
            "platform/generated/study-anything-tool-catalog.md",
        ),
        verification_commands=(
            "./START_HERE.command",
            "python3 scripts/study_anything_cli.py health",
            "API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_agent_tools.py",
        ),
        known_limitations=(
            "Requires a local checkout or extracted runtime files that can execute shell commands.",
            "Does not install a marketplace extension automatically.",
            "Real model credentials stay inside the user's platform Agent or gateway, not Study Anything.",
        ),
    ),
    "kimi": PackSpec(
        platform_id="kimi",
        package_type="openai_compatible_tools",
        title="Study Anything Kimi Plugin Pack",
        summary=(
            "Import OpenAI-compatible tool definitions into Kimi-compatible hosts and "
            "call the local or private Study Anything HTTP runtime."
        ),
        files=COMMON_FILES
        + (
            ("docs/use-with-kimi.md", "operator_doc", "Kimi usage modes and no-key boundary."),
            ("docs/kimi-agent-gateway.md", "operator_doc", "OpenAI-compatible local Agent gateway guide."),
            ("platform/packs/kimi/README.md", "platform_pack", "Kimi-specific import guide."),
            ("platform/packs/kimi/pack.json", "platform_pack", "Kimi platform pack source descriptor."),
            (
                "platform/generated/study-anything-openai-tools.json",
                "tool_import",
                "OpenAI-compatible function tool definitions.",
            ),
            (
                "platform/generated/study-anything-platform-openapi.json",
                "tool_import",
                "OpenAPI fallback import asset.",
            ),
            ("scripts/openai_compatible_agent_gateway.py", "gateway", "User-owned local HTTP Agent gateway."),
            ("scripts/verify_openai_compatible_gateway.py", "verification", "Gateway contract and live verifier."),
        ),
        import_assets=(
            "platform/generated/study-anything-openai-tools.json",
            "platform/generated/study-anything-platform-openapi.json",
            "platform/generated/study-anything-tool-catalog.md",
            "platform/packs/kimi/pack.json",
        ),
        verification_commands=(
            "./START_HERE.command",
            "python3 scripts/verify_openai_compatible_gateway.py --contract-only",
            "API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_agent_tools.py",
        ),
        known_limitations=(
            "Kimi web or workspace policy may block direct localhost calls; use a private gateway when needed.",
            "Manual gateway startup is transitional; Kimi Work or another platform Agent should own model configuration.",
            "Study Anything does not store real model API keys.",
        ),
    ),
    "workbuddy": PackSpec(
        platform_id="workbuddy",
        package_type="inline_learning_workflow",
        title="Study Anything WorkBuddy Plugin Pack",
        summary=(
            "Run the WorkBuddy inline learning workflow first, while keeping constrained "
            "OpenAPI HTTP tools as a fallback for workspaces that can call a local or private runtime."
        ),
        files=COMMON_FILES
        + (
            ("docs/api.md", "operator_doc", "HTTP API reference for platform workspaces."),
            ("docs/use-with-workbuddy.md", "operator_doc", "Beginner WorkBuddy inline flow and fallback guide."),
            (
                "docs/platform-agent-integrations.md",
                "operator_doc",
                "General external platform Agent integration guide.",
            ),
            ("platform/packs/workbuddy/README.md", "platform_pack", "WorkBuddy-style import guide."),
            (
                "platform/packs/workbuddy/pack.json",
                "platform_pack",
                "WorkBuddy platform pack source descriptor.",
            ),
            (
                "scripts/workbuddy_learning_flow.py",
                "inline_runtime",
                "WorkBuddy inline learning flow CLI.",
            ),
            (
                "scripts/verify_workbuddy_inline_learning_flow.py",
                "verification",
                "WorkBuddy inline flow verifier.",
            ),
            (
                "platform/schemas/workbuddy-learning-input-v1.schema.json",
                "schema",
                "WorkBuddy inline input schema.",
            ),
            (
                "platform/schemas/workbuddy-learning-output-v1.schema.json",
                "schema",
                "WorkBuddy inline output schema.",
            ),
            (
                "fixtures/workbuddy-learning-flow/deepseek-pm-interview/input.json",
                "fixture",
                "DeepSeek PM interview inline learning fixture.",
            ),
            (
                "fixtures/workbuddy-learning-flow/deepseek-pm-interview/expected-boundary.json",
                "fixture",
                "WorkBuddy inline privacy and quality boundary fixture.",
            ),
            (
                "platform/generated/study-anything-workbuddy-inline-learning-flow.json",
                "evidence",
                "WorkBuddy inline verifier evidence.",
            ),
            (
                "platform/generated/study-anything-platform-openapi.json",
                "tool_import",
                "OpenAPI 3.1 fallback import asset.",
            ),
        ),
        import_assets=(
            "scripts/workbuddy_learning_flow.py",
            "platform/schemas/workbuddy-learning-input-v1.schema.json",
            "platform/schemas/workbuddy-learning-output-v1.schema.json",
            "platform/generated/study-anything-platform-openapi.json",
            "platform/generated/study-anything-tool-catalog.md",
            "platform/packs/workbuddy/pack.json",
        ),
        verification_commands=(
            "python3 scripts/workbuddy_learning_flow.py doctor",
            "python3 scripts/verify_workbuddy_inline_learning_flow.py --check",
            "python3 scripts/workbuddy_learning_flow.py demo --case deepseek-pm-interview",
            "API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_agent_tools.py",
            "python3 scripts/verify_platform_operator_drill.py --check",
        ),
        known_limitations=(
            "Inline mode expects WorkBuddy or the platform Agent to generate teaching, quiz, and grading content.",
            "HTTP/OpenAPI tools are fallback assets and still require the host workspace to reach the configured endpoint.",
            "Real model credentials and browser/app access remain owned by WorkBuddy or the user's platform Agent.",
        ),
    ),
    "hermes": PackSpec(
        platform_id="hermes",
        package_type="hermes_skill_http_tools",
        title="Study Anything Hermes Agent Plugin Pack",
        summary=(
            "Expose Study Anything to Hermes Agent through the Hermes Skills system "
            "and local HTTP/CLI tools while Hermes keeps model credentials, memory, "
            "browser/app access, MCP servers, and user conversation."
        ),
        files=COMMON_FILES
        + (
            ("docs/use-with-hermes.md", "operator_doc", "Hermes Agent Skill and local HTTP/CLI setup guide."),
            (
                "docs/platform-agent-integrations.md",
                "operator_doc",
                "General external platform Agent integration guide.",
            ),
            ("platform/packs/hermes/README.md", "platform_pack", "Hermes Agent import guide."),
            ("platform/packs/hermes/pack.json", "platform_pack", "Hermes platform pack source descriptor."),
            ("skills/study-anything/SKILL.md", "skill", "Hermes-compatible Skill entrypoint."),
            (
                "platform/generated/study-anything-platform-openapi.json",
                "tool_import",
                "OpenAPI 3.1 reference asset for local/private HTTP tools.",
            ),
        ),
        import_assets=(
            "skills/study-anything/SKILL.md",
            "platform/generated/study-anything-platform-openapi.json",
            "platform/generated/study-anything-tool-catalog.md",
            "platform/packs/hermes/pack.json",
            "docs/use-with-hermes.md",
        ),
        verification_commands=(
            "hermes skills install https://raw.githubusercontent.com/jzvcpe-goat/study-anything/main/skills/study-anything/SKILL.md --name study-anything --yes",
            "./START_HERE.command",
            "python3 scripts/study_anything_cli.py health",
            "API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_agent_tools.py",
            "python3 scripts/verify_platform_plugin_packs.py --platform hermes --check",
        ),
        known_limitations=(
            "This pack is a Hermes Skill and local HTTP/CLI import helper, not a published Hermes-native Python plugin repo.",
            "Do not claim `hermes plugins install jzvcpe-goat/study-anything` works until a standalone plugin repo is released and field-tested.",
            "Real model credentials, memory, browser/app access, MCP servers, and outside tools stay in Hermes or the user's private gateway.",
        ),
    ),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dump_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def read_json(relative_path: str) -> dict[str, Any]:
    path = assert_safe_path(relative_path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PluginPackError(f"Cannot read JSON {relative_path}: {exc}") from exc


def assert_safe_path(relative_path: str) -> Path:
    posix = PurePosixPath(relative_path)
    if posix.is_absolute() or ".." in posix.parts:
        raise PluginPackError(f"Plugin pack path must be repo-relative: {relative_path}")
    if any(part in {".git", ".env", ".venv", "data", "__pycache__"} for part in posix.parts):
        raise PluginPackError(f"Unsafe plugin pack path: {relative_path}")
    path = ROOT / relative_path
    if not path.exists():
        raise PluginPackError(f"Plugin pack file is missing: {relative_path}")
    if path.is_dir():
        raise PluginPackError(f"Plugin pack entry must be a file: {relative_path}")
    return path


def unique_files(spec: PackSpec) -> list[tuple[str, str, str]]:
    seen: set[str] = set()
    result: list[tuple[str, str, str]] = []
    for item in spec.files:
        relative_path = item[0]
        if relative_path in seen:
            raise PluginPackError(f"Duplicate file in {spec.platform_id} pack: {relative_path}")
        seen.add(relative_path)
        result.append(item)
    return result


def file_record(spec: PackSpec, relative_path: str, kind: str, purpose: str) -> dict[str, object]:
    path = assert_safe_path(relative_path)
    return {
        "path": relative_path,
        "archive_path": f"{spec.archive_root}/{relative_path}",
        "kind": kind,
        "purpose": purpose,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def load_source_pack(spec: PackSpec) -> dict[str, Any]:
    pack_path = f"platform/packs/{spec.platform_id}/pack.json"
    pack = read_json(pack_path)
    if pack.get("schema_version") != "study-anything-platform-pack-v1":
        raise PluginPackError(f"{pack_path} schema drifted.")
    if pack.get("platform_id") != spec.platform_id:
        raise PluginPackError(f"{pack_path} platform_id drifted.")
    if pack.get("integration_mode") != spec.package_type:
        raise PluginPackError(f"{pack_path} integration mode drifted.")
    return pack


def manifest_without_archive(spec: PackSpec) -> dict[str, object]:
    source_pack = load_source_pack(spec)
    file_paths = {path for path, _kind, _purpose in unique_files(spec)}
    missing_import_assets = [path for path in spec.import_assets if path not in file_paths]
    if missing_import_assets:
        raise PluginPackError(
            f"{spec.platform_id} import assets are not included in the package: {missing_import_assets}"
        )
    entrypoints = source_pack.get("entrypoints", {})
    local_runtime = {
        "beginner_launcher": "./START_HERE.command",
        "script_launcher": "./scripts/start_here.sh",
        "skill_mode": "./scripts/launch_skill_mode.sh",
        "stop": "./scripts/stop_skill_mode.sh",
        "api_base": "http://127.0.0.1:8000",
    }
    if spec.platform_id == "workbuddy":
        local_runtime = {
            "workbuddy_doctor": "python3 scripts/workbuddy_learning_flow.py doctor",
            "workbuddy_inline": "python3 scripts/workbuddy_learning_flow.py demo --case deepseek-pm-interview",
            "http_fallback_beginner_launcher": "./START_HERE.command",
            "http_fallback_script_launcher": "./scripts/start_here.sh",
            "http_fallback_skill_mode": "./scripts/launch_skill_mode.sh",
            "http_fallback_stop": "./scripts/stop_skill_mode.sh",
            "http_fallback_api_base": "http://127.0.0.1:8000",
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "platform_id": spec.platform_id,
        "package_type": spec.package_type,
        "name": spec.package_name,
        "title": spec.title,
        "summary": spec.summary,
        "source_pack": f"platform/packs/{spec.platform_id}/pack.json",
        "source_pack_sha256": sha256(ROOT / f"platform/packs/{spec.platform_id}/pack.json"),
        "entrypoints": entrypoints,
        "import_assets": list(spec.import_assets),
        "local_runtime": local_runtime,
        "verification_commands": list(spec.verification_commands),
        "privacy_boundaries": {
            "must_not_store_or_share": source_pack.get("must_not_log_or_share", []),
            "real_model_keys": "owned by the user's platform Agent or private gateway",
            "study_anything_stores": "local learning state, validation evidence, redacted audit metadata",
        },
        "known_limitations": list(spec.known_limitations),
        "files": [file_record(spec, *item) for item in unique_files(spec)],
    }


def pack_readme(spec: PackSpec, manifest: dict[str, object]) -> str:
    commands = "\n".join(f"- `{command}`" for command in manifest["verification_commands"])  # type: ignore[index]
    assets = "\n".join(f"- `{path}`" for path in manifest["import_assets"])  # type: ignore[index]
    limitations = "\n".join(f"- {item}" for item in manifest["known_limitations"])  # type: ignore[index]
    if spec.platform_id == "workbuddy":
        runtime = """1. Prefer inline mode: `python3 scripts/workbuddy_learning_flow.py demo --case deepseek-pm-interview`.
2. Let WorkBuddy own real model/search/file/context work and pass structured JSON to the inline script.
3. Use OpenAPI/local HTTP only as fallback when the workspace can reach the endpoint."""
    else:
        runtime = f"""1. Start the local Study Anything runtime with `./START_HERE.command` or `./scripts/start_here.sh`.
2. Import the assets above into {spec.platform_id}.
3. Point the host Agent or workspace at `http://127.0.0.1:8000` or your private runtime endpoint."""
    return f"""# {spec.title}

{spec.summary}

## Import Assets

{assets}

## Local Runtime

{runtime}

## Verification

{commands}

## Privacy Boundary

Real model credentials, browser access, external app context, and private tools stay in the user's
platform Agent or gateway. Study Anything only owns the local learning workflow, validation,
redacted evidence, and export contracts.

## Known Limitations

{limitations}
"""


def zip_info(name: str, executable: bool = False) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name)
    info.date_time = (1980, 1, 1, 0, 0, 0)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = ((0o755 if executable else 0o644) & 0xFFFF) << 16
    return info


def archive_bytes(spec: PackSpec, manifest: dict[str, object]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(
            zip_info(f"{spec.archive_root}/manifest.json"),
            dump_json(manifest).encode("utf-8"),
        )
        archive.writestr(
            zip_info(f"{spec.archive_root}/PLUGIN_PACK_README.md"),
            pack_readme(spec, manifest).encode("utf-8"),
        )
        for record in sorted(manifest["files"], key=lambda item: str(item["path"])):  # type: ignore[index]
            relative_path = str(record["path"])
            source = assert_safe_path(relative_path)
            executable = source.suffix in {".sh", ".command"} or relative_path.startswith("scripts/")
            archive.writestr(zip_info(str(record["archive_path"]), executable=executable), source.read_bytes())
    return buffer.getvalue()


def build_outputs(spec: PackSpec) -> tuple[str, bytes, str]:
    archive_manifest = manifest_without_archive(spec)
    archive = archive_bytes(spec, archive_manifest)
    archive_hash = sha256_bytes(archive)
    sidecar = dict(archive_manifest)
    sidecar["archive"] = {
        "path": f"platform/generated/{spec.package_name}.zip",
        "sha256": archive_hash,
        "bytes": len(archive),
        "root": spec.archive_root,
    }
    sha_text = f"{archive_hash}  {spec.package_name}.zip\n"
    return dump_json(sidecar), archive, sha_text


def write_outputs(platforms: tuple[str, ...] = PLATFORMS) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for platform_id in platforms:
        spec = SPECS[platform_id]
        manifest_text, archive, sha_text = build_outputs(spec)
        spec.sidecar_json.write_text(manifest_text, encoding="utf-8")
        spec.archive_path.write_bytes(archive)
        spec.sha256_path.write_text(sha_text, encoding="utf-8")
        print(f"wrote {spec.sidecar_json.relative_to(ROOT)}")
        print(f"wrote {spec.archive_path.relative_to(ROOT)}")
        print(f"wrote {spec.sha256_path.relative_to(ROOT)}")


def check_outputs(platforms: tuple[str, ...] = PLATFORMS) -> None:
    stale: list[str] = []
    missing: list[str] = []
    for platform_id in platforms:
        spec = SPECS[platform_id]
        expected_manifest, expected_archive, expected_sha = build_outputs(spec)
        for path in [spec.sidecar_json, spec.archive_path, spec.sha256_path]:
            if not path.exists():
                missing.append(str(path.relative_to(ROOT)))
        if spec.sidecar_json.exists() and spec.sidecar_json.read_text(encoding="utf-8") != expected_manifest:
            stale.append(str(spec.sidecar_json.relative_to(ROOT)))
        if spec.archive_path.exists() and spec.archive_path.read_bytes() != expected_archive:
            stale.append(str(spec.archive_path.relative_to(ROOT)))
        if spec.sha256_path.exists() and spec.sha256_path.read_text(encoding="utf-8") != expected_sha:
            stale.append(str(spec.sha256_path.relative_to(ROOT)))
    if missing or stale:
        raise PluginPackError(
            "Platform plugin packs are stale. Run "
            "`python3 scripts/generate_platform_plugin_packs.py`. "
            f"missing={missing} stale={stale}"
        )
    print("ok    generated platform plugin packs are up to date")


def parse_platforms(values: list[str] | None) -> tuple[str, ...]:
    if not values:
        return PLATFORMS
    unknown = sorted(set(values) - set(PLATFORMS))
    if unknown:
        raise PluginPackError(f"Unknown platforms: {unknown}")
    return tuple(values)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if generated plugin packs are stale")
    parser.add_argument("--platform", action="append", choices=PLATFORMS, help="Generate only one platform pack")
    args = parser.parse_args()
    platforms = parse_platforms(args.platform)
    if args.check:
        check_outputs(platforms)
    else:
        write_outputs(platforms)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"generate_platform_plugin_packs failed: {exc}", file=sys.stderr)
        sys.exit(1)
