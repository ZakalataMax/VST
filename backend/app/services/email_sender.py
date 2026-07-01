from __future__ import annotations

import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@dataclass
class SmtpConfig:
    host: str
    port: int
    tls: str
    user: str
    password: str
    sender: str
    recipients: list[str]
    subject: str

    @classmethod
    def from_env(cls) -> "SmtpConfig | None":
        host = os.getenv("SMTP_HOST", "").strip()
        recipients = [
            part.strip()
            for part in os.getenv("REPORT_EMAIL_TO", "").split(",")
            if part.strip()
        ]
        if not host or not recipients:
            return None
        user = os.getenv("SMTP_USER", "").strip()
        sender = os.getenv("REPORT_EMAIL_FROM", "").strip() or user
        try:
            port = int(os.getenv("SMTP_PORT", "587") or 587)
        except ValueError:
            port = 587
        return cls(
            host=host,
            port=port,
            tls=os.getenv("SMTP_TLS", "starttls").strip().lower() or "starttls",
            user=user,
            password=os.getenv("SMTP_PASS", ""),
            sender=sender,
            recipients=recipients,
            subject=os.getenv("REPORT_EMAIL_SUBJECT", "VST daily report").strip()
            or "VST daily report",
        )


def build_message(
    config: SmtpConfig,
    *,
    body: str,
    attachment_path: str | Path | None,
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = config.sender
    message["To"] = ", ".join(config.recipients)
    message["Subject"] = config.subject
    message.set_content(body)
    if attachment_path:
        path = Path(attachment_path)
        message.add_attachment(
            path.read_bytes(),
            maintype="application",
            subtype=XLSX_MIME.split("/", 1)[1],
            filename=path.name,
        )
    return message


def send_report_email(
    config: SmtpConfig,
    *,
    body: str,
    attachment_path: str | Path | None,
) -> None:
    message = build_message(config, body=body, attachment_path=attachment_path)
    if config.tls == "ssl":
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(config.host, config.port, context=context) as server:
            if config.user:
                server.login(config.user, config.password)
            server.send_message(message)
        return
    with smtplib.SMTP(config.host, config.port) as server:
        if config.tls == "starttls":
            server.starttls(context=ssl.create_default_context())
        if config.user:
            server.login(config.user, config.password)
        server.send_message(message)
