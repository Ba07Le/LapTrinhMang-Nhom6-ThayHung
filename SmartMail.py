import html as htmllib
import re
import threading
from datetime import datetime
from email.utils import parseaddr, parsedate_to_datetime

import customtkinter as ctk

from backend.imap_client import ImapClient   # backend nhận thư của nhóm
from backend.mail_utils import MailError

ctk.set_appearance_mode("light")

BLUE, BG, WHITE, GRAY, SEL = "#1a6cf0", "#f4f7fc", "#ffffff", "#6b7280", "#e6f0ff"
GREEN, RED = "#16a34a", "#dc2626"
COLORS = ["#2563eb", "#ea4335", "#22a559", "#7c3aed", "#f59e0b", "#1877f2", "#ef4444"]

NAV = [("✉", "Hộp thư đến"), ("➤", "Đã gửi"), ("🗎", "Thư nháp")]


# ---------- Hàm nhỏ hỗ trợ ----------
def gui_thu(to, subject, body):
    """HÀM GIẢ (backend chưa có phần gửi thư SMTP). Trả về (thành công?, thông báo)."""
    return True, "Gửi thư thành công"


def loi_text(e):
    """Đổi lỗi kỹ thuật của backend thành câu dễ hiểu."""
    s = str(e)
    if isinstance(e, MailError):
        if "login failed" in s:
            return "Đăng nhập thất bại. Hãy dùng Mật khẩu ứng dụng (16 ký tự) của Gmail."
        if "Cannot connect" in s:
            return "Không kết nối được máy chủ Gmail. Hãy kiểm tra mạng."
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
    return {"uid": h["uid"], "name": name, "email": addr, "subject": h["subject"], "date": h["date"],
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
        self.current, self.token = 0, 0
        self.email, self.pw, self.client = "", "", None
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
            self.client.logout()
            self.client.login(self.email, self.pw)
            return getattr(self.client, ten)(*a, **k)

    def dong(self):
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
        self.status = ctk.CTkLabel(card, text="", wraplength=340, height=40)
        self.status.pack(pady=(0, 30))

    def set_status(self, text, color):
        self.status.configure(text=text, text_color=color)

    def on_connect(self):
        email, pw = self.e_email.get().strip(), self.e_pass.get().replace(" ", "")
        if "@" not in email:
            return self.set_status("✖ Email không hợp lệ", RED)
        if not pw:
            return self.set_status("✖ Bạn chưa nhập mật khẩu", RED)
        self.btn.configure(state="disabled", text="Đang kết nối...")
        self.set_status("⏳ Đang kết nối, vui lòng chờ...", GRAY)
        self.chay_nen(lambda: ImapClient().login(email, pw),
                      lambda c, e: self.finish_connect(email, pw, c, e))

    def finish_connect(self, email, pw, client, err):
        if err:
            self.set_status("✖ " + loi_text(err), RED)
            self.btn.configure(state="normal", text="Kết nối")
        else:
            self.client, self.email, self.pw = client, email, pw
            self.set_status("✔ Kết nối thành công", GREEN)
            self.after(800, self.open_mail)

    def open_mail(self):
        self.login.destroy()
        self.build_sidebar()
        self.build_main()
        self.load_mails()

    # ---------- Tải thư: loading / lỗi / thành công ----------
    def load_mails(self):
        for w in self.listbox.winfo_children():
            w.destroy()
        self.token += 1
        self.notice("⏳ Đang tải thư...", GRAY)
        self.chay_nen(lambda: self.goi("list_emails", page=1, page_size=30), self.finish_load)

    def finish_load(self, r, err):
        if err:
            return self.notice("✖ " + loi_text(err), RED, retry=True)
        self.mails = [doi_thu(h) for h in r["emails"]]
        self.head_lbl.configure(text=f"Hộp thư đến ({r['total']})")
        if self.mails:
            self.show(0)
        else:
            self.notice("Hộp thư trống", GRAY)

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
        if self.mails:
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

        for i, (icon, name) in enumerate(NAV):
            f = ctk.CTkFrame(sb, height=38, corner_radius=8, fg_color=SEL if i == 0 else "transparent")
            f.pack(fill="x", pady=1)
            ctk.CTkLabel(f, text=icon, width=28, text_color=BLUE if i == 0 else "#374151").pack(side="left", padx=(8, 0))
            ctk.CTkLabel(f, text=name, text_color=BLUE if i == 0 else "#111827",
                         font=("Segoe UI", 13, "bold" if i == 0 else "normal")).pack(side="left", padx=6)

    # ---------- Khu vực chính ----------
    def build_main(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=(0, 16), pady=16)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(main, fg_color="transparent")
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        ctk.CTkEntry(top, placeholder_text="🔍  Tìm kiếm email...", height=42, corner_radius=21,
                     border_width=0, fg_color="#e8eef7", width=500).pack(side="left")
        ctk.CTkLabel(top, text=f"{self.email}  ⌄", text_color="#374151").pack(side="right", padx=8)

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
        for i, m in enumerate(self.mails):
            item = ctk.CTkFrame(self.listbox, corner_radius=8, fg_color=SEL if i == self.current else "transparent")
            item.pack(fill="x", pady=2)
            item.grid_columnconfigure(1, weight=1)
            avatar(item, m["letter"], m["color"]).grid(row=0, column=0, rowspan=2, padx=10, pady=10, sticky="n")
            ctk.CTkLabel(item, text=m["name"][:24], font=("Segoe UI", 13, "bold"), anchor="w").grid(row=0, column=1, sticky="w", pady=(8, 0))
            ctk.CTkLabel(item, text=gio(m["date"]), text_color=GRAY, font=("Segoe UI", 11)).grid(row=0, column=2, padx=10)
            ctk.CTkLabel(item, text=m["subject"][:40], anchor="w", font=("Segoe UI", 12)).grid(row=1, column=1, sticky="w", pady=(0, 10))
            click_all(item, lambda i=i: self.show(i))

    # ---------- Đọc thư ----------
    def show(self, i):
        self.token += 1
        tk, self.current = self.token, i
        self.render_list()
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
        uid = m["uid"]
        self.chay_nen(lambda: self.goi("get_email", uid), lambda f, e: self.finish_read(tk, m, f, e))

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
        self.chay_nen(lambda: self.goi("download_attachment", uid, index, "downloads"), xong)

    # ---------- Màn hình soạn thư ----------
    def compose(self, to="", subject="", body=""):
        self.token += 1
        d = self.detail
        for w in d.winfo_children():
            w.destroy()
        ctk.CTkLabel(d, text="Soạn thư mới", font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=24, pady=(20, 10))

        self.c_to = ctk.CTkEntry(d, placeholder_text="Đến (email người nhận)", height=42)
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

        self.c_status = ctk.CTkLabel(d, text="", height=28)
        self.c_status.pack(anchor="w", padx=24)
        bar = ctk.CTkFrame(d, fg_color="transparent")
        bar.pack(anchor="w", padx=24, pady=(0, 24))
        self.c_send = ctk.CTkButton(bar, text="➤  Gửi", width=120, height=40, corner_radius=20,
                                    fg_color=BLUE, command=self.on_send)
        self.c_send.pack(side="left", padx=(0, 10))
        ctk.CTkButton(bar, text="Hủy", width=100, height=40, corner_radius=20, fg_color=WHITE,
                      text_color="#111827", border_width=1, border_color="#d1d5db",
                      hover_color="#f3f4f6", command=self.back).pack(side="left")

    def on_send(self):
        to, sub, body = self.c_to.get().strip(), self.c_sub.get().strip(), self.c_body.get("1.0", "end").strip()
        if "@" not in to:
            return self.c_status.configure(text="✖ Email người nhận không hợp lệ", text_color=RED)
        if not sub:
            return self.c_status.configure(text="✖ Bạn chưa nhập tiêu đề", text_color=RED)
        self.c_send.configure(state="disabled", text="Đang gửi...")
        self.c_status.configure(text="⏳ Đang gửi thư...", text_color=GRAY)
        self.after(1000, lambda: self.finish_send(to, sub, body))  # giả lập, chờ backend gửi thư

    def finish_send(self, to, sub, body):
        ok, msg = gui_thu(to, sub, body)
        if ok:
            self.c_status.configure(text="✔ " + msg, text_color=GREEN)
            self.after(1000, self.back)
        else:
            self.c_status.configure(text="✖ " + msg, text_color=RED)
            self.c_send.configure(state="normal", text="➤  Gửi")


if __name__ == "__main__":
    App().mainloop()