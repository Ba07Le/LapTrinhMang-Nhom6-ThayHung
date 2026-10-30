"""Google sign-in (OAuth2) for Gmail IMAP via XOAUTH2 - no app password needed.

Setup once: put the OAuth client file (type "Desktop app") next to the repo root as
client_secret.json (or set GOOGLE_CLIENT_SECRET_FILE). The login is saved in
~/.smartmail/token.json, so after the first browser sign-in the app logs in silently.
"""
import base64
import json
import os
import threading

try:
    from . import mail_utils as mu
except ImportError:
    import mail_utils as mu

MailError = mu.MailError

SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://mail.google.com/"]
TOKEN_DIR = os.path.join(os.path.expanduser("~"), ".smartmail")
TOKEN_FILE = os.path.join(TOKEN_DIR, "token.json")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_lock = threading.RLock()


def _client_file() -> str:
    return os.environ.get("GOOGLE_CLIENT_SECRET_FILE") or os.path.join(_ROOT, "client_secret.json")


def saved_email():
    """Email of the saved Google login, or None (does not need the google libraries)."""
    try:
        with open(TOKEN_FILE, encoding="utf-8") as f:
            return json.load(f).get("email")
    except (OSError, ValueError):
        return None


def sign_out():
    try:
        os.remove(TOKEN_FILE)
    except OSError:
        pass


def _load():
    try:
        from google.oauth2.credentials import Credentials
        with open(TOKEN_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return Credentials.from_authorized_user_info(data, SCOPES), data.get("email")
    except Exception:
        return None, None


def _save(creds, email):
    os.makedirs(TOKEN_DIR, exist_ok=True)
    data = json.loads(creds.to_json())
    data["email"] = email
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)
    try:
        os.chmod(TOKEN_FILE, 0o600)
    except OSError:
        pass


def _usable(creds) -> bool:
    """True if the access token is valid, refreshing it first if needed."""
    from google.auth.transport.requests import Request
    if creds.valid:
        return True
    if creds.refresh_token:
        try:
            creds.refresh(Request())
            return True
        except Exception:
            return False   # e.g. refresh token expired/revoked -> sign in again
    return False


def _email_of(creds) -> str:
    try:  # id_token comes straight from Google's token endpoint; read its "email" claim
        payload = creds.id_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))["email"]
    except Exception:
        pass
    import requests
    r = requests.get("https://openidconnect.googleapis.com/v1/userinfo",
                     headers={"Authorization": f"Bearer {creds.token}"}, timeout=15)
    r.raise_for_status()
    return r.json()["email"]


def _browser_flow():
    path = _client_file()
    if not os.path.exists(path):
        raise MailError(f"client_secret.json not found: {path}")
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as e:
        raise MailError("google-auth-oauthlib is not installed (pip install google-auth-oauthlib)") from e
    try:
        flow = InstalledAppFlow.from_client_secrets_file(path, SCOPES)
        return flow.run_local_server(
            port=0, prompt="consent", timeout_seconds=180, authorization_prompt_message="",
            success_message="Sign-in complete. You can close this tab and return to SmartMail.")
    except Exception as e:
        raise MailError(f"Google sign-in failed: {e}") from e


def access_token() -> str:
    """A fresh access token (refreshes automatically). Pass this function as token_provider."""
    with _lock:
        creds, email = _load()
        if creds is None:
            raise MailError("IMAP OAuth sign-in failed: not signed in with Google")
        if not _usable(creds):
            raise MailError("IMAP OAuth sign-in failed: Google session expired, please sign in again")
        _save(creds, email)
        return creds.token


def login_interactive():
    """Returns (email, token_provider). Silent if a saved login still works, else opens the browser.
    Blocks until the user finishes in the browser -> call it from a worker thread in the GUI."""
    with _lock:
        creds, email = _load()
        if creds is not None and email and _usable(creds):
            _save(creds, email)
            return email, access_token
        creds = _browser_flow()
        try:
            email = _email_of(creds)
        except Exception as e:
            raise MailError(f"Google sign-in failed: cannot read your email address ({e})") from e
        _save(creds, email)
        return email, access_token
