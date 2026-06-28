from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path

from _path import ROOT  # noqa: F401


REPO = Path(__file__).resolve().parents[3]
GENERATED = REPO / "platform" / "generated"
PACKS = {
    "codex": {
        "package_type": "terminal_skill",
        "required_assets": {
            "skills/study-anything/SKILL.md",
            "platform/packs/codex/pack.json",
        },
    },
    "kimi": {
        "package_type": "openai_compatible_tools",
        "required_assets": {
            "platform/generated/study-anything-openai-tools.json",
            "platform/generated/study-anything-platform-openapi.json",
            "platform/packs/kimi/pack.json",
        },
    },
    "workbuddy": {
        "package_type": "openapi_http_tools",
        "required_assets": {
            "platform/generated/study-anything-platform-openapi.json",
            "platform/packs/workbuddy/pack.json",
        },
    },
    "hermes": {
        "package_type": "hermes_skill_http_tools",
        "required_assets": {
            "docs/use-with-hermes.md",
            "skills/study-anything/SKILL.md",
            "platform/generated/study-anything-platform-openapi.json",
            "platform/packs/hermes/pack.json",
        },
    },
}


class PlatformPluginPackTests(unittest.TestCase):
    def run_script(self, script_name: str, *args: str) -> str:
        completed = subprocess.run(
            [sys.executable, str(REPO / "scripts" / script_name), *args],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return completed.stdout

    def test_platform_plugin_packs_are_current_and_verified(self) -> None:
        self.run_script("generate_platform_plugin_packs.py", "--check")
        output = self.run_script("verify_platform_plugin_packs.py", "--check")
        for platform_id in PACKS:
            self.assertIn(f"study-anything-{platform_id}-plugin-pack is import-ready", output)

    def test_platform_plugin_download_index_is_current_and_verified(self) -> None:
        self.run_script("generate_platform_plugin_downloads.py", "--check")
        output = self.run_script("verify_platform_plugin_downloads.py", "--check")
        self.assertIn('"schema_version": "platform-plugin-downloads-v1"', output)
        self.assertIn('"release_asset_count": 12', output)
        report = json.loads((GENERATED / "study-anything-platform-plugin-downloads.json").read_text(encoding="utf-8"))
        self.assertEqual(report["schema_version"], "platform-plugin-downloads-v1")
        self.assertEqual(
            set(report["required_release_asset_names"]),
            {
                "study-anything-codex-plugin-pack.json",
                "study-anything-codex-plugin-pack.zip",
                "study-anything-codex-plugin-pack.sha256",
                "study-anything-kimi-plugin-pack.json",
                "study-anything-kimi-plugin-pack.zip",
                "study-anything-kimi-plugin-pack.sha256",
                "study-anything-workbuddy-plugin-pack.json",
                "study-anything-workbuddy-plugin-pack.zip",
                "study-anything-workbuddy-plugin-pack.sha256",
                "study-anything-hermes-plugin-pack.json",
                "study-anything-hermes-plugin-pack.zip",
                "study-anything-hermes-plugin-pack.sha256",
            },
        )

    def test_platform_plugin_pack_archives_have_single_root_and_manifest(self) -> None:
        for platform_id, spec in PACKS.items():
            package_name = f"study-anything-{platform_id}-plugin-pack"
            sidecar_path = GENERATED / f"{package_name}.json"
            archive_path = GENERATED / f"{package_name}.zip"
            sha_path = GENERATED / f"{package_name}.sha256"
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))

            self.assertEqual(sidecar["schema_version"], "study-anything-platform-plugin-pack-v1")
            self.assertEqual(sidecar["platform_id"], platform_id)
            self.assertEqual(sidecar["package_type"], spec["package_type"])
            self.assertEqual(sidecar["archive"]["sha256"], hashlib.sha256(archive_path.read_bytes()).hexdigest())
            self.assertEqual(
                sha_path.read_text(encoding="utf-8"),
                f"{sidecar['archive']['sha256']}  {package_name}.zip\n",
            )

            with zipfile.ZipFile(archive_path) as archive:
                names = archive.namelist()
                self.assertEqual({name.split("/", 1)[0] for name in names}, {package_name})
                self.assertIn(f"{package_name}/manifest.json", names)
                self.assertIn(f"{package_name}/PLUGIN_PACK_README.md", names)
                manifest = json.loads(archive.read(f"{package_name}/manifest.json").decode("utf-8"))
                sidecar_without_archive = dict(sidecar)
                sidecar_without_archive.pop("archive")
                self.assertEqual(manifest, sidecar_without_archive)
                paths = {item["path"] for item in manifest["files"]}
                self.assertTrue(spec["required_assets"].issubset(paths))
                self.assertFalse(any(path.startswith("/") for path in paths))
                self.assertFalse(any("/.env" in path or "/data/" in path or "/.venv/" in path for path in paths))
                for item in manifest["files"]:
                    self.assertRegex(item["sha256"], r"^[a-f0-9]{64}$")
                    self.assertIn(item["archive_path"], names)


if __name__ == "__main__":
    unittest.main()
