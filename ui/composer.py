"""Soạn thư và gửi thư qua SMTP (có đính kèm tệp)."""
from tkinter import filedialog

import customtkinter as ctk

from backend.email_service import send_email
from ui.constants import BLUE, GRAY, GREEN, RED, WHITE
from ui.helpers import loi_text


class ComposerMixin:
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
