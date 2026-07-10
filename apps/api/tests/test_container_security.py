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
        self.assertTrue(report["dockerfile"]["hash_bound_dependencies"])
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

    def test_missing_agent_endpoint_policy_passthrough_is_rejected(self) -> None:
        compose = copy.deepcopy(security.read_compose())
        del compose["services"]["api"]["environment"][
            "STUDY_ANYTHING_AGENT_ENDPOINT_ALLOWLIST"
        ]

        with self.assertRaises(security.ContainerSecurityError):
            security.validate_compose(compose)

    def test_missing_hosted_identity_passthrough_is_rejected(self) -> None:
        compose = copy.deepcopy(security.read_compose())
        del compose["services"]["api"]["environment"]["STUDY_ANYTHING_OIDC_JWKS_JSON"]

        with self.assertRaises(security.ContainerSecurityError):
            security.validate_compose(compose)

    def test_unpinned_action_is_rejected(self) -> None:
        line = "      - uses: actions/checkout@v6"

        self.assertIsNone(security.ACTION_PIN_PATTERN.match(line))

    def test_ci_compose_command_without_generated_env_is_rejected(self) -> None:
        ci = (security.WORKFLOW_DIR / "ci.yml").read_text(encoding="utf-8")
        broken = ci.replace("docker compose --env-file .env ", "docker compose ", 1)

        with self.assertRaises(security.ContainerSecurityError):
            security.validate_ci_workflow(broken)

    def test_ci_unpinned_python_base_image_is_rejected(self) -> None:
        ci = (security.WORKFLOW_DIR / "ci.yml").read_text(encoding="utf-8")
        broken = ci.replace(
            security.PINNED_PYTHON_BASE_IMAGE,
            "public.ecr.aws/docker/library/python:3.11-slim",
            1,
        )

        with self.assertRaises(security.ContainerSecurityError):
            security.validate_ci_workflow(broken)

    def test_docker_unhashed_dependency_install_is_rejected(self) -> None:
        text = security.DOCKERFILE.read_text(encoding="utf-8").replace(
            "--require-hashes -r requirements/locked-full.txt",
            "-r requirements/locked-full.txt",
        )

        with self.assertRaises(security.ContainerSecurityError):
            security.validate_dockerfile(text)


if __name__ == "__main__":
    unittest.main()
