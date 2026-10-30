"""Application service: validate, build MIME email and send through SMTP."""
from __future__ import annotations

import html
import mimetypes
import re
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import getaddresses, make_msgid
from pathlib import Path
from typing import Callable, Iterable

try:
    from .mail_utils import MailError
    from .smtp_client import SMTPClient
except ImportError:  # running as a plain script
    from mail_utils import MailError
    from smtp_client import SMTPClient

_EMAIL_RE = re.compile(r"^[^\s@<>;,]+@[^\s@<>;,]+\.[^\s@<>;,]+$")
MAX_TOTAL_ATTACHMENT_BYTES = 18 * 1024 * 1024  # leave room for MIME/base64 overhead under Gmail's limit


def _parse_addresses(value: str | Iterable[str], field_name: str) -> list[str]:
    if isinstance(value, str):
        raw = value.replace(";", ",")
    else:
        raw = ",".join(str(item) for item in value)
    pairs = getaddresses([raw])
    addresses = [address.strip() for _name, address in pairs if address.strip()]
    if not addresses:
        raise MailError(f"Bạn chưa nhập địa chỉ {field_name}.")
    invalid = [address for address in addresses if not _EMAIL_RE.fullmatch(address)]
    if invalid:
        raise MailError("Địa chỉ email không hợp lệ: " + ", ".join(invalid))
    # Preserve order while removing duplicates (case-insensitive).
    unique = []
    seen = set()
    for address in addresses:
        key = address.casefold()
        if key not in seen:
            seen.add(key)
            unique.append(address)
    return unique


def _safe_header(value: str, field_name: str) -> str:
    value = str(value or "").strip()
    if "\r" in value or "\n" in value:
        raise MailError(f"Trường {field_name} không được chứa ký tự xuống dòng.")
    return value


def build_message(sender: str, recipients: str, subject: str, body: str,
                  attachments: Iterable[str] = (), cc: str = "") -> tuple[EmailMessage, list[str]]:
    sender = sender.strip()
    if not _EMAIL_RE.fullmatch(sender):
        raise MailError("Địa chỉ Gmail người gửi không hợp lệ.")

    to_list = _parse_addresses(recipients, "người nhận")
    cc_list = _parse_addresses(cc, "CC") if cc.strip() else []
    all_recipients = list(dict.fromkeys(to_list + cc_list))
    subject = _safe_header(subject, "tiêu đề")
    if not subject:
        raise MailError("Bạn chưa nhập tiêu đề email.")

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg["Subject"] = subject
    msg["Date"] = datetime.now(timezone.utc).astimezone().strftime("%a, %d %b %Y %H:%M:%S %z")
    msg["Message-ID"] = make_msgid()
    plain_body = body or " "
    msg.set_content(plain_body)
    # The compose screen is plain text; include a safe HTML alternative so HTML-capable clients
    # render line breaks cleanly without interpreting user-entered text as markup.
    html_body = "<html><body><div style=\"white-space:pre-wrap;font-family:Arial,sans-serif\">" + html.escape(plain_body) + "</div></body></html>"
    msg.add_alternative(html_body, subtype="html")

    total_size = 0
    for raw_path in attachments or ():
        path = Path(raw_path).expanduser()
        if not path.is_file():
            raise MailError(f"Không tìm thấy tệp đính kèm: {path.name}")
        size = path.stat().st_size
        total_size += size
        if total_size > MAX_TOTAL_ATTACHMENT_BYTES:
            raise MailError("Tổng dung lượng tệp đính kèm vượt quá 18 MB. Vui lòng chọn ít tệp hơn.")
        content_type, _encoding = mimetypes.guess_type(path.name)
        if not content_type:
            content_type = "application/octet-stream"
        maintype, subtype = content_type.split("/", 1)
        try:
            data = path.read_bytes()
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=path.name)
        except OSError as exc:
            raise MailError(f"Không đọc được tệp đính kèm {path.name}: {exc}") from exc

    return msg, all_recipients


def send_email(*, sender: str, to: str, subject: str, body: str,
               attachments: Iterable[str] = (), password: str | None = None,
               token_provider: Callable[[], str] | None = None,
               cc: str = "", smtp_client: SMTPClient | None = None) -> dict:
    """Send one email. Gmail SMTP acceptance is not a guarantee of inbox placement."""
    message, recipients = build_message(sender, to, subject, body, attachments, cc)
    client = smtp_client or SMTPClient()
    return client.send(sender, recipients, message, password=password, token_provider=token_provider)
