import customtkinter as ctk

ctk.set_appearance_mode("light")

BLUE, BG, WHITE, GRAY, SEL = "#1a6cf0", "#f4f7fc", "#ffffff", "#6b7280", "#e6f0ff"

GREEN, RED = "#16a34a", "#dc2626"

NAV = [("✉", "Hộp thư đến", 6), ("➤", "Đã gửi", 0), ("🗎", "Thư nháp", 2)]

# (chữ cái, màu, tên, email, tiêu đề, nội dung, giờ, có đính kèm?)
MAILS = [
    ("Q", "#2563eb", "Quân Lê Hồng", "lehongquan268@gmail.com", "Re: Tiến độ đồ án",
     "Ok bạn, mình đã nhận được file.\nSẽ xem và phản hồi sớm nhé.\n\nCảm ơn bạn!\n\n--\nQuân Lê Hồng",
     "10:24", True),
    ("G", "#ea4335", "Google", "no-reply@google.com", "Cảnh báo bảo mật",
     "Mới đây, chúng tôi phát hiện có hoạt động đăng nhập mới vào tài khoản của bạn.", "08:15", False),
    ("T", "#22a559", "Thắng Nguyễn Quốc", "thang@gmail.com", "Tài liệu nhóm",
     "Mình đã cập nhật file tài liệu trên Drive. Bạn xem giúp nhé!", "Hôm qua", False),
    ("M", "#7c3aed", "Marketing Team", "mkt@shop.com", "Khuyến mãi đặc biệt",
     "Chương trình khuyến mãi tháng 4 với nhiều ưu đãi hấp dẫn...", "Hôm qua", False),
    ("N", "#f59e0b", "Nguyễn Văn A", "vana@gmail.com", "Lịch họp nhóm",
     "Chiều nay 14h chúng ta họp online nhé!", "Hôm qua", False),
    ("F", "#1877f2", "Facebook", "security@facebook.com", "Thông báo đăng nhập",
     "Bạn vừa đăng nhập vào tài khoản Facebook từ thiết bị mới...", "Thứ 5", False),
    ("T", "#ef4444", "Trần Thị B", "thib@gmail.com", "Tài liệu tham khảo",
     "Mình gửi kèm một số tài liệu tham khảo cho đồ án nhé!", "Thứ 4", False),
]


def ket_noi(email, password):
    """HÀM GIẢ (chờ backend). Trả về (thành công?, thông báo).
    Sau này chỉ cần thay nội dung hàm này bằng hàm đăng nhập thật."""
    if "@" not in email:
        return False, "Email không hợp lệ"
    if len(password) < 4:
        return False, "Mật khẩu không đúng hoặc quá ngắn"
    return True, "Kết nối thành công"


GIA_LAP_LOI_MANG = False  # đổi thành True để thử màn hình báo lỗi khi tải thư


def lay_thu():
    """HÀM GIẢ (chờ backend). Trả về (True, danh sách thư) hoặc (False, thông báo lỗi)."""
    if GIA_LAP_LOI_MANG:
        return False, "Không tải được thư. Hãy kiểm tra kết nối mạng."
    return True, MAILS


