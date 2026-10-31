"""Tìm kiếm và lọc thư chưa đọc."""
from ui.constants import GRAY, RED
from ui.helpers import doi_thu, loi_text


class SearchMixin:
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
