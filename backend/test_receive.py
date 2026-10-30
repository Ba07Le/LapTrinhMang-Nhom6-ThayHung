"""Smoke test / CLI for the receiver backend against a REAL server.

  export IMAP_USER=you@gmail.com IMAP_PASS='app password'
  python test_receive.py imap folders
  python test_receive.py imap list --page 1
  python test_receive.py imap read 123
  python test_receive.py imap attach 123 0
  python test_receive.py imap search --keyword "đồ án" --sender thay@
  python test_receive.py imap watch --interval 15
  python test_receive.py pop3 list
  python test_receive.py pop3 read <uidl>
Add --debug to see raw IMAP commands (good for Wireshark comparison).
"""
import argparse
import imaplib
import os
import sys
import time

try:
    from .imap_client import ImapClient, NewMailWatcher
    from .pop3_client import Pop3Client
    from .mail_utils import MailError
    from . import oauth_google
except ImportError:
    from imap_client import ImapClient, NewMailWatcher
    from pop3_client import Pop3Client
    from mail_utils import MailError
    import oauth_google


def show_rows(emails):
    for e in emails:
        mark = "*" if e["seen"] is False else " "
        print(f"{mark} [{e['uid']}] {e['date']} | {e['from']} | {e['subject']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("protocol", choices=["imap", "pop3"])
    ap.add_argument("cmd", choices=["folders", "list", "read", "attach", "search", "watch"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--page", type=int, default=1)
    ap.add_argument("--unseen", action="store_true")
    ap.add_argument("--keyword")
    ap.add_argument("--sender")
    ap.add_argument("--dir", default="downloads")
    ap.add_argument("--interval", type=int, default=30)
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--google", action="store_true", help="sign in with Google (IMAP only)")
    a = ap.parse_args()

    user, pw = os.environ.get("IMAP_USER"), os.environ.get("IMAP_PASS")
    g_email = g_provider = None
    if a.google:
        if a.protocol != "imap":
            sys.exit("--google works with IMAP only")
        try:
            g_email, g_provider = oauth_google.login_interactive()
        except MailError as e:
            sys.exit(f"Error: {e}")
        print("Signed in as", g_email)
    elif not (user and pw):
        sys.exit("Set IMAP_USER and IMAP_PASS (or use --google).")
    if a.debug:
        imaplib.Debug = 4
    imap_host = os.environ.get("IMAP_HOST", "imap.gmail.com")
    pop_host = os.environ.get("POP3_HOST", "pop.gmail.com")

    if a.cmd == "watch":
        if a.protocol != "imap":
            sys.exit("watch is IMAP only")
        w = NewMailWatcher(imap_host, 993, g_email or user, pw, token_provider=g_provider,
                           on_new=lambda m: (print("NEW MAIL:"), show_rows(m)),
                           on_error=lambda e: print("watcher stopped:", e), interval=a.interval)
        w.start()
        print(f"Watching INBOX every {a.interval}s, Ctrl+C to stop")
        try:
            while w.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            w.stop()
        return

    try:
        if a.google:
            c = ImapClient(imap_host).login_oauth(g_email, g_provider)
        else:
            c = (ImapClient(imap_host) if a.protocol == "imap" else Pop3Client(pop_host)).login(user, pw)
        with c:
            if a.cmd == "folders":
                print("\n".join(c.list_folders()))
            elif a.cmd == "list":
                kw = {"unseen_only": True} if a.unseen and a.protocol == "imap" else {}
                r = c.list_emails(page=a.page, **kw)
                print(f"total={r['total']} page={r['page']}")
                show_rows(r["emails"])
            elif a.cmd == "read":
                uid = int(a.args[0]) if a.protocol == "imap" else a.args[0]
                m = c.get_email(uid)
                print(f"From: {m['from']}\nTo: {m['to']}\nDate: {m['date']}\nSubject: {m['subject']}")
                print(f"Attachments: {m['attachments']}\n\n{m['body_text'] or m['body_html'][:1000]}")
            elif a.cmd == "attach":
                uid = int(a.args[0]) if a.protocol == "imap" else a.args[0]
                print("Saved to", c.download_attachment(uid, int(a.args[1]), a.dir))
            elif a.cmd == "search":
                if a.protocol != "imap":
                    sys.exit("search is IMAP only")
                show_rows(c.search(keyword=a.keyword, sender=a.sender))
    except MailError as e:
        sys.exit(f"Error: {e}")


if __name__ == "__main__":
    main()