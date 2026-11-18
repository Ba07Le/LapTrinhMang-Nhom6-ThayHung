"""Bố cục chính: thanh bên trái (thư mục) và khu vực chính (tìm kiếm, danh sách, nội dung)."""
from tkinter import StringVar, PanedWindow

import customtkinter as ctk

from ui.constants import BLUE, GREEN, NAV, SEL, WHITE
from ui.helpers import click_all


class LayoutMixin:
    # ---------- Thanh bên trái ----------
    def build_sidebar(self):
        sb = ctk.CTkFrame(self, width=222, fg_color="#ffffff", corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)
        ctk.CTkLabel(sb, text="✉  SmartMail", font=("Segoe UI", 25, "bold"),
                     text_color=BLUE).pack(anchor="w", padx=18, pady=(26, 2))
        ctk.CTkLabel(sb, text="Hộp thư điện tử của bạn", text_color="#64748B",
                     font=("Segoe UI", 12)).pack(anchor="w", padx=20, pady=(0, 24))
        ctk.CTkButton(sb, text="＋  Soạn thư mới", height=46, corner_radius=10,
                      fg_color=BLUE, font=("Segoe UI", 14, "bold"),
                      command=self.compose).pack(fill="x", padx=14, pady=(0, 22))
        ctk.CTkLabel(sb, text="HỘP THƯ", text_color="#64748B",
                     font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=20, pady=(0, 7))
        self.nav_items = []
        self.nav_counts = {"inbox_unread": 0, "sent": 0, "drafts": 0, "all": 0, "trash": 0}
        for i, (symbol, name) in enumerate(NAV):
            f = ctk.CTkFrame(sb, height=42, corner_radius=9, fg_color="transparent")
            f.pack(fill="x", padx=12, pady=2)
            li = ctk.CTkLabel(f, text=symbol, width=26, font=("Segoe UI Symbol", 15))
            li.pack(side="left", padx=(8, 0))
            ln = ctk.CTkLabel(f, text=name, font=("Segoe UI", 13))
            ln.pack(side="left", padx=6)
            click_all(f, lambda i=i: self.switch(i))
            self.nav_items.append((f, li, ln))
        self.style_nav()
        ctk.CTkLabel(sb, text="CÔNG CỤ", text_color="#64748B",
                     font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=20, pady=(24, 8))
        tools = [('Lịch gửi và lịch sử', self.open_history),
                 ('Gửi email hàng loạt', self.open_bulk),
                 ('Bản nháp trên máy', self.open_drafts),
                 ('Mẫu email HTML', self.open_templates)]
        for label, action in tools:
            ctk.CTkButton(sb, text=label, anchor="w", height=39,
                          font=("Segoe UI", 12), fg_color="transparent",
                          text_color="#25354a", hover_color="#eaf1ff",
                          corner_radius=9, command=action).pack(fill="x", padx=12, pady=2)

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
        main.grid(row=0, column=1, sticky="nsew", padx=18, pady=18)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(main, fg_color="transparent")
        self.top_bar = top
        self.account_menu = None
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        self.search_entry = ctk.CTkEntry(
            top, placeholder_text="Tìm kiếm email trong thư mục hiện tại...", height=43,
            corner_radius=10, border_width=1, border_color="#dce4ef",
            fg_color=WHITE, width=330, font=("Segoe UI", 13)
        )
        self.search_entry.pack(side="left")
        self.search_entry.bind("<Return>", lambda e: self.on_search())
        self.search_mode = StringVar(value="Toàn bộ nội dung")
        self.search_mode_menu = ctk.CTkOptionMenu(
            top, variable=self.search_mode,
            values=["Toàn bộ nội dung", "Người gửi", "Tiêu đề", "Chưa đọc"],
            width=150, height=42, corner_radius=9, font=("Segoe UI", 12),
            command=lambda _v: None
        )
        self.search_mode_menu.pack(side="left", padx=(8, 8))
        ctk.CTkButton(top, text="Tìm kiếm", width=95, height=42, corner_radius=9,
                      fg_color=BLUE, font=("Segoe UI", 12, "bold"),
                      command=self.on_search).pack(side="left")
        self.account_button = ctk.CTkButton(
            top, text=f"{self.email}  ▾", width=220, height=42,
            fg_color=WHITE, border_width=1, border_color="#dce4ef",
            hover_color="#eaf1ff", text_color="#25354a", anchor="center",
            corner_radius=9, font=("Segoe UI", 12), command=self.toggle_account_menu
        )
        self.account_button.pack(side="right")
        self.bell = ctk.CTkButton(top, text="Thư mới", height=34,
                                  corner_radius=9, fg_color=GREEN,
                                  hover_color="#15803d", command=self.open_new)

        # Thanh chia kéo được: giữ chiều rộng ban đầu như giao diện cũ.
        self.mail_split = PanedWindow(
            main, orient="horizontal", sashwidth=8, sashpad=0,
            sashrelief="flat", showhandle=False,
            bg="#dce4ef", bd=0, relief="flat", opaqueresize=True,
        )
        self.mail_split.grid(row=1, column=0, columnspan=2, sticky="nsew")

        box = ctk.CTkFrame(self.mail_split, width=335, fg_color=WHITE, corner_radius=14,
                           border_width=1, border_color="#e4eaf2")
        # Không dùng grid cố định cho danh sách: PanedWindow điều khiển độ rộng.
        self.mail_split.add(box, minsize=230, width=335, stretch="never", padx=0, pady=0)
        head = ctk.CTkFrame(box, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(17, 10))
        self.head_lbl = ctk.CTkLabel(head, text="Hộp thư đến",
                                     font=("Segoe UI", 17, "bold"), text_color="#17263b")
        self.head_lbl.pack(side="left")
        ctk.CTkButton(head, text="Làm mới", width=74, height=32,
                      fg_color="#eaf1ff", text_color=BLUE, hover_color="#dbeafe",
                      font=("Segoe UI", 12), command=self.load_mails).pack(side="right")
        ctk.CTkFrame(box, height=1, fg_color="#edf1f6").pack(fill="x", padx=12, pady=(0, 4))
        self.listbox = ctk.CTkScrollableFrame(box, fg_color="transparent")
        self.listbox.pack(fill="both", expand=True, padx=5, pady=(0, 8))

        self.detail = ctk.CTkFrame(self.mail_split, fg_color=WHITE, corner_radius=14,
                                   border_width=1, border_color="#e4eaf2")
        self.mail_split.add(self.detail, minsize=360, stretch="always", padx=0, pady=0)
        # Chỉ đặt vị trí mặc định một lần; sau đó người dùng kéo tùy ý.
        def place_initial_sash():
            if self.mail_split.winfo_exists() and self.mail_split.winfo_width() > 700:
                self.mail_split.sash_place(0, 335, 0)
            else:
                self.mail_split.after(80, place_initial_sash)
        self.mail_split.after_idle(place_initial_sash)
