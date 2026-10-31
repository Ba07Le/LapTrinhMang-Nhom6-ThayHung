"""Bố cục chính: thanh bên trái (thư mục) và khu vực chính (tìm kiếm, danh sách, nội dung)."""
from tkinter import StringVar

import customtkinter as ctk

from ui.constants import BLUE, GREEN, NAV, SEL, WHITE
from ui.helpers import click_all


class LayoutMixin:
    # ---------- Thanh bên trái ----------
    def build_sidebar(self):
        sb = ctk.CTkFrame(self, width=240, fg_color="transparent")
        sb.grid(row=0, column=0, sticky="ns", padx=16, pady=16)

        ctk.CTkLabel(sb, text="✉  SmartMail", font=("Segoe UI", 22, "bold"),
                     text_color=BLUE).pack(anchor="w")
        ctk.CTkLabel(sb, text="Kết nối thế giới qua email", text_color="#6b7280",
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