def gui_thu(to, subject, body):
    """HÀM GIẢ (chờ backend). Trả về (thành công?, thông báo)."""
    return True, "Gửi thư thành công"


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
        self.current = 0
        self.email = ""
        self.mails = []
        self.show_login()

    # ---------- Màn hình đăng nhập ----------
    def show_login(self):
        self.login = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.login.place(relx=0, rely=0, relwidth=1, relheight=1)

        card = ctk.CTkFrame(self.login, fg_color=WHITE, corner_radius=16)
        card.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(card, text="✉  SmartMail", font=("Segoe UI", 28, "bold"),
                     text_color=BLUE).pack(padx=50, pady=(40, 2))
        ctk.CTkLabel(card, text="Kết nối tài khoản email của bạn", text_color=GRAY).pack(pady=(0, 24))

        self.e_email = ctk.CTkEntry(card, placeholder_text="Email", width=340, height=44)
        self.e_email.pack(pady=6)
        self.e_pass = ctk.CTkEntry(card, placeholder_text="Mật khẩu", show="•", width=340, height=44)
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
        email, pw = self.e_email.get().strip(), self.e_pass.get()
        self.btn.configure(state="disabled", text="Đang kết nối...")
        self.set_status("⏳ Đang kết nối, vui lòng chờ...", GRAY)
        self.after(1200, lambda: self.finish_connect(email, pw))  # giả lập thời gian chờ

    def finish_connect(self, email, pw):
        ok, msg = ket_noi(email, pw)
        if ok:
            self.email = email
            self.set_status("✔ " + msg, GREEN)
            self.after(800, self.open_mail)
        else:
            self.set_status("✖ " + msg, RED)
            self.btn.configure(state="normal", text="Kết nối")

    def open_mail(self):
        self.login.destroy()
        self.build_sidebar()
        self.build_main()
        self.load_mails()

    # ---------- Tải thư: loading / lỗi / thành công ----------
    def load_mails(self):
        for w in self.listbox.winfo_children():
            w.destroy()
        self.notice("⏳ Đang tải thư...", GRAY)
        self.after(1200, self.finish_load)  # giả lập thời gian chờ

    def finish_load(self):
        ok, data = lay_thu()
        if ok:
            self.mails = data
            self.show(0)
        else:
            self.notice("✖ " + data, RED, retry=True)

    def notice(self, text, color, retry=False):
        for w in self.detail.winfo_children():
            w.destroy()
        box = ctk.CTkFrame(self.detail, fg_color="transparent")
        box.place(relx=0.5, rely=0.45, anchor="center")
        ctk.CTkLabel(box, text=text, text_color=color, font=("Segoe UI", 16)).pack(pady=8)
        if retry:
            ctk.CTkButton(box, text="↻  Thử lại", fg_color=BLUE, corner_radius=20,
                          command=self.load_mails).pack(pady=8)

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

        for i, (icon, name, count) in enumerate(NAV):
            self.row(sb, icon, name, count, selected=(i == 0))

    def row(self, parent, icon, name, count, selected=False, icon_color=None):
        f = ctk.CTkFrame(parent, height=38, corner_radius=8, fg_color=SEL if selected else "transparent")
        f.pack(fill="x", pady=1)
        color = icon_color or (BLUE if selected else "#374151")
        ctk.CTkLabel(f, text=icon, width=28, text_color=color).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(f, text=name, text_color=BLUE if selected else "#111827",
                     font=("Segoe UI", 13, "bold" if selected else "normal")).pack(side="left", padx=6)
        if count:
            ctk.CTkLabel(f, text=str(count), width=22, height=22, corner_radius=11,
                         fg_color=SEL if selected else "#eef0f4", text_color=BLUE if selected else GRAY,
                         font=("Segoe UI", 11)).pack(side="right", padx=8)

    # ---------- Khu vực chính ----------
    def build_main(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=(0, 16), pady=16)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(1, weight=1)

        # Thanh trên cùng
        top = ctk.CTkFrame(main, fg_color="transparent")
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        ctk.CTkEntry(top, placeholder_text="🔍  Tìm kiếm email...", height=42, corner_radius=21,
                     border_width=0, fg_color="#e8eef7", width=500).pack(side="left")
        ctk.CTkLabel(top, text=f"{self.email}  ⌄", text_color="#374151").pack(side="right", padx=8)

        # Danh sách thư
        box = ctk.CTkFrame(main, width=400, fg_color=WHITE, corner_radius=12)
        box.grid(row=1, column=0, sticky="ns", padx=(0, 12))
        box.grid_propagate(False)
        ctk.CTkLabel(box, text="Hộp thư đến (6)", font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=16, pady=14)
        self.listbox = ctk.CTkScrollableFrame(box, fg_color="transparent")
        self.listbox.pack(fill="both", expand=True)

        # Chi tiết thư
        self.detail = ctk.CTkFrame(main, fg_color=WHITE, corner_radius=12)
        self.detail.grid(row=1, column=1, sticky="nsew")

    def render_list(self):
        for w in self.listbox.winfo_children():
            w.destroy()
        for i, (letter, color, name, _, subject, body, time, _) in enumerate(self.mails):
            item = ctk.CTkFrame(self.listbox, corner_radius=8, fg_color=SEL if i == self.current else "transparent")
            item.pack(fill="x", pady=2)
            avatar(item, letter, color).grid(row=0, column=0, rowspan=3, padx=10, pady=10, sticky="n")
            item.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(item, text=name, font=("Segoe UI", 13, "bold"), anchor="w").grid(row=0, column=1, sticky="w")
            ctk.CTkLabel(item, text=time, text_color=GRAY, font=("Segoe UI", 11)).grid(row=0, column=2, padx=10)
            ctk.CTkLabel(item, text=subject, anchor="w", font=("Segoe UI", 12)).grid(row=1, column=1, sticky="w")
            ctk.CTkLabel(item, text=body.split("\n")[0][:42] + "…", text_color=GRAY, anchor="w",
                         font=("Segoe UI", 11)).grid(row=2, column=1, sticky="w", pady=(0, 8))
            click_all(item, lambda i=i: self.show(i))

    def show(self, i):
        self.current = i
        self.render_list()
        letter, color, name, email, subject, body, time, has_att = self.mails[i]
        d = self.detail
        for w in d.winfo_children():
            w.destroy()

        # Tiêu đề
        head = ctk.CTkFrame(d, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=(20, 10))
        ctk.CTkLabel(head, text=subject, font=("Segoe UI", 20, "bold")).pack(side="left")
        ctk.CTkLabel(head, text="●  Công việc", fg_color=SEL, text_color=BLUE, corner_radius=12,
                     height=24, font=("Segoe UI", 11)).pack(side="left", padx=12)

        # Người gửi
        sender = ctk.CTkFrame(d, fg_color="transparent")
        sender.pack(fill="x", padx=24, pady=10)
        avatar(sender, letter, color, 48).pack(side="left")
        info = ctk.CTkFrame(sender, fg_color="transparent")
        info.pack(side="left", padx=12)
        ctk.CTkLabel(info, text=name, font=("Segoe UI", 14, "bold"), anchor="w").pack(anchor="w")
        ctk.CTkLabel(info, text=email, text_color=GRAY, anchor="w").pack(anchor="w")
        ctk.CTkLabel(info, text=f"Đến: {self.email}", text_color=GRAY, anchor="w").pack(anchor="w")
        ctk.CTkLabel(sender, text=f"{time}, 12/04/2025", text_color=GRAY).pack(side="right", anchor="n")

        # Nội dung
        ctk.CTkLabel(d, text=body, justify="left", anchor="w", wraplength=600,
                     font=("Segoe UI", 14)).pack(fill="x", padx=24, pady=20)

        # Đính kèm
        if has_att:
            ctk.CTkLabel(d, text="📎  2 tệp đính kèm", font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=24)
            for icon, color, fname, size in [("W", "#2563eb", "BaoCao_TienDo.docx", "1.2 MB"),
                                             ("PDF", "#ef4444", "Code_SmartMail.zip", "2.8 MB")]:
                f = ctk.CTkFrame(d, fg_color="transparent", border_width=1, border_color="#e5e7eb", corner_radius=8)
                f.pack(fill="x", padx=24, pady=6)
                ctk.CTkLabel(f, text=icon, width=36, height=36, corner_radius=6, fg_color=color,
                             text_color="white", font=("Segoe UI", 11, "bold")).pack(side="left", padx=12, pady=10)
                ctk.CTkLabel(f, text=f"{fname}\n{size}", justify="left", anchor="w").pack(side="left")
                ctk.CTkLabel(f, text="⬇", font=("Segoe UI", 16)).pack(side="right", padx=16)

        # Nút trả lời
        btns = ctk.CTkFrame(d, fg_color="transparent")
        btns.pack(side="bottom", anchor="w", padx=24, pady=24)
        actions = [("↩  Trả lời", lambda: self.compose(email, "Re: " + subject)),
                   ("↩↩  Trả lời tất cả", lambda: self.compose(email, "Re: " + subject)),
                   ("↪  Chuyển tiếp", lambda: self.compose("", "Fwd: " + subject,
                                                          "\n\n--- Thư chuyển tiếp ---\n" + body))]
        for text, cmd in actions:
            ctk.CTkButton(btns, text=text, command=cmd, corner_radius=20, height=38, fg_color=WHITE, text_color="#111827",
                          border_width=1, border_color="#d1d5db", hover_color="#f3f4f6").pack(side="left", padx=(0, 10))

    # ---------- Màn hình soạn thư ----------
    def compose(self, to="", subject="", body=""):
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
                      hover_color="#f3f4f6", command=lambda: self.show(self.current)).pack(side="left")

    def on_send(self):
        to, sub, body = self.c_to.get().strip(), self.c_sub.get().strip(), self.c_body.get("1.0", "end").strip()
        if "@" not in to:
            return self.c_status.configure(text="✖ Email người nhận không hợp lệ", text_color=RED)
        if not sub:
            return self.c_status.configure(text="✖ Bạn chưa nhập tiêu đề", text_color=RED)
        self.c_send.configure(state="disabled", text="Đang gửi...")
        self.c_status.configure(text="⏳ Đang gửi thư...", text_color=GRAY)
        self.after(1000, lambda: self.finish_send(to, sub, body))  # giả lập thời gian chờ

    def finish_send(self, to, sub, body):
        ok, msg = gui_thu(to, sub, body)
        if ok:
            self.c_status.configure(text="✔ " + msg, text_color=GREEN)
            self.after(1000, lambda: self.show(self.current))
        else:
            self.c_status.configure(text="✖ " + msg, text_color=RED)
            self.c_send.configure(state="normal", text="➤  Gửi")


if __name__ == "__main__":
    App().mainloop()