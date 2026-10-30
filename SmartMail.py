import html as htmllib
import queue
import re
import threading
from tkinter import filedialog, messagebox, StringVar
from datetime import datetime
from email.utils import parseaddr, parsedate_to_datetime

import customtkinter as ctk

from backend import oauth_google
from backend.imap_client import ImapClient, NewMailWatcher   # backend nhận thư của nhóm
from backend.mail_utils import MailError
from backend.email_service import send_email

ctk.set_appearance_mode("light")

BLUE, BG, WHITE, GRAY, SEL = "#1a6cf0", "#f4f7fc", "#ffffff", "#6b7280", "#e6f0ff"
GREEN, RED = "#16a34a", "#dc2626"
COLORS = ["#2563eb", "#ea4335", "#22a559", "#7c3aed", "#f59e0b", "#1877f2", "#ef4444"]

MAX_LOAD = 1000   # tối đa số thư hiển thị mỗi thư mục (muốn xem thư cũ hơn thì dùng ô tìm kiếm)
PAGE_SIZE = 15   # số thư mỗi lần tải (bấm "Tải thêm" để xem thư cũ hơn)
NAV = [("✉", "Hộp thư đến"), ("➤", "Đã gửi"), ("🗎", "Thư nháp"),
       ("🗂", "Tất cả thư"), ("🗑", "Thùng rác")]


