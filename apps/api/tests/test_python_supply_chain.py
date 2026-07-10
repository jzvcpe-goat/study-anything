from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "generate_python_supply_chain.py"


def load_script():
    spec = importlib.util.spec_from_file_location("generate_python_supply_chain", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


supply_chain = load_script()


class PythonSupplyChainTests(unittest.TestCase):
    def test_uv_version_floor(self) -> None:
        self.assertEqual(supply_chain.parse_uv_version("uv 0.11.18"), (0, 11, 18))
        self.assertEqual(
            supply_chain.parse_uv_version("uv 0.11.18 (e32666915 2026-06-01)"),
            (0, 11, 18),
        )

    def test_unhashed_requirement_is_rejected(self) -> None:
        with self.assertRaises(supply_chain.PythonSupplyChainError):
            supply_chain.validate_requirements_text("fastapi==1.0.0\n", label="test")

    def test_direct_url_requirement_is_rejected(self) -> None:
        text = "package @ https://example.invalid/package.whl --hash=sha256:" + "a" * 64

        with self.assertRaises(supply_chain.PythonSupplyChainError):
            supply_chain.validate_requirements_text(text, label="test")

    def test_hashed_requirement_is_accepted(self) -> None:
        text = (
            "fastapi==1.0.0 \\\n"
            "    --hash=sha256:" + "a" * 64 + "\n"
        )

        self.assertEqual(
            supply_chain.validate_requirements_text(text, label="test"),
            1,
        )


if __name__ == "__main__":
    unittest.main()
