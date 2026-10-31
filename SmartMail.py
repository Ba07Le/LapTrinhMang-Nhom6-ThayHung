import queue
import threading

import customtkinter as ctk

from ui.account import AccountMixin
from ui.composer import ComposerMixin
from ui.constants import BG
from ui.layout import LayoutMixin
from ui.login import LoginMixin
from ui.mail_list import MailListMixin
from ui.reader import ReaderMixin
from ui.search import SearchMixin
from ui.watcher import WatcherMixin

ctk.set_appearance_mode("light")


class App(LoginMixin, AccountMixin, LayoutMixin, MailListMixin,
          SearchMixin, WatcherMixin, ReaderMixin, ComposerMixin, ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SmartMail - Email Client")
        self.geometry("1280x780")
        self.configure(fg_color=BG)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.current, self.token, self.load_id = 0, 0, 0
        self.nav_i, self.folder, self.folders = 0, "INBOX", {}
        self.page, self.total, self.loading_more, self.rows, self.more_btn = 1, 0, False, [], None
        self.watcher, self.new_q, self.new_count = None, queue.Queue(), 0
        self.search_active = False
        self.email, self.pw, self.client, self.token_provider = "", "", None, None
        self.mails, self.cache = [], {}
        self.lock = threading.Lock()   # imaplib không chạy song song được -> xếp hàng từng việc
        self.protocol("WM_DELETE_WINDOW", self.dong)
        self.show_login()

    # ---------- Chạy việc mạng ở luồng riêng (giao diện không bị đơ) ----------
    def chay_nen(self, ham, xong):
        """Chạy ham() ở luồng riêng. Xong thì gọi xong(kết_quả, lỗi) ở luồng chính."""
        kq = {}

        def lam():
            try:
                with self.lock:
                    kq["v"] = ham()
            except Exception as e:
                kq["e"] = e

        threading.Thread(target=lam, daemon=True).start()

        def cho():
            if "v" in kq or "e" in kq:
                xong(kq.get("v"), kq.get("e"))
            else:
                self.after(100, cho)
        cho()

    def goi(self, ten, *a, **k):
        """Gọi hàm của backend; nếu mất kết nối thì đăng nhập lại rồi thử thêm 1 lần."""
        try:
            return getattr(self.client, ten)(*a, **k)
        except Exception:
            self.client.reconnect()
            return getattr(self.client, ten)(*a, **k)

    def dong(self):
        if self.watcher:
            self.watcher.stop()
        if self.client:
            self.client.logout()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
