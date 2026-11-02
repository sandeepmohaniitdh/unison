"""Sending email. Only the worker sends, from the email outbox.

Locally the SMTP server is Mailpit, which catches every message
(inbox at http://localhost:8025). On a real server, set SMTP_HOST, SMTP_PORT,
SMTP_USERNAME, SMTP_PASSWORD and SMTP_STARTTLS for a mail service. Tests use FakeMailer.
"""

import smtplib
from email.message import EmailMessage


class Mailer:
    def send(self, to: str, subject: str, body: str) -> None:
        raise NotImplementedError


class SmtpMailer(Mailer):
    def __init__(
        self, host: str, port: int, sender: str, username: str = "", password: str = "", starttls: bool = False
    ):
        self.host = host
        self.port = port
        self.sender = sender
        self.username = username
        self.password = password
        self.starttls = starttls

    def send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = self.sender
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
            if self.starttls:
                smtp.starttls()
            if self.username:
                smtp.login(self.username, self.password)
            smtp.send_message(msg)


class FakeMailer(Mailer):
    def __init__(self):
        self.sent: list[dict] = []

    def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body})
