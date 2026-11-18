# SmartMail – bản tích hợp bổ sung

## Cài đặt (Windows PowerShell)

```powershell
cd SmartMail-Nhom6-HoanThien
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python SmartMail.py
```

Đăng nhập Gmail bằng App Password hoặc Google OAuth2 đã được thiết lập hợp lệ. Nếu dùng OAuth2, đặt `client_secret.json` của chính bạn tại thư mục dự án theo README gốc; không đưa file này lên GitHub.

## Các chức năng mới
- Soạn thư → **Lên lịch**: chọn `YYYY-MM-DD HH:MM` theo giờ máy. **Ứng dụng phải đang mở và đăng nhập** khi đến giờ; lịch lưu SQLite trong `~/.smartmail/automation.sqlite3`. Không tự chạy khi tắt máy.
- **Gửi hàng loạt**: chọn CSV UTF-8 hoặc XLSX có cột `email`, thêm cột `ten` tùy ý; mẫu dùng `$ten`, `$email`. Xác nhận trước khi gửi, giới hạn 100 địa chỉ/lượt và nghỉ 2 giây giữa thư. Chỉ gửi cho người đã đồng ý nhận.
- **Bản nháp trên máy**: trong Soạn thư → Lưu nháp, xem và mở lại ở thanh trái. **Không đồng bộ với Gmail Drafts**.
- **Mẫu email**: lưu tiêu đề và nội dung dùng lại. Mẫu có thể chứa mã HTML. Khi chọn mẫu, chế độ HTML được bật và backend gửi MIME text/html; không có trình soạn WYSIWYG hoặc bộ lọc HTML. Chỉ dùng HTML do bạn tin cậy.
- **Lịch gửi / Lịch sử**: xem trạng thái gửi SMTP và lịch gửi, hủy lịch chưa thực hiện. Trạng thái `accepted` nghĩa là máy chủ SMTP chấp nhận, không đảm bảo đã vào Inbox.
- Đọc thư → Xóa / Khôi phục / Chưa đọc, qua IMAP. Gmail cần hỗ trợ lệnh `MOVE`.
- Reply / Reply All / Forward: có nút trên giao diện; Reply All cần xác nhận lại danh sách người nhận, vì dữ liệu header trong phiên bản gốc chưa đầy đủ.

## An toàn và giới hạn
- Không lưu mật khẩu hoặc OAuth token vào SQLite; lịch chỉ lưu người nhận, nội dung, đường dẫn file đính kèm. **File đính kèm phải còn tồn tại lúc gửi.**
- Nếu bị ngắt khi gửi, lịch chuyển `needs_review` để tránh gửi trùng; kiểm tra thư mục Đã gửi trước khi xử lý thủ công.
- Chỉ dùng trên máy cá nhân tin cậy: SQLite chứa nội dung email ở dạng rõ.
- Không kiểm thử gửi thư thật trong môi trường tạo bản ZIP. Kiểm tra với tài khoản thử trước khi sử dụng.

## Các file mới
- `backend/automation.py`: SQLite jobs, drafts, templates, history.
- `backend/bulk_mail.py`: đọc CSV/XLSX và thay biến mẫu.
- `ui/automation.py`: giao diện các chức năng mới và scheduler chạy khi mở ứng dụng.

## Các file sửa
- `SmartMail.py`, `backend/imap_client.py`, `backend/email_service.py`, `ui/login.py`, `ui/layout.py`, `ui/composer.py`, `ui/reader.py`, `requirements.txt`.

## Chạy kiểm thử

```powershell
python -m unittest discover -p "test*.py" -v
```
