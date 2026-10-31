"""Màn hình đăng nhập: mật khẩu ứng dụng và đăng nhập bằng Google (OAuth2)."""
import customtkinter as ctk

from backend import oauth_google
from backend.imap_client import ImapClient
from ui.constants import BG, BLUE, GRAY, GREEN, RED, WHITE
from ui.helpers import loi_text


class LoginMixin:
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

    # ---------- Đăng nhập bằng mật khẩu ứng dụng ----------
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
