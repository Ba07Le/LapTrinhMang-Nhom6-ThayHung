"""SMTP transport for Gmail: STARTTLS + App Password or OAuth2 XOAUTH2."""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from typing import Callable, Iterable

try:
    from .mail_utils import MailError, make_ssl_context
except ImportError:  # running as a plain script
    from mail_utils import MailError, make_ssl_context


class SMTPClient:
    def __init__(self, host: str = "smtp.gmail.com", port: int = 587, timeout: int = 30):
        self.host = host
        self.port = port
        self.timeout = timeout

    def send(
        self,
        sender: str,
        recipients: Iterable[str],
        message: EmailMessage,
        *,
        password: str | None = None,
        token_provider: Callable[[], str] | None = None,
    ) -> dict:
        if bool(password) == bool(token_provider):
            raise MailError("SMTP cần đúng một phương thức xác thực: App Password hoặc OAuth2.")

        recipient_list = list(recipients)
        try:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as smtp:
                smtp.ehlo()
                smtp.starttls(context=make_ssl_context())
                smtp.ehlo()

                if token_provider:
                    access_token = token_provider()
                    if not access_token:
                        raise MailError("Google không cấp Access Token hợp lệ cho SMTP.")
                    auth_string = f"user={sender}\x01auth=Bearer {access_token}\x01\x01"
                    def xoauth2_response(challenge=None):
                        # Gmail sends an error challenge (334) on failure; answer once with empty data.
                        return auth_string if challenge is None else ""
                    smtp.auth("XOAUTH2", xoauth2_response)
                else:
                    smtp.login(sender, password)

                refused = smtp.send_message(message, from_addr=sender, to_addrs=recipient_list)
                accepted = [address for address in recipient_list if address not in refused]
                return {
                    "accepted": accepted,
                    "refused": refused,
                    "message_id": str(message.get("Message-ID", "")),
                }

        except MailError:
            raise
        except smtplib.SMTPAuthenticationError as exc:
            raise MailError(
                "SMTP xác thực thất bại. Với OAuth, hãy cấp quyền Gmail cho tài khoản và đăng nhập lại; "
                "với App Password, kiểm tra mật khẩu ứng dụng. Chi tiết: " + str(exc)
            ) from exc
        except smtplib.SMTPRecipientsRefused as exc:
            refused = ", ".join(exc.recipients.keys())
            raise MailError(f"Gmail từ chối tất cả địa chỉ người nhận: {refused}") from exc
        except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, OSError, ssl.SSLError) as exc:
            raise MailError(f"Không kết nối được Gmail SMTP ({self.host}:{self.port}): {exc}") from exc
        except smtplib.SMTPException as exc:
            raise MailError(f"Lỗi giao thức SMTP: {exc}") from exc