# ---------- Hàm nhỏ hỗ trợ ----------
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


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SmartMail - Email Client")
        self.geometry("1280x780")
        self.configure(fg_color=BG)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.current, self.token, self.load_id = 0, 0, 0
        self.nav_i, self.folder, self.folders = 0, "INBOX", {}
        self.page, self.total, self.loading_more, self.rows, self.more_btn = 1, 0, False, [], None
        self.watcher, self.new_q, self.new_count = None, queue.Queue(), 0
        self.search_active = False
        self.email, self.pw, self.client, self.token_provider = "", "", None, None
        self.mails, self.cache = [], {}
        self.lock = threading.Lock()   # imaplib không chạy song song được -> xếp hàng từng việc
        self.protocol("WM_DELETE_WINDOW", self.dong)
        self.show_login()

    # ---------- Chạy việc mạng ở luồng riêng (giao diện không bị đơ) ----------
    def chay_nen(self, ham, xong):
        """Chạy ham() ở luồng riêng. Xong thì gọi xong(kết_quả, lỗi) ở luồng chính."""
        kq = {}

        def lam():
            try:
                with self.lock:
                    kq["v"] = ham()
            except Exception as e:
                kq["e"] = e

        threading.Thread(target=lam, daemon=True).start()

        def cho():
            if "v" in kq or "e" in kq:
                xong(kq.get("v"), kq.get("e"))
            else:
                self.after(100, cho)
        cho()

    def goi(self, ten, *a, **k):
        """Gọi hàm của backend; nếu mất kết nối thì đăng nhập lại rồi thử thêm 1 lần."""
        try:
            return getattr(self.client, ten)(*a, **k)
        except Exception:
            self.client.reconnect()
            return getattr(self.client, ten)(*a, **k)

    def dong(self):
        if self.watcher:
            self.watcher.stop()
        if self.client:
            self.client.logout()
        self.destroy()

    # ---------- Màn hình đăng nhập ----------
    def show_login(self):
        self.login = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.login.place(relx=0, rely=0, relwidth=1, relheight=1)

        card = ctk.CTkFrame(self.login, fg_color=WHITE, corner_radius=16)
        card.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(card, text="✉  SmartMail", font=("Segoe UI", 28, "bold"),
                     text_color=BLUE).pack(padx=50, pady=(40, 2))
        ctk.CTkLabel(card, text="Kết nối tài khoản Gmail của bạn", text_color=GRAY).pack(pady=(0, 24))

        self.e_email = ctk.CTkEntry(card, placeholder_text="Email", width=340, height=44)
        self.e_email.pack(pady=6)
        self.e_pass = ctk.CTkEntry(card, placeholder_text="Mật khẩu ứng dụng (16 ký tự)", show="•",
                                   width=340, height=44)
        self.e_pass.pack(pady=6)
        self.e_pass.bind("<Return>", lambda e: self.on_connect())

        self.btn = ctk.CTkButton(card, text="Kết nối", width=340, height=44, fg_color=BLUE,
                                 font=("Segoe UI", 14, "bold"), command=self.on_connect)
        self.btn.pack(pady=(14, 6))

        ctk.CTkLabel(card, text="──────────  hoặc  ──────────", text_color=GRAY).pack(pady=(4, 8))
        saved = oauth_google.saved_email()
        self.btn_g = ctk.CTkButton(card, text="G   " + (f"Tiếp tục với {saved}" if saved else "Đăng nhập bằng Google"),
                                   width=340, height=44, fg_color=WHITE, text_color="#111827",
                                   border_width=1, border_color="#d1d5db", hover_color="#f3f4f6",
                                   font=("Segoe UI", 14, "bold"), command=self.on_google)
        self.btn_g.pack()
        self.btn_other = ctk.CTkButton(card, text="Dùng tài khoản Google khác", height=24, fg_color="transparent",
                                       text_color=GRAY, hover_color="#f3f4f6", font=("Segoe UI", 11),
                                       command=lambda: self.on_google(True))
        self.btn_other.pack(pady=(4, 0))
        self.status = ctk.CTkLabel(card, text="", wraplength=340, height=40)
        self.status.pack(pady=(0, 30))

    def set_status(self, text, color):
        self.status.configure(text=text, text_color=color)

    def set_busy(self, busy):
        st = "disabled" if busy else "normal"
        self.btn.configure(state=st, text="Đang kết nối..." if busy else "Kết nối")
        self.btn_g.configure(state=st)
        self.btn_other.configure(state=st)

    # ---------- Đăng nhập bằng Google (OAuth2, không cần mật khẩu ứng dụng) ----------
    def on_google(self, new_account=False):
        self.set_busy(True)
        self.set_status("⏳ Đang mở trình duyệt để đăng nhập Google...\nHãy hoàn tất trong cửa sổ trình duyệt.", GRAY)

        def work():
            if new_account:
                oauth_google.sign_out()
            email, provider = oauth_google.login_interactive()   # lần sau đăng nhập ngầm, không mở trình duyệt
            return ImapClient().login_oauth(email, provider), email, provider
        self.chay_nen(work, self.finish_google)

    def finish_google(self, res, err):
        if err:
            self.set_status("✖ " + loi_text(err), RED)
            return self.set_busy(False)
        self.client, self.email, self.token_provider = res
        self.pw = ""
        self.set_status("✔ Đăng nhập Google thành công", GREEN)
        self.after(800, self.open_mail)

    def on_connect(self):
        email, pw = self.e_email.get().strip(), self.e_pass.get().replace(" ", "")
        if "@" not in email:
            return self.set_status("✖ Email không hợp lệ", RED)
        if not pw:
            return self.set_status("✖ Bạn chưa nhập mật khẩu", RED)
        self.set_busy(True)
        self.set_status("⏳ Đang kết nối, vui lòng chờ...", GRAY)
        self.chay_nen(lambda: ImapClient().login(email, pw),
                      lambda c, e: self.finish_connect(email, pw, c, e))

    def finish_connect(self, email, pw, client, err):
        if err:
            self.set_status("✖ " + loi_text(err), RED)
            self.set_busy(False)
        else:
            self.client, self.email, self.pw = client, email, pw
            self.set_status("✔ Kết nối thành công", GREEN)
            self.after(800, self.open_mail)

    def open_mail(self):
        self.login.destroy()
        self.build_sidebar()
        self.build_main()
        self.load_mails(auto_open=False)
        self.refresh_nav_counts()
        self.start_watcher()

    # ---------- Menu tài khoản / đăng xuất ----------
    def toggle_account_menu(self):
        """Hiện hoặc ẩn menu tài khoản ở góc trên bên phải."""
        if getattr(self, "account_menu", None) and self.account_menu.winfo_exists():
            self.account_menu.destroy()
            self.account_menu = None
            return

        # Đặt menu trực tiếp trên cửa sổ chính để tránh bị khung top_bar
        # hoặc các widget khác che khuất.
        self.account_menu = ctk.CTkFrame(
            self, fg_color=WHITE, corner_radius=10,
            border_width=1, border_color="#d1d5db", width=260
        )
        self.account_menu.place(relx=0.99, rely=0.115, anchor="ne")
        self.account_menu.lift()
        ctk.CTkLabel(
            self.account_menu, text=self.email, text_color=GRAY,
            font=("Segoe UI", 11), wraplength=240
        ).pack(fill="x", padx=14, pady=(10, 5))
        ctk.CTkButton(
            self.account_menu, text="↪  Đăng xuất", height=36,
            fg_color="transparent", hover_color="#fee2e2",
            text_color=RED, anchor="w", corner_radius=7,
            command=self.confirm_logout
        ).pack(fill="x", padx=6, pady=(2, 6))

    def confirm_logout(self):
        if getattr(self, "account_menu", None) and self.account_menu.winfo_exists():
            self.account_menu.destroy()
            self.account_menu = None
        if messagebox.askyesno("Xác nhận đăng xuất", "Bạn có chắc chắn muốn đăng xuất khỏi SmartMail?"):
            self.logout()

    def logout(self):
        """Đóng các kết nối hiện tại và quay về màn hình đăng nhập."""
        # Vô hiệu hóa các kết quả tải thư đang chờ để chúng không cập nhật giao diện đăng nhập.
        self.token += 1
        self.load_id += 1

        if self.watcher:
            try:
                self.watcher.stop()
            except Exception:
                pass
            self.watcher = None

        if self.client:
            try:
                self.client.logout()
            except Exception:
                pass
            self.client = None

        # Chỉ xóa token Google khi phiên hiện tại được đăng nhập bằng OAuth.
        if self.token_provider:
            oauth_google.sign_out()

        self.email = self.pw = ""
        self.token_provider = None
        self.mails, self.cache, self.rows = [], {}, []
        self.folders = {}
        self.new_count = 0
        self.account_menu = None

        for widget in self.winfo_children():
            widget.destroy()
        self.show_login()

    # ---------- Tải thư: loading / lỗi / thành công ----------
    def load_mails(self, auto_open=False):
        selected_uid = (self.mails[self.current]["uid"]
                        if self.mails and 0 <= self.current < len(self.mails) else None)
        self.search_active = False
        for w in self.listbox.winfo_children():
            w.destroy()
        self.token += 1
        self.load_id += 1
        self.loading_more = False
        lid, nav = self.load_id, self.nav_i
        self.notice("⏳ Đang tải thư...", GRAY)

        def work():
            if nav == 0:
                name = "INBOX"
            else:
                if not self.folders:
                    self.folders = self.goi("special_folders")
                folder_key = {1: "sent", 2: "drafts", 3: "all", 4: "trash"}.get(nav)
                name = self.folders.get(folder_key) if folder_key else None
                if not name:
                    raise MailError("Không tìm thấy thư mục này trong tài khoản Gmail.")
            return name, self.goi("list_emails", folder=name, page=1, page_size=PAGE_SIZE)

        self.chay_nen(work, lambda res, e: self.finish_load(
            lid, nav, res, e, auto_open=auto_open, selected_uid=selected_uid))

    def finish_load(self, lid, nav, res, err, auto_open=True, selected_uid=None):
        if lid != self.load_id:   # đã chuyển thư mục / tìm kiếm mới -> bỏ kết quả cũ
            return
        if err:
            return self.notice("✖ " + loi_text(err), RED, retry=True)
        self.folder, r = res[0], res[1]
        self.cache = {}
        self.mails = [doi_thu(h) for h in r["emails"]]
        self.current, self.page, self.total = -1, 1, min(r["total"], MAX_LOAD)
        cnt = f"{MAX_LOAD}+" if r["total"] > MAX_LOAD else str(r["total"])
        self.head_lbl.configure(text=f"{NAV[nav][1]} ({cnt})")
        self.render_list()
        if self.mails:
            if auto_open:
                self.show(0)
            else:
                # Làm mới danh sách nền mà không tự mở thư mới (tránh tự đánh dấu đã đọc).
                self.current = next((i for i, m in enumerate(self.mails)
                                    if m["uid"] == selected_uid), -1)
                if self.current >= 0:
                    self.highlight(-1, self.current)
                else:
                    self.notice("Chọn một email để xem nội dung", GRAY)
        else:
            self.current = -1
            self.notice("Thư mục trống", GRAY)

    def load_more(self):
        """Tải thêm 1 trang thư cũ hơn và nối vào cuối danh sách (không vẽ lại cả danh sách)."""
        if self.loading_more:
            return
        self.loading_more = True
        self.more_btn.configure(text="⏳ Đang tải...", state="disabled")
        lid, folder, page = self.load_id, self.folder, self.page + 1
        self.chay_nen(lambda: self.goi("list_emails", folder=folder, page=page, page_size=PAGE_SIZE),
                      lambda r, e: self.finish_more(lid, page, r, e))

    def finish_more(self, lid, page, r, err):
        self.loading_more = False
        if lid != self.load_id:
            return
        if err:
            return self.more_btn.configure(text="✖ Lỗi - bấm để thử lại", state="normal")
        self.page = page
        have = {m["uid"] for m in self.mails}
        start = len(self.mails)
        self.mails += [doi_thu(h) for h in r["emails"] if h["uid"] not in have]
        del self.mails[MAX_LOAD:]   # trang cuối có thể vượt giới hạn
        self.append_rows(start)

    # ---------- Tìm kiếm và lọc hộp thư ----------
    def on_search(self):
        q = self.search_entry.get().strip()
        mode = self.search_mode.get()
        if mode == "Chưa đọc":
            self.token += 1
            self.load_id += 1
            lid, folder = self.load_id, self.folder
            self.search_active = True
            self.notice("⏳ Đang lọc thư chưa đọc...", GRAY)
            self.chay_nen(
                lambda: self.goi("search", folder=folder, unseen_only=True),
                lambda r, e: self.finish_search(lid, "Chưa đọc", r, e, auto_open=False)
            )
            return
        if not q:
            return self.load_mails()

        self.token += 1
        self.load_id += 1
        lid, folder = self.load_id, self.folder
        self.search_active = True
        for w in self.listbox.winfo_children():
            w.destroy()
        self.notice("⏳ Đang tìm...", GRAY)

        criteria = {"folder": folder}
        if mode == "Người gửi":
            criteria["sender"] = q
        elif mode == "Tiêu đề":
            criteria["subject"] = q
        else:
            criteria["keyword"] = q
        self.chay_nen(lambda: self.goi("search", **criteria),
                      lambda r, e: self.finish_search(lid, f"{mode}: {q}", r, e, auto_open=False))

    def finish_search(self, lid, label, r, err, auto_open=False):
        if lid != self.load_id:
            return
        if err:
            return self.notice("✖ " + loi_text(err), RED, retry=True)
        self.mails = [doi_thu(h) for h in r]
        self.current, self.total = -1, len(r)
        self.head_lbl.configure(text=f"Kết quả {label} ({len(r)})")
        self.render_list()
        if self.mails:
            if auto_open:
                self.show(0)
            else:
                self.notice("Chọn một email để xem nội dung", GRAY)
        else:
            self.current = -1
            self.notice("Không tìm thấy thư nào", GRAY)

    # ---------- Thông báo thư mới (NewMailWatcher chạy kết nối riêng) ----------
    def start_watcher(self):
        self.watcher = NewMailWatcher(
            "imap.gmail.com", 993, self.email, self.pw,
            on_new=lambda items: self.new_q.put(("new", items)),
            folder="INBOX", interval=30, token_provider=self.token_provider,
            on_error=lambda err: self.new_q.put(("error", err))
        )
        self.watcher.start()
        self.after(1000, self.poll_new)
        self.after(60000, self.periodic_nav_counts)

    def periodic_nav_counts(self):
        """Refresh folder badges periodically, including changes made outside SmartMail."""
        if not self.watcher or not self.client:
            return
        self.refresh_nav_counts()
        self.after(60000, self.periodic_nav_counts)

    def poll_new(self):   # luồng chính lấy kết quả từ hàng đợi (Tkinter không an toàn khi gọi từ luồng khác)
        if not self.watcher:
            return
        try:
            while True:
                kind, payload = self.new_q.get_nowait()
                if kind == "error":
                    self.bell.configure(
                        text="⚠ Kết nối thông báo bị gián đoạn",
                        fg_color="#d97706", hover_color="#b45309"
                    )
                    if not self.bell.winfo_ismapped():
                        self.bell.pack(side="right", padx=8)
                    continue

                new = payload
                if not new:
                    continue
                self.new_count += len(new)
                # Cập nhật số thư chưa đọc và số lượng các thư mục từ IMAP.
                self.refresh_nav_counts()
                self.bell.configure(
                    text=f"🔔 {self.new_count} thư mới: {new[0]['subject'][:24]}",
                    fg_color=GREEN, hover_color="#15803d"
                )
                if not self.bell.winfo_ismapped():
                    self.bell.pack(side="right", padx=8)

                # Đồng bộ lại danh sách Inbox nhưng không tự mở thư mới.
                if self.nav_i == 0 and self.folder == "INBOX" and not self.search_active:
                    self.load_mails(auto_open=False)
        except queue.Empty:
            pass
        if self.watcher:
            self.after(1000, self.poll_new)

    def open_new(self):
        self.bell.pack_forget()
        self.new_count = 0
        self.bell.configure(fg_color=GREEN, hover_color="#15803d")
        self.switch(0)

    def notice(self, text, color, retry=False):
        for w in self.detail.winfo_children():
            w.destroy()
        box = ctk.CTkFrame(self.detail, fg_color="transparent")
        box.place(relx=0.5, rely=0.45, anchor="center")
        ctk.CTkLabel(box, text=text, text_color=color, font=("Segoe UI", 16), wraplength=500).pack(pady=8)
        if retry:
            ctk.CTkButton(box, text="↻  Thử lại", fg_color=BLUE, corner_radius=20,
                          command=self.load_mails).pack(pady=8)

    def back(self):
        if self.mails and 0 <= self.current < len(self.mails):
            self.show(self.current)
        else:
            self.notice("Chọn một thư để đọc", GRAY)

    # ---------- Thanh bên trái ----------
    def build_sidebar(self):
        sb = ctk.CTkFrame(self, width=240, fg_color="transparent")
        sb.grid(row=0, column=0, sticky="ns", padx=16, pady=16)

        ctk.CTkLabel(sb, text="✉  SmartMail", font=("Segoe UI", 22, "bold"),
                     text_color=BLUE).pack(anchor="w")
        ctk.CTkLabel(sb, text="Kết nối thế giới qua email", text_color=GRAY,
                     font=("Segoe UI", 11)).pack(anchor="w", pady=(0, 20))

        ctk.CTkButton(sb, text="✎  Soạn thư", height=44, corner_radius=8, fg_color=BLUE,
                      font=("Segoe UI", 14, "bold"), command=self.compose).pack(fill="x", pady=(0, 16))

        self.nav_items = []
        self.nav_counts = {"inbox_unread": 0, "sent": 0, "drafts": 0, "all": 0, "trash": 0}
        for i, (icon, name) in enumerate(NAV):
            f = ctk.CTkFrame(sb, height=38, corner_radius=8)
            f.pack(fill="x", pady=1)
            li = ctk.CTkLabel(f, text=icon, width=28)
            li.pack(side="left", padx=(8, 0))
            ln = ctk.CTkLabel(f, text=name)
            ln.pack(side="left", padx=6)
            click_all(f, lambda i=i: self.switch(i))
            self.nav_items.append((f, li, ln))
        self.style_nav()

    def update_nav_counts(self, counts):
        """Render IMAP-backed counts beside mailbox folders."""
        if not isinstance(counts, dict):
            return
        self.nav_counts.update(counts)
        keys = ["inbox_unread", "sent", "drafts", "all", "trash"]
        for i, key in enumerate(keys):
            if i >= len(self.nav_items):
                continue
            label = self.nav_items[i][2]
            count = int(self.nav_counts.get(key, 0) or 0)
            # Inbox shows unread count; other folders show total items.
            base = NAV[i][1]
            label.configure(text=f"{base}  ({count})" if count > 0 else base)

    def refresh_nav_counts(self):
        if not self.client or not hasattr(self, "nav_items"):
            return
        self.chay_nen(
            lambda: self.goi("folder_counts"),
            lambda counts, err: (self.update_nav_counts(counts) if not err and counts else None)
        )

    def style_nav(self):
        for i, (f, li, ln) in enumerate(self.nav_items):
            on = i == self.nav_i
            f.configure(fg_color=SEL if on else "transparent")
            li.configure(text_color=BLUE if on else "#374151")
            ln.configure(text_color=BLUE if on else "#111827", font=("Segoe UI", 13, "bold" if on else "normal"))

    def switch(self, i):
        self.nav_i = i
        self.style_nav()
        self.search_entry.delete(0, "end")
        self.load_mails()

    # ---------- Khu vực chính ----------
    def build_main(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=(0, 16), pady=16)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(main, fg_color="transparent")
        self.top_bar = top
        self.account_menu = None
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        self.search_entry = ctk.CTkEntry(
            top, placeholder_text="Từ khóa tìm kiếm...", height=42,
            corner_radius=21, border_width=0, fg_color="#e8eef7", width=340
        )
        self.search_entry.pack(side="left")
        self.search_entry.bind("<Return>", lambda e: self.on_search())
        self.search_mode = StringVar(value="Toàn bộ nội dung")
        self.search_mode_menu = ctk.CTkOptionMenu(
            top, variable=self.search_mode,
            values=["Toàn bộ nội dung", "Người gửi", "Tiêu đề", "Chưa đọc"],
            width=125, height=36, command=lambda _v: None
        )
        self.search_mode_menu.pack(side="left", padx=(8, 6))
        ctk.CTkButton(
            top, text="Tìm", width=54, height=36, corner_radius=18,
            fg_color=BLUE, command=self.on_search
        ).pack(side="left", padx=(0, 8))
        self.account_button = ctk.CTkButton(
            top, text=f"{self.email}  ▾", width=260, height=36,
            fg_color="transparent", hover_color="#e8eef7",
            text_color="#374151", anchor="e", corner_radius=8,
            font=("Segoe UI", 12), command=self.toggle_account_menu
        )
        self.account_button.pack(side="right", padx=8)
        self.bell = ctk.CTkButton(top, text="", height=34, corner_radius=17, fg_color=GREEN,
                                  hover_color="#15803d", command=self.open_new)   # hiện khi có thư mới

        box = ctk.CTkFrame(main, width=400, fg_color=WHITE, corner_radius=12)
        box.grid(row=1, column=0, sticky="ns", padx=(0, 12))
        box.grid_propagate(False)
        head = ctk.CTkFrame(box, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=14)
        self.head_lbl = ctk.CTkLabel(head, text="Hộp thư đến", font=("Segoe UI", 16, "bold"))
        self.head_lbl.pack(side="left")
        ctk.CTkButton(head, text="↻", width=34, height=30, fg_color="transparent", text_color="#111827",
                      hover_color="#f3f4f6", command=self.load_mails).pack(side="right")
        self.listbox = ctk.CTkScrollableFrame(box, fg_color="transparent")
        self.listbox.pack(fill="both", expand=True)

        self.detail = ctk.CTkFrame(main, fg_color=WHITE, corner_radius=12)
        self.detail.grid(row=1, column=1, sticky="nsew")

    def render_list(self):
        for w in self.listbox.winfo_children():
            w.destroy()
        self.rows, self.more_btn = [], None
        self.append_rows(0)

    def append_rows(self, start):
        """Chỉ tạo thêm các dòng mới (CustomTkinter vẽ chậm nên không tạo lại cả danh sách)."""
        if self.more_btn is not None:
            self.more_btn.destroy()
            self.more_btn = None
        for i in range(start, len(self.mails)):
            self.rows.append(self.add_row(i, self.mails[i]))
        left = self.total - len(self.mails)
        if left > 0 and self.mails:
            self.more_btn = ctk.CTkButton(self.listbox, text=f"↓  Tải thêm ({left} thư cũ hơn)", height=36,
                                          corner_radius=18, fg_color="transparent", text_color=BLUE,
                                          border_width=1, border_color=BLUE, hover_color=SEL,
                                          command=self.load_more)
            self.more_btn.pack(pady=10)

    def add_row(self, i, m):
        item = ctk.CTkFrame(self.listbox, corner_radius=8, fg_color=SEL if i == self.current else "transparent")
        item.pack(fill="x", pady=2)
        item.grid_columnconfigure(1, weight=1)
        avatar(item, m["letter"], m["color"]).grid(row=0, column=0, rowspan=2, padx=10, pady=10, sticky="n")
        nm = ctk.CTkLabel(item, text=("● " if not m["seen"] else "") + m["name"][:24],
                          font=("Segoe UI", 13, "bold"), anchor="w")
        nm.grid(row=0, column=1, sticky="w", pady=(8, 0))
        ctk.CTkLabel(item, text=gio(m["date"]), text_color=GRAY, font=("Segoe UI", 11)).grid(row=0, column=2, padx=10)
        sj = ctk.CTkLabel(item, text=m["subject"][:40], anchor="w",
                          font=("Segoe UI", 12, "normal" if m["seen"] else "bold"))
        sj.grid(row=1, column=1, sticky="w", pady=(0, 10))
        click_all(item, lambda i=i: self.show(i))
        return item, nm, sj

    def highlight(self, prev, i):
        if 0 <= prev < len(self.rows):
            self.rows[prev][0].configure(fg_color="transparent")
        if 0 <= i < len(self.rows):
            self.rows[i][0].configure(fg_color=SEL)

    def refresh_row(self, i):
        if i < len(self.rows):
            _, nm, sj = self.rows[i]
            m = self.mails[i]
            nm.configure(text=("● " if not m["seen"] else "") + m["name"][:24])
            sj.configure(font=("Segoe UI", 12, "normal" if m["seen"] else "bold"))

    # ---------- Đọc thư ----------
    def show(self, i):
        self.token += 1
        prev = self.current
        tk, self.current = self.token, i
        self.highlight(prev, i)
        m = self.mails[i]
        d = self.detail
        for w in d.winfo_children():
            w.destroy()

        ctk.CTkLabel(d, text=m["subject"], font=("Segoe UI", 20, "bold"), anchor="w", justify="left",
                     wraplength=650).pack(fill="x", padx=24, pady=(20, 10))

        sender = ctk.CTkFrame(d, fg_color="transparent")
        sender.pack(fill="x", padx=24, pady=10)
        avatar(sender, m["letter"], m["color"], 48).pack(side="left")
        info = ctk.CTkFrame(sender, fg_color="transparent")
        info.pack(side="left", padx=12)
        ctk.CTkLabel(info, text=m["name"], font=("Segoe UI", 14, "bold"), anchor="w").pack(anchor="w")
        ctk.CTkLabel(info, text=m["email"], text_color=GRAY, anchor="w").pack(anchor="w")
        ctk.CTkLabel(info, text=f"Đến: {self.email}", text_color=GRAY, anchor="w").pack(anchor="w")
        ctk.CTkLabel(sender, text=gio(m["date"], True), text_color=GRAY).pack(side="right", anchor="n")

        # Nút trả lời (đặt ở đáy trước để luôn thấy)
        btns = ctk.CTkFrame(d, fg_color="transparent")
        btns.pack(side="bottom", anchor="w", padx=24, pady=24)
        old = lambda: self.cache.get(m["uid"], {}).get("text", "")
        actions = [("↩  Trả lời", lambda: self.compose(m["email"], "Re: " + m["subject"])),
                   ("↩↩  Trả lời tất cả", lambda: self.compose(m["email"], "Re: " + m["subject"])),
                   ("↪  Chuyển tiếp", lambda: self.compose("", "Fwd: " + m["subject"],
                                                          "\n\n--- Thư chuyển tiếp ---\n" + old()))]
        for text, cmd in actions:
            ctk.CTkButton(btns, text=text, command=cmd, corner_radius=20, height=38, fg_color=WHITE,
                          text_color="#111827", border_width=1, border_color="#d1d5db",
                          hover_color="#f3f4f6").pack(side="left", padx=(0, 10))

        # Nội dung: lấy từ backend (get_email), có loading / lỗi
        self.body_box = ctk.CTkFrame(d, fg_color="transparent")
        self.body_box.pack(fill="both", expand=True, padx=24, pady=(10, 0))
        if m["uid"] in self.cache:
            return self.render_body(m, self.cache[m["uid"]])
        ctk.CTkLabel(self.body_box, text="⏳ Đang tải nội dung thư...", text_color=GRAY).pack(pady=30)
        uid, folder = m["uid"], self.folder
        self.chay_nen(lambda: self.goi("get_email", uid, folder=folder), lambda f, e: self.finish_read(tk, m, f, e))

    def finish_read(self, tk, m, f, err):
        if tk != self.token:   # người dùng đã bấm sang thư khác -> bỏ kết quả này
            return
        for w in self.body_box.winfo_children():
            w.destroy()
        if err:
            ctk.CTkLabel(self.body_box, text="✖ " + loi_text(err), text_color=RED, wraplength=600).pack(pady=(30, 8))
            ctk.CTkButton(self.body_box, text="↻  Thử lại", fg_color=BLUE, corner_radius=20,
                          command=lambda: self.show(self.current)).pack()
            return
        text = f["body_text"].strip() or html_sang_text(f["body_html"]) or "(Thư không có nội dung)"
        self.cache[m["uid"]] = {"text": text, "attachments": f["attachments"]}
        self.render_body(m, self.cache[m["uid"]])
        if not m["seen"]:   # đánh dấu đã đọc trên Gmail
            m["seen"] = True
            uid, folder = m["uid"], self.folder
            self.chay_nen(lambda: self.goi("mark_seen", uid, folder=folder),
                          lambda *_: self.refresh_nav_counts())
            self.refresh_row(self.current)

    def render_body(self, m, info):
        box, att = self.body_box, info["attachments"]
        for w in box.winfo_children():
            w.destroy()

        if att:
            af = ctk.CTkFrame(box, fg_color="transparent")
            af.pack(side="bottom", fill="x")
            ctk.CTkLabel(af, text=f"📎  {len(att)} tệp đính kèm", font=("Segoe UI", 13, "bold")).pack(anchor="w")
            for a in att:
                name = a["filename"]
                ext = (name.rsplit(".", 1)[-1][:4] if "." in name else "FILE").upper()
                f = ctk.CTkFrame(af, fg_color="transparent", border_width=1, border_color="#e5e7eb", corner_radius=8)
                f.pack(fill="x", pady=4)
                ctk.CTkLabel(f, text=ext, width=40, height=36, corner_radius=6, fg_color="#2563eb",
                             text_color="white", font=("Segoe UI", 11, "bold")).pack(side="left", padx=12, pady=8)
                ctk.CTkLabel(f, text=f"{name}\n{dung_luong(a['size'])}", justify="left", anchor="w").pack(side="left")
                ctk.CTkButton(f, text="⬇", width=40, fg_color="transparent", text_color="#111827",
                              hover_color="#f3f4f6", font=("Segoe UI", 16),
                              command=lambda idx=a["index"]: self.tai_dinh_kem(m["uid"], idx)).pack(side="right", padx=10)
            self.att_status = ctk.CTkLabel(af, text="", wraplength=600, justify="left")
            self.att_status.pack(anchor="w", pady=(2, 0))

        tb = ctk.CTkTextbox(box, fg_color=WHITE, font=("Segoe UI", 14), wrap="word")
        tb.pack(fill="both", expand=True, pady=(0, 8))
        tb.insert("1.0", info["text"])
        tb.configure(state="disabled")

    def tai_dinh_kem(self, uid, index):
        self.att_status.configure(text="⏳ Đang tải tệp...", text_color=GRAY)

        def xong(path, err):
            if self.att_status.winfo_exists():
                self.att_status.configure(
                    text=("✖ " + loi_text(err)) if err else f"✔ Đã lưu tại: {path}",
                    text_color=RED if err else GREEN)
        folder = self.folder
        self.chay_nen(lambda: self.goi("download_attachment", uid, index, "downloads", folder=folder), xong)

    # ---------- Màn hình soạn thư ----------
    def compose(self, to="", subject="", body=""):
        self.token += 1
        d = self.detail
        for w in d.winfo_children():
            w.destroy()
        self.c_attachments = []
        ctk.CTkLabel(d, text="Soạn thư mới", font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=24, pady=(20, 10))

        self.c_to = ctk.CTkEntry(d, placeholder_text="Đến (email người nhận; có thể nhập nhiều địa chỉ, cách nhau bằng dấu phẩy)", height=42)
        self.c_to.pack(fill="x", padx=24, pady=6)
        self.c_sub = ctk.CTkEntry(d, placeholder_text="Tiêu đề", height=42)
        self.c_sub.pack(fill="x", padx=24, pady=6)
        self.c_body = ctk.CTkTextbox(d, border_width=1, border_color="#e5e7eb", fg_color=WHITE,
                                     font=("Segoe UI", 14))
        self.c_body.pack(fill="both", expand=True, padx=24, pady=6)

        if to:
            self.c_to.insert(0, to)
        if subject:
            self.c_sub.insert(0, subject)
        self.c_body.insert("1.0", body)

        attach_row = ctk.CTkFrame(d, fg_color="transparent")
        attach_row.pack(fill="x", padx=24, pady=(4, 2))
        self.c_attach_btn = ctk.CTkButton(attach_row, text="📎  Đính kèm tệp", width=145,
                                          fg_color=WHITE, text_color="#111827", border_width=1,
                                          border_color="#d1d5db", hover_color="#f3f4f6",
                                          command=self.chon_dinh_kem)
        self.c_attach_btn.pack(side="left")
        self.c_attach_label = ctk.CTkLabel(attach_row, text="Chưa có tệp đính kèm", text_color=GRAY,
                                           anchor="w")
        self.c_attach_label.pack(side="left", padx=10, fill="x", expand=True)

        self.c_status = ctk.CTkLabel(d, text="", height=28, wraplength=850, justify="left")
        self.c_status.pack(anchor="w", padx=24)
        bar = ctk.CTkFrame(d, fg_color="transparent")
        bar.pack(anchor="w", padx=24, pady=(0, 24))
        self.c_send = ctk.CTkButton(bar, text="➤  Gửi", width=120, height=40, corner_radius=20,
                                    fg_color=BLUE, command=self.on_send)
        self.c_send.pack(side="left", padx=(0, 10))
        ctk.CTkButton(bar, text="Hủy", width=100, height=40, corner_radius=20, fg_color=WHITE,
                      text_color="#111827", border_width=1, border_color="#d1d5db",
                      hover_color="#f3f4f6", command=self.back).pack(side="left")

    def chon_dinh_kem(self):
        paths = filedialog.askopenfilenames(title="Chọn tệp đính kèm")
        if not paths:
            return
        for path in paths:
            if path not in self.c_attachments:
                self.c_attachments.append(path)
        names = [path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] for path in self.c_attachments]
        label = "; ".join(names)
        self.c_attach_label.configure(text=label, text_color="#111827")

    def on_send(self):
        to = self.c_to.get().strip()
        sub = self.c_sub.get().strip()
        body = self.c_body.get("1.0", "end-1c")
        if not to:
            return self.c_status.configure(text="✖ Bạn chưa nhập địa chỉ người nhận", text_color=RED)
        if not sub:
            return self.c_status.configure(text="✖ Bạn chưa nhập tiêu đề", text_color=RED)
        if not self.email:
            return self.c_status.configure(text="✖ Chưa có tài khoản gửi thư. Hãy đăng nhập lại.", text_color=RED)
        if not self.token_provider and not self.pw:
            return self.c_status.configure(text="✖ Không có thông tin xác thực SMTP. Hãy đăng nhập lại.", text_color=RED)

        attachments = tuple(self.c_attachments)
        sender = self.email
        password = self.pw or None
        token_provider = self.token_provider
        self.c_send.configure(state="disabled", text="Đang gửi...")
        self.c_attach_btn.configure(state="disabled")
        self.c_status.configure(text="⏳ Đang kết nối Gmail SMTP và gửi thư...", text_color=GRAY)

        def work():
            return send_email(
                sender=sender,
                to=to,
                subject=sub,
                body=body,
                attachments=attachments,
                password=password,
                token_provider=token_provider,
            )

        self.chay_nen(work, self.finish_send)

    def finish_send(self, result, err):
        if err:
            self.c_status.configure(text="✖ " + loi_text(err), text_color=RED)
            self.c_send.configure(state="normal", text="➤  Gửi")
            self.c_attach_btn.configure(state="normal")
            return

        refused = result.get("refused", {})
        accepted = result.get("accepted", [])
        if refused:
            rejected = ", ".join(refused.keys())
            self.c_status.configure(
                text=f"⚠ Đã gửi tới {len(accepted)} địa chỉ; Gmail từ chối: {rejected}. Không bấm gửi lại ngay để tránh gửi trùng.",
                text_color=RED)
            self.c_send.configure(state="normal", text="➤  Gửi")
            self.c_attach_btn.configure(state="normal")
            return

        self.c_status.configure(
            text=f"✔ Gmail đã chấp nhận thư gửi tới {len(accepted)} địa chỉ. Kiểm tra mục Đã gửi và hộp thư người nhận. (Message-ID: {result.get('message_id', 'N/A')})",
            text_color=GREEN)
        self.c_send.configure(state="disabled", text="Đã gửi")
        self.c_attach_btn.configure(state="disabled")


if __name__ == "__main__":
    App().mainloop()