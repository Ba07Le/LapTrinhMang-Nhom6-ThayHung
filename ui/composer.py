"""Soạn thư và gửi thư qua SMTP (có đính kèm tệp)."""
from tkinter import filedialog

import customtkinter as ctk

from backend.email_service import send_email
from backend import automation as store
from ui.constants import BLUE, GRAY, GREEN, RED, WHITE
from ui.helpers import loi_text


class ComposerMixin:
    def compose(self, to="", subject="", body=""):
        self.token += 1
        d = self.detail
        for w in d.winfo_children():
            w.destroy()
        self.c_attachments = []
        self.c_html_mode = ctk.BooleanVar(value=False)
        header = ctk.CTkFrame(d, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 6))
        ctk.CTkLabel(header, text="Soạn email mới", font=("Segoe UI", 21, "bold"),
                     text_color="#17263b").pack(side="left")
        ctk.CTkLabel(header, text="Gửi qua Gmail SMTP", text_color=GRAY,
                     font=("Segoe UI", 12)).pack(side="right")
        ctk.CTkLabel(d, text="NGƯỜI NHẬN", font=("Segoe UI", 11, "bold"),
                     text_color="#526277").pack(anchor="w", padx=24, pady=(9, 2))
        self.c_to = ctk.CTkEntry(d, placeholder_text="Ví dụ: ban@example.com, nhom@example.com",
                                 height=41, font=("Segoe UI", 13), border_color="#dce4ef")
        self.c_to.pack(fill="x", padx=24)
        ctk.CTkLabel(d, text="TIÊU ĐỀ", font=("Segoe UI", 11, "bold"),
                     text_color="#526277").pack(anchor="w", padx=24, pady=(12, 2))
        self.c_sub = ctk.CTkEntry(d, placeholder_text="Nhập tiêu đề email...", height=41,
                                  font=("Segoe UI", 13), border_color="#dce4ef")
        self.c_sub.pack(fill="x", padx=24)
        ctk.CTkLabel(d, text="NỘI DUNG EMAIL", font=("Segoe UI", 11, "bold"),
                     text_color="#526277").pack(anchor="w", padx=24, pady=(12, 2))
        self.c_body = ctk.CTkTextbox(d, border_width=1, border_color="#dce4ef",
                                     fg_color=WHITE, font=("Segoe UI", 14),
                                     corner_radius=8, wrap="word")
        self.c_body.pack(fill="both", expand=True, padx=24, pady=(0, 6))
        if to:
            self.c_to.insert(0, to)
        if subject:
            self.c_sub.insert(0, subject)
        self.c_body.insert("1.0", body)
        ctk.CTkCheckBox(d, text="Gửi nội dung dưới dạng HTML (chỉ dùng mã HTML tin cậy)",
                        variable=self.c_html_mode, font=("Segoe UI", 12),
                        checkbox_width=19, checkbox_height=19).pack(anchor="w", padx=24, pady=5)
        attach_row = ctk.CTkFrame(d, fg_color="transparent")
        attach_row.pack(fill="x", padx=24, pady=(5, 4))
        self.c_attach_btn = ctk.CTkButton(attach_row, text="Đính kèm tệp", width=135, height=35,
                                          fg_color="#eaf1ff", text_color=BLUE,
                                          hover_color="#dbeafe", command=self.chon_dinh_kem)
        self.c_attach_btn.pack(side="left")
        self.c_attach_label = ctk.CTkLabel(attach_row, text="Chưa chọn tệp đính kèm",
                                           text_color=GRAY, anchor="w", font=("Segoe UI", 12))
        self.c_attach_label.pack(side="left", padx=12, fill="x", expand=True)
        self.c_status = ctk.CTkLabel(d, text="", height=26, wraplength=780,
                                     justify="left", font=("Segoe UI", 12))
        self.c_status.pack(anchor="w", padx=24)
        bar = ctk.CTkFrame(d, fg_color="transparent")
        bar.pack(fill="x", padx=24, pady=(0, 18))
        self.c_send = ctk.CTkButton(bar, text="Gửi email", width=116, height=40,
                                    corner_radius=9, fg_color=BLUE,
                                    font=("Segoe UI", 13, "bold"), command=self.on_send)
        self.c_send.pack(side="left", padx=(0, 8))
        ctk.CTkButton(bar, text="Lên lịch gửi", width=108, height=40,
                      fg_color="#eaf1ff", text_color=BLUE, hover_color="#dbeafe",
                      command=self.schedule_current).pack(side="left", padx=4)
        ctk.CTkButton(bar, text="Lưu bản nháp", width=112, height=40,
                      fg_color="#eaf1ff", text_color=BLUE, hover_color="#dbeafe",
                      command=self.save_current_draft).pack(side="left", padx=4)
        ctk.CTkButton(bar, text="Hủy soạn", width=92, height=40,
                      fg_color="#f2f4f8", text_color="#344256",
                      hover_color="#e3e9f0", command=self.back).pack(side="right")

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
        html_mode = self.c_html_mode.get()
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
                html_body=body if html_mode else None,
            )

        self._sending_to,self._sending_subject=to,sub
        self.chay_nen(work, self.finish_send)

    def finish_send(self, result, err):
        if err:
            store.log(self.email,self._sending_to,self._sending_subject,'failed',str(err))
            self.c_status.configure(text="✖ " + loi_text(err), text_color=RED)
            self.c_send.configure(state="normal", text="➤  Gửi")
            self.c_attach_btn.configure(state="normal")
            return

        refused = result.get("refused", {})
        store.log(self.email,self._sending_to,self._sending_subject,
                  'partial' if refused else 'accepted',str(result.get('message_id','')))
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
