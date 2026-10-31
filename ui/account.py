"""Menu tài khoản và đăng xuất."""
from tkinter import messagebox

import customtkinter as ctk

from backend import oauth_google
from ui.constants import GRAY, RED, WHITE


class AccountMixin:
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
