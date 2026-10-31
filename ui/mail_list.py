"""Danh sách thư: tải, phân trang, vẽ từng dòng và thông báo trạng thái."""
import customtkinter as ctk

from backend.mail_utils import MailError
from ui.constants import BLUE, GRAY, MAX_LOAD, NAV, PAGE_SIZE, RED, SEL
from ui.helpers import avatar, click_all, doi_thu, gio, loi_text


class MailListMixin:
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

    # ---------- Vẽ danh sách ----------
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

    # ---------- Thông báo ở khung bên phải ----------
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
