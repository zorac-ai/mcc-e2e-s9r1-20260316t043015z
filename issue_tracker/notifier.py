from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Any


class EmailNotifier:
    """Send email notifications via SMTP when issues are created or closed.

    Configuration is read from environment variables:
      SMTP_HOST     - SMTP server hostname (required to enable notifications)
      SMTP_PORT     - SMTP server port (default: 25)
      SMTP_FROM     - Sender address (required)
      SMTP_TO       - Recipient address (required)
      SMTP_USERNAME - SMTP authentication username (optional)
      SMTP_PASSWORD - SMTP authentication password (optional)
      SMTP_TLS      - Use SMTP_SSL when set to '1', 'true', or 'yes' (optional)

    NOTE: Actual delivery requires a real SMTP server. No mock SMTP is used.
    """

    def __init__(
        self,
        host: str,
        port: int,
        from_addr: str,
        to_addr: str,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.from_addr = from_addr
        self.to_addr = to_addr
        self.username = username
        self.password = password
        self.use_tls = use_tls

    @classmethod
    def from_env(cls) -> EmailNotifier | None:
        """Create an EmailNotifier from environment variables.

        Returns None when SMTP_HOST is not set (notifications disabled).
        """
        host = os.environ.get("SMTP_HOST")
        if not host:
            return None
        return cls(
            host=host,
            port=int(os.environ.get("SMTP_PORT", "25")),
            from_addr=os.environ.get("SMTP_FROM", ""),
            to_addr=os.environ.get("SMTP_TO", ""),
            username=os.environ.get("SMTP_USERNAME") or None,
            password=os.environ.get("SMTP_PASSWORD") or None,
            use_tls=os.environ.get("SMTP_TLS", "").lower() in ("1", "true", "yes"),
        )

    def notify_created(self, issue: dict[str, Any]) -> None:
        """Send an email notification when an issue is created."""
        subject = f"[issue_tracker] Issue #{issue['id']} created: {issue['title']}"
        body = (
            f"Issue #{issue['id']} has been created.\n\n"
            f"Title:      {issue['title']}\n"
            f"Status:     {issue['status']}\n"
            f"Created at: {issue['created_at']}\n"
        )
        self._send(subject, body)

    def notify_closed(self, issue: dict[str, Any]) -> None:
        """Send an email notification when an issue is closed."""
        subject = f"[issue_tracker] Issue #{issue['id']} closed: {issue['title']}"
        body = (
            f"Issue #{issue['id']} has been closed.\n\n"
            f"Title:      {issue['title']}\n"
            f"Status:     {issue['status']}\n"
            f"Closed at:  {issue['closed_at']}\n"
        )
        self._send(subject, body)

    def _send(self, subject: str, body: str) -> None:
        """Connect to the SMTP server and send a plain-text email."""
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = self.to_addr
        msg.set_content(body)

        smtp_class = smtplib.SMTP_SSL if self.use_tls else smtplib.SMTP
        with smtp_class(self.host, self.port) as smtp:
            if self.username and self.password:
                smtp.login(self.username, self.password)
            smtp.send_message(msg)
