from __future__ import annotations

import unittest

from _path import ROOT  # noqa: F401

from neural_console.core.integrations import integration_matrix


class IntegrationMatrixTests(unittest.TestCase):
    def test_matrix_lists_required_open_source_projects(self) -> None:
        names = {item.name for item in integration_matrix()}

        expected = {
            "LangGraph",
            "Langfuse",
            "Agent Gateway",
            "Ollama",
            "FalkorDB",
            "LanceDB",
            "Mem0",
            "LangMem",
            "py-fsrs",
            "Postgres",
            "ClickHouse",
            "Redis",
            "MinIO",
        }

        self.assertTrue(expected.issubset(names))


if __name__ == "__main__":
    unittest.main()
