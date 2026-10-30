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
        self._cred = None   # remembered so reconnect() can log in again

    # ---- connection -------------------------------------------------
    def login(self, user: str, password: str) -> "ImapClient":
        self._cred = ("pw", user, password)
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

    def login_oauth(self, user: str, token_provider) -> "ImapClient":
        """Gmail OAuth2 (XOAUTH2). token_provider() must return a fresh access token."""
        self._cred = ("oauth", user, token_provider)
        try:
            auth = f"user={user}\x01auth=Bearer {token_provider()}\x01\x01".encode()
            sent = []

            def responder(_challenge):
                if sent:          # server answered with an error challenge -> end the exchange
                    return b""
                sent.append(1)
                return auth

            self.conn = imaplib.IMAP4_SSL(self.host, self.port,
                                          ssl_context=mu.make_ssl_context(), timeout=self.timeout)
            self.conn.authenticate("XOAUTH2", responder)
        except imaplib.IMAP4.error as e:
            self.logout()
            raise MailError(f"IMAP OAuth sign-in failed: {e}") from e
        except (OSError, ssl.SSLError) as e:
            raise MailError(f"Cannot connect to {self.host}:{self.port}: {e}") from e
        return self

    def reconnect(self) -> "ImapClient":
        """Log in again with whatever was used before (password or Google)."""
        self.logout()
        kind, user, secret = self._cred
        return self.login(user, secret) if kind == "pw" else self.login_oauth(user, secret)

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
    def _select(self, folder: str, readonly=True) -> int:
        """Open a folder; returns how many messages it holds."""
        typ, data = self.conn.select(f'"{folder}"', readonly=readonly)
        if typ != "OK":
            raise MailError(f"Cannot open folder: {folder}")
        try:
            return int(data[0])
        except (TypeError, ValueError, IndexError):
            return 0

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
        return self._parse_header_rows(typ, data)

    def _fetch_headers_seq(self, lo: int, hi: int) -> list[dict]:
        typ, data = self.conn.fetch(f"{lo}:{hi}", _HDR_SPEC)
        return self._parse_header_rows(typ, data)

    def _parse_header_rows(self, typ, data) -> list[dict]:
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

    def special_folders(self) -> dict:
        """{'sent': name, 'drafts': name, 'all': name} from IMAP special-use flags (any Gmail language)."""
        _, data = self.conn.list()
        found = {}
        for line in data:
            if not isinstance(line, bytes):
                continue
            m = re.match(rb'\((.*?)\) "(.*?)" (.+)', line)
            if not m:
                continue
            flags = m.group(1).lower().split()
            name = m.group(3).strip(b'"').decode(errors="replace")
            for key, flag in (("sent", b"\\sent"), ("drafts", b"\\drafts"), ("all", b"\\all")):
                if flag in flags:
                    found[key] = name
        return found

    def list_emails(self, folder="INBOX", page=1, page_size=20, unseen_only=False) -> dict:
        total = self._select(folder)
        if unseen_only:
            uids = sorted(self._search("UNSEEN"), reverse=True)
            start = (page - 1) * page_size
            return {"total": len(uids), "page": page,
                    "emails": self._fetch_headers(uids[start:start + page_size])}
        # Newest first = highest message numbers. Fetch ONLY this page's range, so a mailbox
        # with thousands of mails costs the same as one with a few dozen.
        hi = total - (page - 1) * page_size
        lo = max(1, hi - page_size + 1)
        emails = self._fetch_headers_seq(lo, hi) if hi >= 1 else []
        return {"total": total, "page": page, "emails": emails}

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

    def __init__(self, host, port, user, password, on_new, on_error=None, folder="INBOX", interval=30,
                 token_provider=None):
        super().__init__(daemon=True)
        self.token_provider = token_provider   # set for Google login (password is then ignored)
        self.args = (host, port, user, password)
        self.on_new, self.on_error = on_new, on_error
        self.folder, self.interval = folder, interval
        self._stop_evt = threading.Event()

    def stop(self):
        self._stop_evt.set()

    def _connect(self) -> "ImapClient":
        host, port, user, password = self.args
        c = ImapClient(host, port)
        return c.login_oauth(user, self.token_provider) if self.token_provider else c.login(user, password)

    def run(self):
        last = None
        while not self._stop_evt.is_set():
            try:
                with self._connect() as c:
                    if last is None:
                        last = c.latest_uid(self.folder)
                    while not self._stop_evt.wait(self.interval):
                        new = c.poll_new(self.folder, last)
                        if new:
                            last = new[0]["uid"]
                            self.on_new(new)
                return
            except Exception as e:   # network drop, expired session... -> report, retry in a minute
                if self.on_error:
                    self.on_error(e)
                if self._stop_evt.wait(60):
                    return