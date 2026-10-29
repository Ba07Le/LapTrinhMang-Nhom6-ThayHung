"""Shared helpers for IMAP/POP3 receivers (parsing, TLS, saving attachments)."""
import email
import os
import re
import ssl
from email import policy


class MailError(Exception):
    """Single error type the GUI needs to catch."""


def make_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    keylog = os.environ.get("SSLKEYLOGFILE")  # lets Wireshark decrypt the TLS session
    if keylog:
        ctx.keylog_filename = keylog
    return ctx


def _content(part) -> str:
    try:
        return part.get_content()
    except (LookupError, UnicodeDecodeError):
        return (part.get_payload(decode=True) or b"").decode("utf-8", errors="replace")


def _payload(part) -> bytes:
    data = part.get_payload(decode=True)
    return data if data is not None else part.as_bytes()  # e.g. message/rfc822


def parse_headers(raw: bytes) -> dict:
    msg = email.message_from_bytes(raw, policy=policy.default)
    return {
        "from": str(msg["from"] or ""),
        "subject": str(msg["subject"] or "(no subject)"),
        "date": str(msg["date"] or ""),
    }


def parse_message(raw: bytes) -> dict:
    msg = email.message_from_bytes(raw, policy=policy.default)
    text = msg.get_body(preferencelist=("plain",))
    html = msg.get_body(preferencelist=("html",))
    attachments = []
    for i, part in enumerate(msg.iter_attachments()):
        attachments.append({
            "index": i,
            "filename": part.get_filename() or f"attachment_{i}",
            "content_type": part.get_content_type(),
            "size": len(_payload(part)),
        })
    return {
        "from": str(msg["from"] or ""),
        "to": str(msg["to"] or ""),
        "cc": str(msg["cc"] or ""),
        "subject": str(msg["subject"] or "(no subject)"),
        "date": str(msg["date"] or ""),
        "message_id": str(msg["message-id"] or ""),
        "body_text": _content(text) if text else "",
        "body_html": _content(html) if html else "",
        "attachments": attachments,
    }


def extract_attachment(raw: bytes, index: int) -> tuple[str, bytes]:
    msg = email.message_from_bytes(raw, policy=policy.default)
    parts = list(msg.iter_attachments())
    if not 0 <= index < len(parts):
        raise MailError(f"No attachment with index {index} (message has {len(parts)})")
    part = parts[index]
    return part.get_filename() or f"attachment_{index}", _payload(part)


def save_bytes(save_dir: str, filename: str, data: bytes) -> str:
    """Save safely: strips path parts, never overwrites an existing file."""
    os.makedirs(save_dir, exist_ok=True)
    name = re.sub(r'[\\/:*?"<>|]', "_", os.path.basename(filename)).lstrip(".") or "attachment"
    base, ext = os.path.splitext(name)
    path, n = os.path.join(save_dir, name), 1
    while os.path.exists(path):
        path = os.path.join(save_dir, f"{base}_{n}{ext}")
        n += 1
    with open(path, "wb") as f:
        f.write(data)
    return path
