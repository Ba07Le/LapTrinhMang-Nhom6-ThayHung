"""Đọc thư: hiển thị nội dung, tệp đính kèm và các nút trả lời / chuyển tiếp."""
import customtkinter as ctk

from tkinter import messagebox
from email.utils import getaddresses
from ui.constants import BLUE, GRAY, GREEN, RED, WHITE
from ui.helpers import avatar, dung_luong, gio, html_sang_text, loi_text
from backend.html_support import looks_like_html, sanitize_email_html, html_to_plain


class ReaderMixin:
    def show(self, i):
        self.token += 1
        prev = self.current
        tk, self.current = self.token, i
        self.highlight(prev, i)
        m = self.mails[i]
        d = self.detail
        for w in d.winfo_children():
            w.destroy()

        ctk.CTkLabel(d, text=m["subject"], font=("Segoe UI", 20, "bold"), anchor="w", justify="left",
                     wraplength=850).pack(fill="x", padx=24, pady=(20, 10))

        sender = ctk.CTkFrame(d, fg_color="transparent")
        sender.pack(fill="x", padx=24, pady=10)
        avatar(sender, m["letter"], m["color"], 48).pack(side="left")
        info = ctk.CTkFrame(sender, fg_color="transparent")
        info.pack(side="left", padx=12)
        # Always show the real From and To headers; never assume To is the logged-in account.
        if m.get("is_sent"):
            display_name = self.email
            display_email = m.get("sender_email") or self.email
        else:
            display_name = m["name"]
            display_email = m["email"]
        ctk.CTkLabel(info, text=display_name, font=("Segoe UI", 14, "bold"), anchor="w").pack(anchor="w")
        ctk.CTkLabel(info, text=display_email, text_color=GRAY, anchor="w").pack(anchor="w")
        recipient_label = ctk.CTkLabel(info, text="Đến: " + (m.get("to") or "Đang tải người nhận..."),
                                       text_color=GRAY, anchor="w", justify="left", wraplength=680)
        recipient_label.pack(anchor="w")
        self._recipient_label = recipient_label
        ctk.CTkLabel(sender, text=gio(m["date"], True), text_color=GRAY).pack(side="right", anchor="n")

        # Nút trả lời (đặt ở đáy trước để luôn thấy)
        btns = ctk.CTkFrame(d, fg_color="transparent")
        btns.pack(fill="x", padx=24, pady=(4, 12))
        old = lambda: self.cache.get(m["uid"], {}).get("text", "")
        actions = [("↩  Trả lời", lambda: self.compose((m.get("email") if m.get("is_sent") else m["email"]), "Re: " + m["subject"], "\n\n--- Thư gốc ---\n"+old())),
                   ("↩↩  Trả lời tất cả", lambda: self.reply_all(m)),
                   ("↪  Chuyển tiếp", lambda: self.compose("", "Fwd: " + m["subject"],
                                                          "\n\n--- Thư chuyển tiếp ---\n" + old()))]
        actions.append(('🗑  Xóa / Thùng rác',lambda: self.move_selected(m,restore=False)))
        if self.nav_i==4:
            actions.append(('↩  Khôi phục',lambda: self.move_selected(m,restore=True)))
        actions.append(('Chưa đọc',lambda: self.mark_selected_unread(m)))
        for index, (text, cmd) in enumerate(actions):
            row = index // 3
            column = index % 3
            ctk.CTkButton(btns, text=text, command=cmd, corner_radius=8, height=36,
                          font=("Segoe UI", 12), fg_color="#eef4ff",
                          text_color="#1c4f94", hover_color="#dceaff").grid(
                              row=row, column=column, sticky="ew", padx=4, pady=4)
        for col in range(3):
            btns.grid_columnconfigure(col, weight=1)

        # Nội dung: lấy từ backend (get_email), có loading / lỗi
        self.body_box = ctk.CTkFrame(d, fg_color="transparent")
        self.body_box.pack(fill="both", expand=True, padx=24, pady=(10, 0))
        if m["uid"] in self.cache:
            cached = self.cache[m["uid"]]
            recipient_label.configure(text="Đến: " + (cached.get("to") or m.get("to") or "(Không có người nhận)"))
            return self.render_body(m, cached)
        ctk.CTkLabel(self.body_box, text="⏳ Đang tải nội dung thư...", text_color=GRAY).pack(pady=30)
        uid, folder = m["uid"], self.folder
        self.chay_nen(lambda: self.goi("get_email", uid, folder=folder), lambda f, e: self.finish_read(tk, m, f, e))

    def finish_read(self, tk, m, f, err):
        if tk != self.token:   # người dùng đã bấm sang thư khác -> bỏ kết quả này
            return
        for w in self.body_box.winfo_children():
            w.destroy()
        if err:
            ctk.CTkLabel(self.body_box, text="✖ " + loi_text(err), text_color=RED, wraplength=600).pack(pady=(30, 8))
            ctk.CTkButton(self.body_box, text="↻  Thử lại", fg_color=BLUE, corner_radius=20,
                          command=lambda: self.show(self.current)).pack()
            return
        raw_text = f["body_text"].strip()
        raw_html = f["body_html"].strip()
        # Legacy emails may have been sent with raw HTML inside text/plain.
        # Render those too, but keep their plain-text alternative readable.
        if not raw_html and looks_like_html(raw_text):
            raw_html = raw_text
            raw_text = ""
        text = raw_text or html_to_plain(raw_html) or "(Thư không có nội dung)"
        # The full RFC 5322 To header is authoritative, including multiple recipients.
        if self._recipient_label.winfo_exists():
            self._recipient_label.configure(text="Đến: " + (f.get("to") or "(Không có người nhận)"))
        recipients=[addr for _,addr in getaddresses([f.get('to',''),f.get('cc','')])]
        self.cache[m["uid"]] = {"text": text, "html": raw_html, "attachments": f["attachments"],"recipients":recipients, "to": f.get("to", ""), "from": f.get("from", "")}
        self.render_body(m, self.cache[m["uid"]])
        if not m["seen"]:   # đánh dấu đã đọc trên Gmail
            m["seen"] = True
            uid, folder = m["uid"], self.folder
            self.chay_nen(lambda: self.goi("mark_seen", uid, folder=folder),
                          lambda *_: self.refresh_nav_counts())
            self.refresh_row(self.current)

    def render_body(self, m, info):
        box, att = self.body_box, info["attachments"]
        for w in box.winfo_children():
            w.destroy()

        if att:
            af = ctk.CTkFrame(box, fg_color="transparent")
            af.pack(side="bottom", fill="x")
            ctk.CTkLabel(af, text=f"📎  {len(att)} tệp đính kèm", font=("Segoe UI", 13, "bold")).pack(anchor="w")
            for a in att:
                name = a["filename"]
                ext = (name.rsplit(".", 1)[-1][:4] if "." in name else "FILE").upper()
                f = ctk.CTkFrame(af, fg_color="transparent", border_width=1, border_color="#e5e7eb", corner_radius=8)
                f.pack(fill="x", pady=4)
                ctk.CTkLabel(f, text=ext, width=40, height=36, corner_radius=6, fg_color="#2563eb",
                             text_color="white", font=("Segoe UI", 11, "bold")).pack(side="left", padx=12, pady=8)
                ctk.CTkLabel(f, text=f"{name}\n{dung_luong(a['size'])}", justify="left", anchor="w").pack(side="left")
                ctk.CTkButton(f, text="Tải về", width=72, fg_color="transparent", text_color="#111827",
                              hover_color="#f3f4f6", font=("Segoe UI", 16),
                              command=lambda idx=a["index"]: self.tai_dinh_kem(m["uid"], idx)).pack(side="right", padx=10)
            self.att_status = ctk.CTkLabel(af, text="", wraplength=600, justify="left")
            self.att_status.pack(anchor="w", pady=(2, 0))

        html_source = info.get("html", "")
        view = ctk.CTkFrame(box, fg_color="transparent")
        view.pack(fill="both", expand=True, pady=(0, 8))
        mode_bar = ctk.CTkFrame(view, fg_color="transparent")
        mode_bar.pack(fill="x", pady=(0, 5))
        content_area = ctk.CTkFrame(view, fg_color="transparent")
        content_area.pack(fill="both", expand=True)

        def show_plain():
            for child in content_area.winfo_children():
                child.destroy()
            tb = ctk.CTkTextbox(content_area, fg_color=WHITE, font=("Segoe UI", 14), wrap="word")
            tb.pack(fill="both", expand=True)
            tb.insert("1.0", info["text"])
            tb.configure(state="disabled")

        def show_html():
            for child in content_area.winfo_children():
                child.destroy()
            try:
                from tkinterweb import HtmlFrame
                frame = HtmlFrame(content_area, messages_enabled=False)
                frame.pack(fill="both", expand=True)
                frame.load_html(sanitize_email_html(html_source))
            except Exception as exc:
                # Keep the email readable even without the optional HTML renderer.
                for child in content_area.winfo_children():
                    child.destroy()
                show_plain()
                ctk.CTkLabel(mode_bar, text="Không thể hiển thị HTML. Cài tkinterweb để bật chế độ HTML.",
                             text_color=RED, font=("Segoe UI", 11)).pack(side="left", padx=8)

        if html_source:
            ctk.CTkButton(mode_bar, text="Xem HTML", width=110, height=30,
                          command=show_html).pack(side="left", padx=(0, 6))
            ctk.CTkButton(mode_bar, text="Xem văn bản", width=115, height=30,
                          fg_color="#eaf1ff", text_color=BLUE,
                          command=show_plain).pack(side="left")
            show_html()
        else:
            show_plain()

    def tai_dinh_kem(self, uid, index):
        self.att_status.configure(text="⏳ Đang tải tệp...", text_color=GRAY)

        def xong(path, err):
            if self.att_status.winfo_exists():
                self.att_status.configure(
                    text=("✖ " + loi_text(err)) if err else f"✔ Đã lưu tại: {path}",
                    text_color=RED if err else GREEN)
        folder = self.folder
        self.chay_nen(lambda: self.goi("download_attachment", uid, index, "downloads", folder=folder), xong)

    def reply_all(self,m):
        info=self.cache.get(m['uid'],{})
        others=info.get('recipients',[])
        primary = m.get('email', '')
        addresses=([primary] if primary and primary.lower() != self.email.lower() else []) + [x for x in others if x.lower() not in (primary.lower(), self.email.lower())]
        self.compose(', '.join(dict.fromkeys(addresses)),'Re: '+m['subject'],'\n\n--- Thư gốc ---\n'+info.get('text',''))

    def move_selected(self,m,restore=False):
        if not messagebox.askyesno('Xác nhận','Khôi phục về Inbox?' if restore else 'Chuyển email vào Thùng rác?'):return
        uid,folder=m['uid'],self.folder
        op='restore_email' if restore else 'trash_email'
        def done(result,err):
            if err:messagebox.showerror('Lỗi IMAP',str(err))
            else:self.load_mails(auto_open=False);self.refresh_nav_counts()
        self.chay_nen(lambda:self.goi(op,uid,folder=folder),done)

    def mark_selected_unread(self,m):
        uid,folder=m['uid'],self.folder
        def done(result,err):
            if err:messagebox.showerror('Lỗi IMAP',str(err))
            else:self.load_mails(auto_open=False);self.refresh_nav_counts()
        self.chay_nen(lambda:self.goi('mark_unseen',uid,folder=folder),done)
