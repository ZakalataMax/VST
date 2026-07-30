from __future__ import annotations

from pathlib import Path

MAIL_ITEM = 0


def outlook_available() -> bool:
    try:
        import win32com.client  # noqa: F401
    except Exception:
        return False
    return True


def send_via_outlook(
    *,
    recipients: list[str],
    subject: str,
    body: str,
    attachment_path: str | Path | None,
) -> None:
    import pythoncom
    import win32com.client as win32

    pythoncom.CoInitialize()
    try:
        try:
            outlook = win32.GetActiveObject("Outlook.Application")
        except Exception:
            outlook = win32.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(MAIL_ITEM)
        mail.To = "; ".join(recipients)
        mail.Subject = subject
        mail.Body = body
        if attachment_path:
            mail.Attachments.Add(str(Path(attachment_path).resolve()))
        mail.Send()
    finally:
        pythoncom.CoUninitialize()
