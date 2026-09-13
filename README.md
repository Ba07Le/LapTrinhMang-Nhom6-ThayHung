> Đồ án cuối kỳ môn **Lập trình mạng** — Đề tài nhóm

# Hệ Thống Email Tự Động (SMTP/POP3/IMAP)

## 1. Thông tin nhóm

| STT | Họ tên            | MSSV       | Vai trò                              |
| --- | ----------------- | ---------- | ------------------------------------ |
| 1   | Lê Đức Bảo        | 2331540272 | Nhóm trưởng / Backend (SMTP gửi thư) |
| 2   | Lê Hồng Quân      | 2331540268 | Backend (IMAP/POP3 nhận thư)         |
| 3   | Nguyễn Quốc Thắng | 2331540195 | Frontend/GUI                         |

**GVHD:** ThS. Vũ Quốc Hưng
**Môn học:** Lập trình mạng
**Mức độ đề tài:** Intermediate

---

## 2. Lý do chọn đề tài

Email vẫn là một trong những hình thức giao tiếp phổ biến và quan trọng nhất trong môi trường làm việc, học tập lẫn hệ thống tự động (thông báo, xác thực tài khoản, marketing...). Đề tài giúp nhóm hiểu sâu cách các giao thức tầng ứng dụng (**SMTP** để gửi, **POP3/IMAP** để nhận) hoạt động thực tế trên nền TCP/IP, đồng thời rèn kỹ năng xây dựng ứng dụng mạng có giao diện, phục vụ trực tiếp Chương 6 của môn học.

---

## 3. Mục tiêu đề tài

Xây dựng một ứng dụng desktop cho phép người dùng:

- Soạn & gửi email (có đính kèm file) thông qua giao thức **SMTP**
- Xem, tải và quản lý hộp thư đến thông qua giao thức **IMAP** (hoặc POP3)
- Cung cấp giao diện trực quan, dễ sử dụng như một ứng dụng email thu nhỏ

---

## 4. Phạm vi thực hiện (Scope)

### Chức năng bắt buộc (MVP)

- Đăng nhập tài khoản email (Gmail/Outlook qua App Password)
- Soạn và gửi email (tiêu đề, nội dung, người nhận)
- Gửi email kèm file đính kèm
- Xem danh sách email trong hộp thư đến
- Đọc chi tiết nội dung 1 email
- Tải file đính kèm từ email về máy

### Chức năng mở rộng (Creative — điểm cộng)

- Lên lịch gửi email tự động (schedule send)
- Gửi hàng loạt (mail merge) từ danh sách Excel/CSV
- Tìm kiếm / lọc email theo từ khóa, người gửi
- Mã hóa nội dung email trước khi gửi (bảo mật)
- Thông báo (notification) khi có email mới (real-time polling)
- Soạn thảo email dạng HTML template

---

## 5. Công nghệ sử dụng

| Thành phần           | Công nghệ                          |
| -------------------- | ---------------------------------- |
| Ngôn ngữ             | Python 3.x                         |
| Giao thức gửi thư    | SMTP (`smtplib`)                   |
| Giao thức nhận thư   | IMAP (`imaplib`) / POP3 (`poplib`) |
| Xử lý nội dung email | `email` (thư viện chuẩn Python)    |
| Giao diện người dùng | Tkinter / PyQt5                    |
| Quản lý mã nguồn     | Git & GitHub                       |
| Công cụ phân tích    | Wireshark                          |

---

## 6. Kiến trúc tổng quan

```
┌─────────────────┐        SMTP (port 587/465)        ┌──────────────────┐
│                  │ ─────────────────────────────────▶ │                  │
│   Client (GUI)   │                                     │   Mail Server    │
│   Python App     │        IMAP (port 993)              │  (Gmail/Outlook) │
│                  │ ◀───────────────────────────────── │                  │
└─────────────────┘                                     └──────────────────┘
        │
        ▼
   Wireshark bắt gói tin để phân tích quá trình
   handshake, xác thực (AUTH), truyền dữ liệu
```

---

## 7. Kế hoạch thực hiện

## 8. Tài liệu tham khảo

- RFC 5321 — Simple Mail Transfer Protocol (SMTP)
- RFC 3501 — Internet Message Access Protocol (IMAP)
- RFC 1939 — Post Office Protocol version 3 (POP3)
- Python Docs: [smtplib](https://docs.python.org/3/library/smtplib.html), [imaplib](https://docs.python.org/3/library/imaplib.html)

---

## 9. Cấu trúc thư mục dự kiến
