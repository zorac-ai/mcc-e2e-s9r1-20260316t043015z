from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_cli(db_path: Path, *args: str) -> object:
    result = subprocess.run(
        [sys.executable, "-m", "issue_tracker", "--db", str(db_path), *args],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


class CliTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "issues.json"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_json(self, *args: str) -> object:
        return run_cli(self.db_path, *args)

    def test_create_and_list_open_issues(self) -> None:
        created = self.run_json("add", "Ship the CLI")
        self.assertEqual(created["id"], 1)
        self.assertEqual(created["status"], "open")

        issues = self.run_json("list")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["title"], "Ship the CLI")

    def test_list_includes_created_issue(self) -> None:
        created = self.run_json("add", "Document the commands")
        issues = self.run_json("list")
        self.assertEqual(issues[0]["id"], created["id"])
        self.assertEqual(issues[0]["title"], "Document the commands")

    def test_close_issue_and_filter_closed(self) -> None:
        self.run_json("add", "Close me")
        closed = self.run_json("close", "1")
        self.assertEqual(closed["status"], "closed")
        self.assertIsNotNone(closed["closed_at"])

        issues = self.run_json("list", "--status", "closed")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["id"], 1)

    def test_missing_issue_returns_non_zero(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "issue_tracker", "--db", str(self.db_path), "close", "999"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("issue 999 not found", result.stderr)

    def test_smtp_connection_failure_does_not_crash_cli(self) -> None:
        """SMTP接続失敗時にCLIが正常終了しJSON出力が行われることを確認する。"""
        from issue_tracker.cli import main

        smtp_env = {
            "SMTP_HOST": "localhost",
            "SMTP_FROM": "sender@example.com",
            "SMTP_TO": "recipient@example.com",
        }
        captured_stdout = io.StringIO()
        with patch.dict(os.environ, smtp_env, clear=False), \
             patch("smtplib.SMTP", side_effect=ConnectionRefusedError), \
             patch("sys.stdout", captured_stdout):
            exit_code = main(["--db", str(self.db_path), "add", "Test SMTP failure"])

        self.assertEqual(exit_code, 0)
        result = json.loads(captured_stdout.getvalue())
        self.assertEqual(result["title"], "Test SMTP failure")
        self.assertEqual(result["status"], "open")


if __name__ == "__main__":
    unittest.main()
