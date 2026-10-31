"""Thông báo thư mới (NewMailWatcher chạy kết nối riêng) và cập nhật số lượng thư mục."""
import queue

from backend.imap_client import NewMailWatcher
from ui.constants import GREEN


class WatcherMixin:
    def start_watcher(self):
        self.watcher = NewMailWatcher(
            "imap.gmail.com", 993, self.email, self.pw,
            on_new=lambda items: self.new_q.put(("new", items)),
            folder="INBOX", interval=30, token_provider=self.token_provider,
            on_error=lambda err: self.new_q.put(("error", err))
        )
        self.watcher.start()
        self.after(1000, self.poll_new)
        self.after(60000, self.periodic_nav_counts)

    def periodic_nav_counts(self):
        """Refresh folder badges periodically, including changes made outside SmartMail."""
        if not self.watcher or not self.client:
            return
        self.refresh_nav_counts()
        self.after(60000, self.periodic_nav_counts)

    def poll_new(self):   # luồng chính lấy kết quả từ hàng đợi (Tkinter không an toàn khi gọi từ luồng khác)
        if not self.watcher:
            return
        try:
            while True:
                kind, payload = self.new_q.get_nowait()
                if kind == "error":
                    self.bell.configure(
                        text="⚠ Kết nối thông báo bị gián đoạn",
                        fg_color="#d97706", hover_color="#b45309"
                    )
                    if not self.bell.winfo_ismapped():
                        self.bell.pack(side="right", padx=8)
                    continue

                new = payload
                if not new:
                    continue
                self.new_count += len(new)
                # Cập nhật số thư chưa đọc và số lượng các thư mục từ IMAP.
                self.refresh_nav_counts()
                self.bell.configure(
                    text=f"🔔 {self.new_count} thư mới: {new[0]['subject'][:24]}",
                    fg_color=GREEN, hover_color="#15803d"
                )
                if not self.bell.winfo_ismapped():
                    self.bell.pack(side="right", padx=8)

                # Đồng bộ lại danh sách Inbox nhưng không tự mở thư mới.
                if self.nav_i == 0 and self.folder == "INBOX" and not self.search_active:
                    self.load_mails(auto_open=False)
        except queue.Empty:
            pass
        if self.watcher:
            self.after(1000, self.poll_new)

    def open_new(self):
        self.bell.pack_forget()
        self.new_count = 0
        self.bell.configure(fg_color=GREEN, hover_color="#15803d")
        self.switch(0)
