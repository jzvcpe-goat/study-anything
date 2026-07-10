from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "verify_container_security.py"


def load_script():
    script_dir = str(SCRIPT.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location("verify_container_security", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


security = load_script()


class ContainerSecurityTests(unittest.TestCase):
    def test_repository_policy_passes(self) -> None:
        report = security.verify()

        self.assertEqual(report["status"], "pass")
        self.assertTrue(report["dockerfile"]["non_root_user_final"])
        self.assertTrue(report["dockerfile"]["base_image_digest_pinned"])
        self.assertFalse(report["runtime_container"]["checked"])

    def test_root_runtime_user_is_rejected(self) -> None:
        text = security.DOCKERFILE.read_text(encoding="utf-8").replace(
            "USER 10001:10001", "USER root"
        )

        with self.assertRaises(security.ContainerSecurityError):
            security.validate_dockerfile(text)

    def test_privileged_service_is_rejected(self) -> None:
        compose = copy.deepcopy(security.read_compose())
        compose["services"]["api"]["privileged"] = True

        with self.assertRaises(security.ContainerSecurityError):
            security.validate_compose(compose)

    def test_writable_root_filesystem_is_rejected(self) -> None:
        compose = copy.deepcopy(security.read_compose())
        compose["services"]["mock-http-agent"]["read_only"] = False

        with self.assertRaises(security.ContainerSecurityError):
            security.validate_compose(compose)

    def test_missing_tmpfs_hardening_is_rejected(self) -> None:
        compose = copy.deepcopy(security.read_compose())
        compose["services"]["api"]["tmpfs"] = ["/tmp:rw"]

        with self.assertRaises(security.ContainerSecurityError):
            security.validate_compose(compose)

    def test_full_profile_public_port_is_rejected(self) -> None:
        compose = copy.deepcopy(security.read_compose())
        compose["services"]["minio"]["ports"] = ["9090:9000"]

        with self.assertRaises(security.ContainerSecurityError):
            security.validate_compose(compose)

    def test_minio_default_root_password_is_rejected(self) -> None:
        compose = copy.deepcopy(security.read_compose())
        compose["services"]["minio"]["environment"]["MINIO_ROOT_PASSWORD"] = "miniosecret"

        with self.assertRaises(security.ContainerSecurityError):
            security.validate_compose(compose)

    def test_unpinned_action_is_rejected(self) -> None:
        line = "      - uses: actions/checkout@v6"

        self.assertIsNone(security.ACTION_PIN_PATTERN.match(line))


if __name__ == "__main__":
    unittest.main()
