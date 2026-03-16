"""Tests for the EmailNotifier.

NOTE: These tests verify configuration and message construction only.
Actual SMTP delivery requires a real SMTP server that is not available in the
test environment.  End-to-end delivery tests must be run against a live SMTP
host with SMTP_HOST, SMTP_PORT, SMTP_FROM, SMTP_TO, and (optionally)
SMTP_USERNAME / SMTP_PASSWORD set in the environment.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from issue_tracker.notifier import EmailNotifier


class TestEmailNotifierFromEnv(unittest.TestCase):
    def test_returns_none_when_smtp_host_unset(self) -> None:
        env = {k: v for k, v in os.environ.items() if not k.startswith("SMTP_")}
        with patch.dict(os.environ, env, clear=True):
            self.assertIsNone(EmailNotifier.from_env())

    def test_returns_notifier_when_smtp_host_set(self) -> None:
        with patch.dict(
            os.environ,
            {"SMTP_HOST": "mail.example.com", "SMTP_FROM": "a@example.com", "SMTP_TO": "b@example.com"},
            clear=False,
        ):
            notifier = EmailNotifier.from_env()
        self.assertIsNotNone(notifier)
        assert notifier is not None
        self.assertEqual(notifier.host, "mail.example.com")
        self.assertEqual(notifier.from_addr, "a@example.com")
        self.assertEqual(notifier.to_addr, "b@example.com")
        self.assertEqual(notifier.port, 25)
        self.assertFalse(notifier.use_tls)

    def test_custom_port_and_tls(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SMTP_HOST": "smtp.example.com",
                "SMTP_PORT": "465",
                "SMTP_FROM": "a@example.com",
                "SMTP_TO": "b@example.com",
                "SMTP_TLS": "true",
            },
            clear=False,
        ):
            notifier = EmailNotifier.from_env()
        assert notifier is not None
        self.assertEqual(notifier.port, 465)
        self.assertTrue(notifier.use_tls)

    def test_username_and_password(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SMTP_HOST": "smtp.example.com",
                "SMTP_FROM": "a@example.com",
                "SMTP_TO": "b@example.com",
                "SMTP_USERNAME": "user",
                "SMTP_PASSWORD": "secret",
            },
            clear=False,
        ):
            notifier = EmailNotifier.from_env()
        assert notifier is not None
        self.assertEqual(notifier.username, "user")
        self.assertEqual(notifier.password, "secret")

    def test_empty_username_treated_as_none(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SMTP_HOST": "smtp.example.com",
                "SMTP_FROM": "a@example.com",
                "SMTP_TO": "b@example.com",
                "SMTP_USERNAME": "",
                "SMTP_PASSWORD": "",
            },
            clear=False,
        ):
            notifier = EmailNotifier.from_env()
        assert notifier is not None
        self.assertIsNone(notifier.username)
        self.assertIsNone(notifier.password)


class TestEmailNotifierMessageContent(unittest.TestCase):
    """Verify subject and body content by intercepting smtplib.SMTP."""

    def _make_notifier(self) -> EmailNotifier:
        return EmailNotifier(
            host="localhost",
            port=25,
            from_addr="tracker@example.com",
            to_addr="team@example.com",
        )

    def _capture_sent_message(self, notifier: EmailNotifier, method_name: str, issue: dict) -> object:
        """Call notifier.<method_name>(issue) with SMTP patched; return the sent EmailMessage."""
        sent: list = []

        mock_smtp_instance = MagicMock()
        mock_smtp_instance.__enter__ = lambda s: s
        mock_smtp_instance.__exit__ = MagicMock(return_value=False)
        mock_smtp_instance.send_message.side_effect = lambda msg: sent.append(msg)

        with patch("smtplib.SMTP", return_value=mock_smtp_instance):
            getattr(notifier, method_name)(issue)

        self.assertEqual(len(sent), 1, "Expected exactly one message to be sent")
        return sent[0]

    def test_notify_created_subject_contains_id_and_title(self) -> None:
        issue = {
            "id": 7,
            "title": "Fix login bug",
            "status": "open",
            "created_at": "2026-03-16T00:00:00+00:00",
            "closed_at": None,
        }
        msg = self._capture_sent_message(self._make_notifier(), "notify_created", issue)
        self.assertIn("7", msg["Subject"])
        self.assertIn("Fix login bug", msg["Subject"])
        self.assertIn("created", msg["Subject"].lower())

    def test_notify_created_body_contains_fields(self) -> None:
        issue = {
            "id": 3,
            "title": "Add search",
            "status": "open",
            "created_at": "2026-03-16T00:00:00+00:00",
            "closed_at": None,
        }
        msg = self._capture_sent_message(self._make_notifier(), "notify_created", issue)
        body = msg.get_content()
        self.assertIn("Add search", body)
        self.assertIn("open", body)
        self.assertIn("2026-03-16T00:00:00+00:00", body)

    def test_notify_closed_subject_contains_id_and_title(self) -> None:
        issue = {
            "id": 2,
            "title": "Remove old code",
            "status": "closed",
            "created_at": "2026-03-15T00:00:00+00:00",
            "closed_at": "2026-03-16T01:00:00+00:00",
        }
        msg = self._capture_sent_message(self._make_notifier(), "notify_closed", issue)
        self.assertIn("2", msg["Subject"])
        self.assertIn("Remove old code", msg["Subject"])
        self.assertIn("closed", msg["Subject"].lower())

    def test_notify_closed_body_contains_closed_at(self) -> None:
        issue = {
            "id": 5,
            "title": "Deploy fix",
            "status": "closed",
            "created_at": "2026-03-14T00:00:00+00:00",
            "closed_at": "2026-03-16T02:00:00+00:00",
        }
        msg = self._capture_sent_message(self._make_notifier(), "notify_closed", issue)
        body = msg.get_content()
        self.assertIn("2026-03-16T02:00:00+00:00", body)

    def test_from_and_to_headers_are_set(self) -> None:
        issue = {
            "id": 1,
            "title": "Test headers",
            "status": "open",
            "created_at": "2026-03-16T00:00:00+00:00",
            "closed_at": None,
        }
        notifier = self._make_notifier()
        msg = self._capture_sent_message(notifier, "notify_created", issue)
        self.assertEqual(msg["From"], "tracker@example.com")
        self.assertEqual(msg["To"], "team@example.com")


class TestEmailNotifierTlsPath(unittest.TestCase):
    """Verify that SMTP_SSL is used when use_tls=True."""

    def test_tls_uses_smtp_ssl(self) -> None:
        notifier = EmailNotifier(
            host="smtp.example.com",
            port=465,
            from_addr="a@example.com",
            to_addr="b@example.com",
            use_tls=True,
        )
        issue = {
            "id": 1,
            "title": "TLS test",
            "status": "open",
            "created_at": "2026-03-16T00:00:00+00:00",
            "closed_at": None,
        }
        mock_smtp_ssl = MagicMock()
        mock_smtp_ssl.__enter__ = lambda s: s
        mock_smtp_ssl.__exit__ = MagicMock(return_value=False)

        with patch("smtplib.SMTP_SSL", return_value=mock_smtp_ssl) as patched_ssl, \
             patch("smtplib.SMTP") as patched_plain:
            notifier.notify_created(issue)

        patched_ssl.assert_called_once_with("smtp.example.com", 465)
        patched_plain.assert_not_called()


if __name__ == "__main__":
    unittest.main()
