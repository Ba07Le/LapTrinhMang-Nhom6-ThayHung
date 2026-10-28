"""POP3 receiver backend. POP3 has no folders, no read/unread flags, no server-side search."""
import poplib
import ssl

try:
    from . import mail_utils as mu
except ImportError:
    import mail_utils as mu

MailError = mu.MailError


class Pop3Client:
    def __init__(self, host="pop.gmail.com", port=995, timeout=20):
        self.host, self.port, self.timeout = host, port, timeout
        self.conn = None

    def login(self, user: str, password: str) -> "Pop3Client":
        try:
            self.conn = poplib.POP3_SSL(self.host, self.port,
                                        context=mu.make_ssl_context(), timeout=self.timeout)
            self.conn.user(user)
            self.conn.pass_(password)
        except poplib.error_proto as e:
            self.logout()
            raise MailError(f"POP3 login failed: {e}") from e
        except (OSError, ssl.SSLError) as e:
            raise MailError(f"Cannot connect to {self.host}:{self.port}: {e}") from e
        return self

    def logout(self):
        if self.conn:
            try:
                self.conn.quit()
            except Exception:
                pass
            self.conn = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.logout()

    def _uidl(self) -> list[tuple[int, str]]:
        """[(message_number, stable_uid)] ascending. Numbers only live for one session; UIDL is stable."""
        _, lines, _ = self.conn.uidl()
        pairs = [l.decode().split() for l in lines]
        return [(int(n), uid) for n, uid in pairs]

    def _number_of(self, uid: str) -> int:
        for num, u in self._uidl():
            if u == uid:
                return num
        raise MailError(f"Message {uid} not found")

    def _raw(self, uid: str) -> bytes:
        _, lines, _ = self.conn.retr(self._number_of(uid))
        return b"\r\n".join(lines)

    def list_emails(self, page=1, page_size=20) -> dict:
        items = self._uidl()[::-1]  # newest first
        start = (page - 1) * page_size
        emails = []
        for num, uid in items[start:start + page_size]:
            _, lines, _ = self.conn.top(num, 0)  # headers only
            emails.append({"uid": uid, "seen": None, **mu.parse_headers(b"\r\n".join(lines))})
        return {"total": len(items), "page": page, "emails": emails}

    def get_email(self, uid: str) -> dict:
        return {"uid": uid, **mu.parse_message(self._raw(uid))}

    def download_attachment(self, uid: str, index: int, save_dir="downloads") -> str:
        filename, data = mu.extract_attachment(self._raw(uid), index)
        return mu.save_bytes(save_dir, filename, data)
