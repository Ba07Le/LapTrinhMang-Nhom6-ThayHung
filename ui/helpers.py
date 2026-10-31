"""Các hàm nhỏ hỗ trợ: đổi lỗi, định dạng giờ, đổi dữ liệu thư, tạo avatar..."""
import html as htmllib
import re
from datetime import datetime
from email.utils import parseaddr, parsedate_to_datetime

import customtkinter as ctk

from backend.mail_utils import MailError
from ui.constants import COLORS


def loi_text(e):
    """Đổi lỗi kỹ thuật của backend thành câu dễ hiểu."""
    s = str(e)
    if isinstance(e, MailError):
        if "client_secret" in s:
            return "Thiếu file client_secret.json. Hãy tạo OAuth client trên Google Cloud và đặt file ở thư mục gốc của project."
        if "Google sign-in failed" in s:
            return "Đăng nhập Google không hoàn tất (hết thời gian hoặc bị hủy). Hãy thử lại."
        if "OAuth sign-in failed" in s:
            return "Google từ chối đăng nhập. Hãy bấm 'Dùng tài khoản Google khác' để đăng nhập lại."
        if "not installed" in s:
            return "Thiếu thư viện Google. Chạy: pip install -r requirements.txt"
        if "login failed" in s:
            return "Đăng nhập thất bại. Hãy dùng Mật khẩu ứng dụng (16 ký tự) của Gmail."
        if "Cannot connect" in s or "Không kết nối được Gmail SMTP" in s:
            return "Không kết nối được máy chủ Gmail. Hãy kiểm tra mạng và tường lửa."
        if "SMTP xác thực thất bại" in s:
            return "Gmail từ chối xác thực SMTP. Nếu đăng nhập Google, hãy đăng xuất rồi cấp lại quyền Gmail; nếu dùng App Password, kiểm tra mật khẩu ứng dụng."
        if "Địa chỉ email không hợp lệ" in s:
            return s
    return s or "Có lỗi xảy ra"


def gio(date_str, day_full=False):
    try:
        dt = parsedate_to_datetime(date_str).astimezone()
    except Exception:
        return date_str[:16]
    if day_full:
        return dt.strftime("%H:%M, %d/%m/%Y")
    return dt.strftime("%H:%M") if dt.date() == datetime.now().date() else dt.strftime("%d/%m")


def doi_thu(h):
    """Đổi thư của backend (from, subject, date, uid...) sang dạng giao diện dùng."""
    name, addr = parseaddr(h["from"])
    name = name or addr
    return {"uid": h["uid"], "name": name, "email": addr, "subject": h["subject"], "date": h["date"], "seen": h.get("seen", True),
            "letter": (name[:1] or "?").upper(), "color": COLORS[sum(map(ord, name)) % len(COLORS)]}


def html_sang_text(h):
    h = re.sub(r"(?is)<(script|style).*?</\1>", "", h)
    h = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", h)
    h = htmllib.unescape(re.sub(r"<[^>]+>", "", h))
    return re.sub(r"\n\s*\n+", "\n\n", h).strip()


def dung_luong(n):
    return f"{n / 1024 / 1024:.1f} MB" if n >= 1024 * 1024 else f"{max(1, n // 1024)} KB"


def click_all(widget, fn):
    """Gắn sự kiện click cho widget và tất cả widget con."""
    widget.bind("<Button-1>", lambda e: fn(), add="+")
    for c in widget.winfo_children():
        click_all(c, fn)


def avatar(parent, letter, color, size=40):
    return ctk.CTkLabel(parent, text=letter, width=size, height=size, corner_radius=size // 2,
                        fg_color=color, text_color="white", font=("Segoe UI", 16, "bold"))
