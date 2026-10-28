"""Sending email. Only the worker sends, from the email outbox.

Locally the SMTP server is Mailpit, which catches every message
(inbox at http://localhost:8025). Tests use FakeMailer.
"""

import smtplib
from email.message import EmailMessage


class Mailer:
    def send(self, to: str, subject: str, body: str) -> None:
        raise NotImplementedError


class SmtpMailer(Mailer):
    def __init__(self, host: str, port: int, sender: str):
        self.host = host
        self.port = port
        self.sender = sender

    def send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = self.sender
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
            smtp.send_message(msg)


class FakeMailer(Mailer):
    def __init__(self):
        self.sent: list[dict] = []

    def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body})
