"""Automation windows: schedule, bulk send, local drafts/templates and history."""
import json
import threading
import time
from datetime import datetime,timezone
from tkinter import filedialog,messagebox
import customtkinter as ctk
from backend import automation as store
from backend.bulk_mail import read_recipients,render
from backend.email_service import send_email
from ui.helpers import loi_text

class AutomationMixin:
    def _window(self, title):
        # Keep tool windows associated with SmartMail's main window.
        w = ctk.CTkToplevel(self)
        w.title(title)
        w.geometry('760x600')
        w.transient(self)
        # Windows/CustomTkinter may restack a Toplevel during initialization.
        # Raise and focus it once the window manager has mapped the window.
        def bring_to_front():
            if w.winfo_exists():
                w.lift(self)
                w.focus_force()
        w.after(200, bring_to_front)
        return w
    def _send_args(self,to,subject,body,attachments=(),html_mode=False):
        return dict(sender=self.email,to=to,subject=subject,body=body,attachments=attachments,
                    password=self.pw or None,token_provider=self.token_provider,html_body=body if html_mode else None)
    def _send_and_log(self,to,subject,body,attachments=(),html_mode=False):
        try:
            result=send_email(**self._send_args(to,subject,body,attachments,html_mode))
            refused=result.get('refused',{})
            status='partial' if refused else 'accepted'
            store.log(self.email,to,subject,status,str(refused) if refused else str(result.get('message_id','')))
            return status
        except Exception as exc:
            store.log(self.email,to,subject,'failed',str(exc))
            raise
    def save_current_draft(self):
        store.save_draft(self.email,self.c_to.get(),self.c_sub.get(),self.c_body.get('1.0','end-1c'),self.c_attachments)
        self.c_status.configure(text='Đã lưu bản nháp trên máy (không đồng bộ lên Gmail)',text_color='green')
    def schedule_current(self):
        """Lên lịch gửi bằng các ô chọn ngày giờ, không yêu cầu nhập chuỗi ISO."""
        from calendar import monthrange
        from datetime import timedelta
        w=self._window('Lên lịch gửi email | SmartMail')
        w.geometry('760x580'); w.minsize(630,490); w.configure(fg_color='#F3F6FB')
        page=ctk.CTkScrollableFrame(w,fg_color='#F3F6FB'); page.pack(fill='both',expand=True,padx=16,pady=12)
        ctk.CTkLabel(page,text='LÊN LỊCH GỬI EMAIL',font=('Segoe UI',23,'bold'),text_color='#14243A').pack(anchor='w',padx=12,pady=(10,2))
        ctk.CTkLabel(page,text='Chọn thời điểm gửi theo giờ địa phương trên máy tính.',font=('Segoe UI',13),text_color='#526277').pack(anchor='w',padx=12,pady=(0,14))
        card=ctk.CTkFrame(page,fg_color='white',corner_radius=12);card.pack(fill='x',padx=10,pady=6)
        to=self.c_to.get().strip();sub=self.c_sub.get().strip()
        ctk.CTkLabel(card,text='THÔNG TIN EMAIL',font=('Segoe UI',14,'bold'),text_color='#14243A').pack(anchor='w',padx=18,pady=(14,4))
        for title,value in [('Người nhận',to or '(Chưa nhập)'),('Tiêu đề',sub or '(Chưa nhập)')]:
            ctk.CTkLabel(card,text=f'{title}: {value}',font=('Segoe UI',13),text_color='#334155',anchor='w',wraplength=640).pack(fill='x',padx=18,pady=3)
        ctk.CTkLabel(card,text='NGÀY GỬI',font=('Segoe UI',14,'bold'),text_color='#14243A').pack(anchor='w',padx=18,pady=(20,6))
        now_local=datetime.now().astimezone(); suggested=now_local.replace(second=0,microsecond=0)
        from datetime import timedelta
        suggested+=timedelta(minutes=5)
        controls=ctk.CTkFrame(card,fg_color='transparent');controls.pack(fill='x',padx=18,pady=(0,14))
        def picker(label,values,initial,width):
            col=ctk.CTkFrame(controls,fg_color='transparent');col.pack(side='left',padx=(0,10))
            ctk.CTkLabel(col,text=label,font=('Segoe UI',12),text_color='#526277').pack(anchor='w',pady=(0,5))
            widget=ctk.CTkComboBox(col,values=values,width=width,height=38,state='readonly',font=('Segoe UI',13));widget.set(str(initial));widget.pack();return widget
        day=picker('Ngày',[f'{i:02d}' for i in range(1,32)],f'{suggested.day:02d}',85)
        month=picker('Tháng',[f'{i:02d}' for i in range(1,13)],f'{suggested.month:02d}',90)
        year=picker('Năm',[str(i) for i in range(now_local.year,now_local.year+6)],str(suggested.year),105)
        hour=picker('Giờ',[f'{i:02d}' for i in range(24)],f'{suggested.hour:02d}',85)
        minute=picker('Phút',[f'{i:02d}' for i in range(60)],f'{suggested.minute:02d}',85)
        hint=ctk.CTkLabel(card,text='Lưu ý: SmartMail phải đang mở và đã đăng nhập khi đến giờ gửi.',font=('Segoe UI',12),text_color='#64748B',wraplength=600)
        hint.pack(anchor='w',padx=18,pady=(0,12))
        def save():
            try:
                local=datetime(int(year.get()),int(month.get()),int(day.get()),int(hour.get()),int(minute.get()),tzinfo=now_local.tzinfo)
                if local<=datetime.now().astimezone():raise ValueError('Vui lòng chọn thời gian trong tương lai.')
                if not to or not sub:raise ValueError('Cần nhập người nhận và tiêu đề ở màn hình Soạn thư.')
                store.queue(self.email,to,sub,self.c_body.get('1.0','end-1c'),self.c_attachments,local.astimezone(timezone.utc).isoformat(),self.c_html_mode.get())
                messagebox.showinfo('Đã lưu lịch','Email đã được đưa vào lịch gửi. Giữ SmartMail mở và đăng nhập để gửi đúng giờ.',parent=w);w.destroy()
            except Exception as exc:messagebox.showerror('Không thể lưu lịch',str(exc),parent=w)
        buttons=ctk.CTkFrame(page,fg_color='transparent');buttons.pack(fill='x',padx=12,pady=14)
        ctk.CTkButton(buttons,text='Lưu lịch gửi',font=('Segoe UI',14,'bold'),height=42,width=175,command=save).pack(side='left')
        ctk.CTkButton(buttons,text='Hủy',height=42,width=110,fg_color='#E2E8F0',text_color='#334155',hover_color='#CBD5E1',command=w.destroy).pack(side='left',padx=10)
    def start_scheduler(self):
        store.recover_interrupted(self.email)
        self._scheduler_busy=False
        self._scheduler_active=True
        self.after(2000,self._scheduler_tick)
    def _scheduler_tick(self):
        if not getattr(self,'_scheduler_active',False):return
        if not self._scheduler_busy:
            self._scheduler_busy=True
            def work():
                try:
                    for job in store.pending(self.email):
                        if not store.claim(job['id']):continue
                        try:
                            status=self._send_and_log(job['recipient'],job['subject'],job['body'],json.loads(job['attachments']),bool(job['html_mode']))
                            store.finish(job['id'],'sent' if status=='accepted' else 'needs_review',status)
                        except Exception as exc:
                            # Unknown SMTP outcome: do not automatically retry to avoid duplicates.
                            store.finish(job['id'],'needs_review',str(exc))
                finally:self._scheduler_busy=False
            threading.Thread(target=work,daemon=True).start()
        self.after(30000,self._scheduler_tick)
    def open_drafts(self):
        w=self._window('Bản nháp lưu trên máy | SmartMail')
        w.geometry('900x680');w.minsize(700,500);w.configure(fg_color='#F3F6FB')
        ctk.CTkLabel(w,text='BẢN NHÁP LƯU TRÊN MÁY',font=('Segoe UI',22,'bold'),text_color='#14243A').pack(anchor='w',padx=24,pady=(20,2))
        ctk.CTkLabel(w,text='Mở để tiếp tục soạn hoặc xóa bản nháp. Dữ liệu này chưa đồng bộ với Gmail.',font=('Segoe UI',13),text_color='#64748B').pack(anchor='w',padx=24,pady=(0,12))
        top=ctk.CTkFrame(w,fg_color='transparent');top.pack(fill='x',padx=24,pady=(0,8))
        search=ctk.CTkEntry(top,height=40,placeholder_text='Tìm theo người nhận hoặc tiêu đề...',font=('Segoe UI',13));search.pack(side='left',fill='x',expand=True,padx=(0,10))
        ctk.CTkButton(top,text='Làm mới',width=100,height=40,command=lambda:refresh()).pack(side='right')
        area=ctk.CTkScrollableFrame(w,fg_color='#FFFFFF',corner_radius=12);area.pack(fill='both',expand=True,padx=24,pady=(0,20))
        def refresh(*_):
            for child in area.winfo_children():child.destroy()
            rows=[r for r in store.drafts(self.email) if search.get().lower().strip() in (r['subject']+' '+r['recipient']).lower()]
            if not rows:
                ctk.CTkLabel(area,text='Chưa có bản nháp phù hợp.',font=('Segoe UI',14),text_color='#64748B').pack(pady=45);return
            for r in rows:
                line=ctk.CTkFrame(area,fg_color='#F6F9FE',corner_radius=10);line.pack(fill='x',padx=10,pady=6)
                buttons=ctk.CTkFrame(line,fg_color='transparent');buttons.pack(side='right',padx=12,pady=12)
                info=ctk.CTkFrame(line,fg_color='transparent');info.pack(side='left',fill='x',expand=True,padx=14,pady=10)
                ctk.CTkLabel(info,text=r['subject'] or '(Không có tiêu đề)',font=('Segoe UI',14,'bold'),text_color='#14243A',anchor='w',wraplength=460).pack(fill='x')
                ctk.CTkLabel(info,text='Đến: '+(r['recipient'] or '(Chưa nhập)')+'  •  '+r['created'][:16].replace('T',' '),font=('Segoe UI',12),text_color='#64748B',anchor='w',wraplength=460).pack(fill='x',pady=(4,0))
                def open_draft(row=r):
                    self.compose(row['recipient'],row['subject'],row['body'])
                    self.c_attachments=json.loads(row['attachments'])
                    self.c_attach_label.configure(text='; '.join(self.c_attachments) or 'Chưa có tệp')
                    w.destroy()
                def delete_draft(row=r):
                    if messagebox.askyesno('Xóa bản nháp','Bạn muốn xóa bản nháp này?',parent=w):
                        store.remove_draft(row['id'],self.email);refresh()
                ctk.CTkButton(buttons,text='Mở để sửa',width=105,command=open_draft).pack(side='left',padx=4)
                ctk.CTkButton(buttons,text='Xóa',width=65,fg_color='#B91C1C',hover_color='#991B1B',command=delete_draft).pack(side='left',padx=4)
        search.bind('<KeyRelease>',refresh);refresh()

    def open_templates(self):
        w=self._window('Quản lý mẫu email | SmartMail');w.geometry('960x760');w.minsize(760,590);w.configure(fg_color='#F3F6FB')
        page=ctk.CTkScrollableFrame(w,fg_color='#F3F6FB');page.pack(fill='both',expand=True,padx=12,pady=12)
        ctk.CTkLabel(page,text='MẪU EMAIL HTML / VĂN BẢN',font=('Segoe UI',22,'bold'),text_color='#14243A').pack(anchor='w',padx=14,pady=(8,3))
        ctk.CTkLabel(page,text='Tạo mẫu để sử dụng lại khi soạn thư. Chỉ bật HTML với nội dung đáng tin cậy.',font=('Segoe UI',13),text_color='#64748B').pack(anchor='w',padx=14,pady=(0,12))
        card=ctk.CTkFrame(page,fg_color='white',corner_radius=12);card.pack(fill='x',padx=12,pady=(0,12))
        ctk.CTkLabel(card,text='1. TẠO MẪU MỚI',font=('Segoe UI',16,'bold'),text_color='#14243A').pack(anchor='w',padx=18,pady=(14,8))
        def field(label,placeholder):
            ctk.CTkLabel(card,text=label,font=('Segoe UI',13),text_color='#334155').pack(anchor='w',padx=18)
            entry=ctk.CTkEntry(card,height=40,placeholder_text=placeholder,font=('Segoe UI',13));entry.pack(fill='x',padx=18,pady=(4,12));return entry
        name=field('Tên mẫu *','Ví dụ: Thông báo lịch học')
        sub=field('Tiêu đề email','Ví dụ: Thông báo dành cho sinh viên')
        ctk.CTkLabel(card,text='Nội dung mẫu',font=('Segoe UI',13),text_color='#334155').pack(anchor='w',padx=18)
        body=ctk.CTkTextbox(card,height=170,font=('Segoe UI',13),wrap='word',border_width=1,border_color='#CBD5E1');body.pack(fill='x',padx=18,pady=(4,10))
        ctk.CTkLabel(card,text='Có thể nhập HTML, ví dụ: <h2>Xin chào</h2><p>Thông báo...</p>',font=('Segoe UI',12),text_color='#64748B').pack(anchor='w',padx=18,pady=(0,8))
        def save():
            if not name.get().strip():return messagebox.showwarning('Thiếu thông tin','Vui lòng nhập tên mẫu.',parent=w)
            if not body.get('1.0','end-1c').strip():return messagebox.showwarning('Thiếu thông tin','Vui lòng nhập nội dung mẫu.',parent=w)
            store.save_template(self.email,name.get().strip(),sub.get().strip(),body.get('1.0','end-1c'))
            name.delete(0,'end');sub.delete(0,'end');body.delete('1.0','end');refresh()
            messagebox.showinfo('Đã lưu','Đã lưu mẫu email trên máy.',parent=w)
        ctk.CTkButton(card,text='Lưu mẫu email',height=40,width=160,font=('Segoe UI',13,'bold'),command=save).pack(anchor='w',padx=18,pady=(0,16))
        saved=ctk.CTkFrame(page,fg_color='white',corner_radius=12);saved.pack(fill='x',padx=12,pady=(0,12))
        ctk.CTkLabel(saved,text='2. MẪU ĐÃ LƯU',font=('Segoe UI',16,'bold'),text_color='#14243A').pack(anchor='w',padx=18,pady=(14,8))
        list_area=ctk.CTkFrame(saved,fg_color='transparent');list_area.pack(fill='x',padx=12,pady=(0,14))
        def refresh():
            for child in list_area.winfo_children():child.destroy()
            rows=store.templates(self.email)
            if not rows:ctk.CTkLabel(list_area,text='Chưa có mẫu email nào.',font=('Segoe UI',13),text_color='#64748B').pack(pady=18)
            for r in rows:
                line=ctk.CTkFrame(list_area,fg_color='#F4F7FC');line.pack(fill='x',padx=6,pady=4)
                def use(t=r):
                    self.compose('',t['subject'],t['body']);self.c_html_mode.set(bool('<' in t['body'] and '>' in t['body']));w.destroy()
                def delete(t=r):
                    if messagebox.askyesno('Xóa mẫu',f"Xóa mẫu '{t['name']}'?",parent=w):store.remove_template(t['id'],self.email);refresh()
                ctk.CTkButton(line,text='Sử dụng',width=90,command=use).pack(side='right',padx=5,pady=8)
                ctk.CTkButton(line,text='Xóa',width=65,fg_color='#B91C1C',hover_color='#991B1B',command=delete).pack(side='right',padx=3,pady=8)
                ctk.CTkLabel(line,text=r['name']+'  —  '+(r['subject'] or '(Không có tiêu đề)'),font=('Segoe UI',13),text_color='#14243A',anchor='w',wraplength=570).pack(side='left',fill='x',expand=True,padx=12)
        refresh()

    def open_history(self):
        w=self._window('Lịch gửi và lịch sử | SmartMail');w.geometry('960x730');w.minsize(750,540);w.configure(fg_color='#F3F6FB')
        ctk.CTkLabel(w,text='LỊCH GỬI VÀ LỊCH SỬ EMAIL',font=('Segoe UI',22,'bold'),text_color='#14243A').pack(anchor='w',padx=24,pady=(18,3))
        ctk.CTkLabel(w,text='Theo dõi email đã lên lịch và các lần gửi SMTP được ghi nhận trên máy.',font=('Segoe UI',13),text_color='#64748B').pack(anchor='w',padx=24,pady=(0,12))
        toolbar=ctk.CTkFrame(w,fg_color='transparent');toolbar.pack(fill='x',padx=24,pady=(0,10))
        mode=ctk.CTkSegmentedButton(toolbar,values=['Lịch gửi','Lịch sử SMTP'],font=('Segoe UI',13),command=lambda _:refresh());mode.pack(side='left');mode.set('Lịch gửi')
        ctk.CTkButton(toolbar,text='Làm mới',width=100,command=lambda:refresh()).pack(side='right')
        area=ctk.CTkScrollableFrame(w,fg_color='white',corner_radius=12);area.pack(fill='both',expand=True,padx=24,pady=(0,20))
        def refresh():
            for child in area.winfo_children():child.destroy()
            is_jobs=mode.get()=='Lịch gửi';rows=store.jobs(self.email) if is_jobs else store.history(self.email)
            if not rows:
                ctk.CTkLabel(area,text='Chưa có '+('lịch gửi nào.' if is_jobs else 'lịch sử gửi SMTP.'),font=('Segoe UI',14),text_color='#64748B').pack(pady=50);return
            statuses={'pending':'Đang chờ gửi','sent':'Đã gửi','cancelled':'Đã hủy','sending':'Đang gửi','needs_review':'Cần kiểm tra','accepted':'SMTP đã chấp nhận','failed':'Gửi thất bại','partial':'Một phần bị từ chối'}
            for r in rows:
                line=ctk.CTkFrame(area,fg_color='#F6F9FE',corner_radius=10);line.pack(fill='x',padx=10,pady=6)
                info=ctk.CTkFrame(line,fg_color='transparent');info.pack(side='left',fill='x',expand=True,padx=14,pady=10)
                date=r['due'] if is_jobs else r['created'];date=date[:16].replace('T',' ')
                if is_jobs:
                    try:date=datetime.fromisoformat(r['due']).astimezone().strftime('%d/%m/%Y %H:%M')
                    except (ValueError,TypeError):pass
                ctk.CTkLabel(info,text=r['subject'] or '(Không có tiêu đề)',font=('Segoe UI',14,'bold'),text_color='#14243A',anchor='w',wraplength=590).pack(fill='x')
                ctk.CTkLabel(info,text=f"Đến: {r['recipient']}  |  {date}",font=('Segoe UI',12),text_color='#64748B',anchor='w',wraplength=590).pack(fill='x',pady=(3,0))
                ctk.CTkLabel(info,text='Trạng thái: '+statuses.get(r['status'],r['status']),font=('Segoe UI',12,'bold'),text_color='#2563EB' if r['status'] in ('pending','accepted','sent') else '#B45309',anchor='w').pack(fill='x',pady=(3,0))
                if r.get('error') or r.get('detail'):
                    ctk.CTkLabel(info,text='Chi tiết: '+str(r.get('error') or r.get('detail'))[:180],font=('Segoe UI',11),text_color='#64748B',anchor='w',wraplength=590).pack(fill='x')
                if is_jobs and r['status']=='pending':
                    def cancel_job(job=r):
                        if messagebox.askyesno('Hủy lịch gửi','Bạn muốn hủy lịch gửi này?',parent=w):store.cancel(job['id'],self.email);refresh()
                    ctk.CTkButton(line,text='Hủy lịch',width=90,fg_color='#B91C1C',hover_color='#991B1B',command=cancel_job).pack(side='right',padx=12)
        refresh()
    def open_bulk(self):
        """Vietnamese bulk-mail wizard with import, preview, confirmation and progress."""
        import re
        from pathlib import Path
        from tkinter import ttk
        from email.utils import parseaddr

        w = self._window('Gửi email hàng loạt | SmartMail')
        w.geometry('960x760')
        w.minsize(780, 620)
        w.configure(fg_color='#F3F6FB')
        font = ('Segoe UI', 13)
        small = ('Segoe UI', 12)
        title_font = ('Segoe UI', 23, 'bold')
        blue, dark, muted = '#2563EB', '#14243A', '#5D6B80'
        state = {'rows': [], 'path': '', 'sending': False, 'finished': False}

        # Use a scrollable main surface so labels are not clipped on small displays.
        page = ctk.CTkScrollableFrame(w, fg_color='#F3F6FB', corner_radius=0)
        page.pack(fill='both', expand=True, padx=12, pady=(10, 4))
        ctk.CTkLabel(page, text='GỬI EMAIL HÀNG LOẠT', font=title_font,
                     text_color=dark, anchor='w').pack(fill='x', padx=16, pady=(8, 0))
        ctk.CTkLabel(page, text='Nhập danh sách → Soạn nội dung → Xem trước → Xác nhận gửi',
                     font=small, text_color=muted, anchor='w').pack(fill='x', padx=16, pady=(0, 12))

        def section(name, hint):
            frame = ctk.CTkFrame(page, fg_color='white', corner_radius=12)
            frame.pack(fill='x', padx=14, pady=(0, 12))
            ctk.CTkLabel(frame, text=name, font=('Segoe UI', 16, 'bold'),
                         text_color=dark, anchor='w').pack(fill='x', padx=16, pady=(12, 1))
            ctk.CTkLabel(frame, text=hint, font=small, text_color=muted,
                         anchor='w', justify='left', wraplength=830).pack(fill='x', padx=16, pady=(0, 9))
            return frame

        # 1. Import file.
        f1 = section('1. Danh sách người nhận',
                     'Chọn CSV hoặc Excel (.xlsx). Bắt buộc có cột email; có thể thêm ten, lop, ma_sv...')
        file_row = ctk.CTkFrame(f1, fg_color='transparent')
        file_row.pack(fill='x', padx=16, pady=(0, 8))
        file_entry = ctk.CTkEntry(file_row, font=font, height=40,
                                  placeholder_text='Chưa chọn tệp CSV hoặc Excel')
        file_entry.pack(side='left', fill='x', expand=True, padx=(0, 8))
        file_entry.configure(state='disabled')
        import_btn = ctk.CTkButton(file_row, text='Chọn tệp', font=font,
                                   width=130, height=40, fg_color=blue)
        import_btn.pack(side='right')
        file_info = ctk.CTkLabel(f1, text='Chưa có danh sách. Giới hạn 100 người nhận/lượt.',
                                 font=small, text_color=muted, anchor='w')
        file_info.pack(fill='x', padx=16, pady=(0, 6))
        # ttk treeview supports compact tabular preview with real columns.
        preview_frame = ctk.CTkFrame(f1, fg_color='#EDF2F9', corner_radius=8)
        preview_frame.pack(fill='x', padx=16, pady=(0, 12))
        tree = ttk.Treeview(preview_frame, columns=('stt','email','ten','khac'),
                            show='headings', height=5, selectmode='browse')
        for key, caption, width in [('stt','STT',50), ('email','Email người nhận',270),
                                    ('ten','Tên',170), ('khac','Thông tin khác',270)]:
            tree.heading(key, text=caption)
            tree.column(key, width=width, minwidth=45, stretch=(key != 'stt'))
        tree.pack(fill='x', padx=8, pady=8)
        ctk.CTkLabel(f1, text='Ví dụ: email,ten,lop  →  ban@example.com,Nguyễn Văn A,CNTT1',
                     font=small, text_color=muted, anchor='w').pack(fill='x', padx=16, pady=(0, 12))

        # 2. Compose.
        f2 = section('2. Soạn email',
                     'Dùng $ten, $lop, $email... để thay bằng dữ liệu tương ứng của từng người nhận.')
        ctk.CTkLabel(f2, text='Tiêu đề email *', font=font,
                     text_color=dark, anchor='w').pack(fill='x', padx=16)
        subject = ctk.CTkEntry(f2, font=font, height=40,
                               placeholder_text='Ví dụ: Thông báo lịch học cho $ten')
        subject.pack(fill='x', padx=16, pady=(5, 10))
        ctk.CTkLabel(f2, text='Nội dung email *', font=font,
                     text_color=dark, anchor='w').pack(fill='x', padx=16)
        body = ctk.CTkTextbox(f2, height=145, font=font, wrap='word',
                              border_width=1, border_color='#CAD4E2')
        body.pack(fill='x', padx=16, pady=(5, 8))
        body.insert('1.0', 'Xin chào $ten,\n\nĐây là email thông báo dành cho lớp $lop.\n\nTrân trọng!')
        ctk.CTkLabel(f2, text='Mỗi người nhận một email riêng. Không hiển thị địa chỉ của người khác.',
                     font=small, text_color=muted, anchor='w').pack(fill='x', padx=16, pady=(0, 12))

        # 3. Review and send.
        f3 = section('3. Xem trước và gửi',
                     'Kiểm tra email mẫu và số lượng trước khi xác nhận. Không thể thu hồi thư đã được SMTP chấp nhận.')
        actions = ctk.CTkFrame(f3, fg_color='transparent')
        actions.pack(fill='x', padx=16, pady=(0, 8))
        preview_btn = ctk.CTkButton(actions, text='Xem trước email đầu tiên', font=font,
                                    height=40, fg_color='#E8F0FE', text_color=blue,
                                    hover_color='#D7E7FD')
        preview_btn.pack(side='left', padx=(0, 10))
        send_btn = ctk.CTkButton(actions, text='Xác nhận và gửi', font=('Segoe UI', 13, 'bold'),
                                 height=40, fg_color=blue, state='disabled')
        send_btn.pack(side='left')
        preview_box = ctk.CTkTextbox(f3, height=145, font=small, wrap='word',
                                     fg_color='#F5F8FC', text_color=dark)
        preview_box.pack(fill='x', padx=16, pady=(0, 8))
        preview_box.insert('1.0', 'Sau khi chọn danh sách, nhấn “Xem trước email đầu tiên”.')
        preview_box.configure(state='disabled')
        progress = ctk.CTkProgressBar(f3, progress_color=blue)
        progress.pack(fill='x', padx=16, pady=(6, 4))
        progress.set(0)
        status = ctk.CTkLabel(f3, text='Sẵn sàng. Chưa gửi email nào.',
                              font=small, text_color=muted, anchor='w', wraplength=820)
        status.pack(fill='x', padx=16, pady=(0, 14))

        def set_preview(value):
            preview_box.configure(state='normal')
            preview_box.delete('1.0', 'end')
            preview_box.insert('1.0', value)
            preview_box.configure(state='disabled')

        def valid_address(address):
            address = address.strip()
            parsed = parseaddr(address)[1]
            return (parsed == address and len(address) <= 254 and
                    re.fullmatch(r'[^\s@,;]+@[^\s@,;]+\.[^\s@,;]+', address) is not None)

        def refresh_send_state(*_):
            if state['sending'] or state['finished']:
                send_btn.configure(state='disabled')
            elif state['rows'] and subject.get().strip() and body.get('1.0','end-1c').strip():
                send_btn.configure(state='normal')
            else:
                send_btn.configure(state='disabled')

        def choose_file():
            if state['sending']: return
            path = filedialog.askopenfilename(parent=w, title='Chọn danh sách người nhận',
                   filetypes=[('CSV và Excel', '*.csv *.xlsx'), ('CSV', '*.csv'), ('Excel', '*.xlsx')])
            if not path: return
            try:
                rows = read_recipients(path)
                invalid = [(i, r.get('email','')) for i,r in enumerate(rows,2)
                           if not valid_address(str(r.get('email','')))]
                if invalid:
                    raise ValueError('Địa chỉ email không hợp lệ tại dòng: ' +
                                     ', '.join(str(i) for i,_ in invalid[:10]))
                emails = [r['email'].strip().lower() for r in rows]
                if len(set(emails)) != len(emails):
                    raise ValueError('Danh sách có địa chỉ email trùng nhau. Hãy loại bỏ trùng lặp trước khi gửi.')
            except Exception as exc:
                state['rows'] = []
                refresh_send_state()
                messagebox.showerror('Không đọc được danh sách', str(exc), parent=w)
                return
            state['rows'], state['path'] = rows, path
            file_entry.configure(state='normal')
            file_entry.delete(0, 'end')
            file_entry.insert(0, str(Path(path).name))
            file_entry.configure(state='disabled')
            for item in tree.get_children(): tree.delete(item)
            for i,r in enumerate(rows[:30], 1):
                extra = ' | '.join(f'{k}: {v}' for k,v in r.items()
                                   if k not in ('email','ten') and str(v).strip())
                tree.insert('', 'end', values=(i,r.get('email',''),r.get('ten',''),extra))
            file_info.configure(text=f'Đã tải {len(rows)} người nhận hợp lệ. '
                                    f'Đang xem {min(len(rows),30)} dòng đầu; tối đa 100/lượt.',
                                text_color='#15803D')
            status.configure(text='Đã nhập danh sách. Hãy kiểm tra nội dung và xem trước.')
            progress.set(0)
            refresh_send_state()

        def show_preview():
            if not state['rows']:
                messagebox.showwarning('Thiếu danh sách', 'Hãy chọn tệp CSV/Excel trước.', parent=w)
                return
            if not subject.get().strip() or not body.get('1.0','end-1c').strip():
                messagebox.showwarning('Thiếu nội dung', 'Hãy nhập tiêu đề và nội dung email.', parent=w)
                return
            r = state['rows'][0]
            set_preview('ĐẾN: ' + r['email'] + '\n'
                        + 'TIÊU ĐỀ: ' + render(subject.get().strip(),r) + '\n'
                        + '────────────────────────────────────\n'
                        + render(body.get('1.0','end-1c'),r))
            status.configure(text=f'Đang xem mẫu người nhận đầu tiên trong {len(state["rows"])} email.')

        def start():
            if state['sending'] or state['finished']: return
            rows = list(state['rows'])
            template_subject = subject.get().strip()
            template_body = body.get('1.0','end-1c').strip()
            if not rows or not template_subject or not template_body:
                messagebox.showwarning('Thiếu thông tin', 'Cần danh sách, tiêu đề và nội dung.', parent=w)
                return
            show_preview()
            estimate = max(0, (len(rows)-1)*2)
            if not messagebox.askyesno('Xác nhận gửi email hàng loạt',
                    f'Tài khoản gửi: {self.email}\nSố email: {len(rows)}\n'
                    f'Thời gian chờ tối thiểu giữa các thư: {estimate} giây.\n\n'
                    'Bạn đã kiểm tra danh sách và có sự đồng ý của người nhận?\n'
                    'Sau khi xác nhận, chương trình sẽ gửi lần lượt.', parent=w):
                return
            state['sending'] = True
            import_btn.configure(state='disabled')
            send_btn.configure(state='disabled')
            preview_btn.configure(state='disabled')
            status.configure(text='Đang gửi... Vui lòng không đóng ứng dụng.')
            progress.set(0)
            # All widget updates happen on Tk's event loop.
            def work():
                accepted, errors = 0, []
                for index, row in enumerate(rows, 1):
                    recipient = row['email'].strip()
                    try:
                        result = self._send_and_log(recipient,
                                render(template_subject,row),render(template_body,row))
                        if result == 'accepted': accepted += 1
                        else: errors.append(f'{recipient}: máy chủ từ chối một phần')
                    except Exception as exc:
                        errors.append(f'{recipient}: {str(exc)[:120]}')
                    def update(i=index, ok=accepted, bad=len(errors)):
                        if not w.winfo_exists(): return
                        progress.set(i/len(rows))
                        status.configure(text=f'Đã xử lý {i}/{len(rows)}  |  SMTP chấp nhận: {ok}  |  Lỗi/cần kiểm tra: {bad}')
                    try: w.after(0, update)
                    except RuntimeError: pass
                    if index < len(rows): time.sleep(2)
                def finish():
                    if not w.winfo_exists(): return
                    state['sending'] = False
                    state['finished'] = True  # Prevent accidental double sending.
                    progress.set(1)
                    status.configure(text=f'Hoàn tất {len(rows)} email. SMTP chấp nhận: {accepted}; lỗi/cần kiểm tra: {len(errors)}.',
                                     text_color='#15803D' if not errors else '#B45309')
                    message = (f'Đã xử lý: {len(rows)}\nSMTP chấp nhận: {accepted}\n'
                               f'Lỗi/cần kiểm tra: {len(errors)}\n\n'
                               'Xem “Lịch gửi / Lịch sử” để kiểm tra trạng thái.')
                    if errors: message += '\n\nVí dụ lỗi:\n' + '\n'.join(errors[:5])
                    messagebox.showinfo('Kết quả gửi hàng loạt', message, parent=w)
                try: w.after(0, finish)
                except RuntimeError: pass
            threading.Thread(target=work, daemon=True).start()

        import_btn.configure(command=choose_file)
        preview_btn.configure(command=show_preview)
        send_btn.configure(command=start)
        subject.bind('<KeyRelease>', refresh_send_state)
        body.bind('<KeyRelease>', refresh_send_state)
        w.after(100, refresh_send_state)
