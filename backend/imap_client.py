"""IMAP receiver backend (folders, paged inbox, read, attachments, search, new-mail polling)."""
import imaplib
import re
import ssl
import threading

try:
    from . import mail_utils as mu
except ImportError:  # running as a plain script
    import mail_utils as mu

MailError = mu.MailError
_HDR_SPEC = "(UID FLAGS BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])"


class ImapClient:
    """One instance = one connection. imaplib is NOT thread-safe: don't share across threads."""

    def __init__(self, host="imap.gmail.com", port=993, timeout=20):
        self.host, self.port, self.timeout = host, port, timeout
        self.conn = None

    # ---- connection -------------------------------------------------
    def login(self, user: str, password: str) -> "ImapClient":
        try:
            self.conn = imaplib.IMAP4_SSL(self.host, self.port,
                                          ssl_context=mu.make_ssl_context(), timeout=self.timeout)
            self.conn.login(user, password)
        except imaplib.IMAP4.error as e:
            self.logout()
            raise MailError(f"IMAP login failed: {e}") from e
        except (OSError, ssl.SSLError) as e:
            raise MailError(f"Cannot connect to {self.host}:{self.port}: {e}") from e
        return self

    def logout(self):
        if self.conn:
            try:
                self.conn.logout()
            except Exception:
                pass
            self.conn = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.logout()

    # ---- internals --------------------------------------------------
    def _select(self, folder: str, readonly=True):
        typ, _ = self.conn.select(f'"{folder}"', readonly=readonly)
        if typ != "OK":
            raise MailError(f"Cannot open folder: {folder}")

    def _search(self, *criteria) -> list[int]:
        typ, data = self.conn.uid("SEARCH", *criteria)
        return [int(x) for x in data[0].split()] if typ == "OK" and data and data[0] else []

    def _search_text(self, key: str, value: str) -> list[int]:
        self.conn.literal = value.encode("utf-8")  # sent as IMAP literal -> Vietnamese works
        return self._search("CHARSET", "UTF-8", key)

    def _fetch_headers(self, uids: list[int]) -> list[dict]:
        if not uids:
            return []
        typ, data = self.conn.uid("FETCH", ",".join(map(str, uids)), _HDR_SPEC)
        if typ != "OK":
            raise MailError("FETCH headers failed")
        out = []
        for i, item in enumerate(data):
            if not isinstance(item, tuple):
                continue
            tail = data[i + 1] if i + 1 < len(data) and isinstance(data[i + 1], bytes) else b""
            meta = (item[0] + b" " + tail).decode(errors="replace")  # UID/FLAGS may come after literal
            uid = int(re.search(r"UID (\d+)", meta).group(1))
            flags = re.search(r"FLAGS \(([^)]*)\)", meta)
            out.append({"uid": uid, "seen": "\\Seen" in (flags.group(1) if flags else ""),
                        **mu.parse_headers(item[1])})
        return sorted(out, key=lambda e: e["uid"], reverse=True)

    def _fetch_raw(self, uid: int, folder: str) -> bytes:
        self._select(folder)
        typ, data = self.conn.uid("FETCH", str(uid), "(BODY.PEEK[])")
        for item in data or []:
            if isinstance(item, tuple):
                return item[1]
        raise MailError(f"Message UID {uid} not found in {folder}")

    # ---- public API (what the GUI calls) -----------------------------
    def list_folders(self) -> list[str]:
        _, data = self.conn.list()
        names = []
        for line in data:
            if not isinstance(line, bytes):
                continue
            m = re.match(rb'\((.*?)\) "(.*?)" (.+)', line)
            if m and b"\\Noselect" not in m.group(1):
                names.append(m.group(3).strip(b'"').decode(errors="replace"))
        return names

    def list_emails(self, folder="INBOX", page=1, page_size=20, unseen_only=False) -> dict:
        self._select(folder)
        uids = sorted(self._search("UNSEEN" if unseen_only else "ALL"), reverse=True)
        start = (page - 1) * page_size
        return {"total": len(uids), "page": page,
                "emails": self._fetch_headers(uids[start:start + page_size])}

    def get_email(self, uid: int, folder="INBOX") -> dict:
        return {"uid": uid, **mu.parse_message(self._fetch_raw(uid, folder))}

    def download_attachment(self, uid: int, index: int, save_dir="downloads", folder="INBOX") -> str:
        filename, data = mu.extract_attachment(self._fetch_raw(uid, folder), index)
        return mu.save_bytes(save_dir, filename, data)

    def mark_seen(self, uid: int, folder="INBOX"):
        self._select(folder, readonly=False)
        self.conn.uid("STORE", str(uid), "+FLAGS", "(\\Seen)")

    def search(self, keyword=None, sender=None, folder="INBOX", limit=50) -> list[dict]:
        self._select(folder)
        found = []
        if keyword:
            found.append(set(self._search_text("TEXT", keyword)))
        if sender:
            found.append(set(self._search_text("FROM", sender)))
        if not found:
            return []
        uids = sorted(set.intersection(*found), reverse=True)[:limit]
        return self._fetch_headers(uids)

    def latest_uid(self, folder="INBOX") -> int:
        self._select(folder)
        return max(self._search("ALL"), default=0)

    def poll_new(self, folder="INBOX", last_uid=0) -> list[dict]:
        self._select(folder)
        uids = [u for u in self._search("UID", f"{last_uid + 1}:*") if u > last_uid]
        return self._fetch_headers(sorted(uids, reverse=True))


class NewMailWatcher(threading.Thread):
    """Background polling for the 'new mail notification' feature.
    Uses its OWN connection; calls on_new(list_of_headers) from the worker thread
    (in Tkinter use root.after / a queue to hop back to the UI thread)."""

    def __init__(self, host, port, user, password, on_new, on_error=None, folder="INBOX", interval=30):
        super().__init__(daemon=True)
        self.args = (host, port, user, password)
        self.on_new, self.on_error = on_new, on_error
        self.folder, self.interval = folder, interval
        self._stop_evt = threading.Event()

    def stop(self):
        self._stop_evt.set()

    def run(self):
        host, port, user, password = self.args
        try:
            with ImapClient(host, port).login(user, password) as c:
                last = c.latest_uid(self.folder)
                while not self._stop_evt.wait(self.interval):
                    new = c.poll_new(self.folder, last)
                    if new:
                        last = new[0]["uid"]
                        self.on_new(new)
        except Exception as e:
            if self.on_error:
                self.on_error(e)