"""Read CSV/XLSX mail merge. One message per recipient, with explicit confirmation."""
import csv
from pathlib import Path
from .mail_utils import MailError

def read_recipients(filename):
    path=Path(filename)
    if path.suffix.lower()=='.csv':
        with path.open(encoding='utf-8-sig',newline='') as f: data=list(csv.DictReader(f))
    elif path.suffix.lower()=='.xlsx':
        try:from openpyxl import load_workbook
        except ImportError as exc:raise MailError('Cài openpyxl để đọc Excel: pip install openpyxl') from exc
        wb=load_workbook(path,read_only=True,data_only=True)
        try:
            it=wb.active.values
            headers=[str(x or '').strip() for x in next(it)]
            data=[dict(zip(headers,[str(x or '') for x in row])) for row in it]
        finally:wb.close()
    else:raise MailError('Chỉ hỗ trợ .csv hoặc .xlsx')
    if not data or 'email' not in data[0]:raise MailError('Danh sách cần có cột email (chữ thường)')
    if len(data)>100:raise MailError('Giới hạn 100 người nhận mỗi lần gửi')
    for i,row in enumerate(data,2):
        if not row.get('email','').strip():raise MailError(f'Dòng {i} thiếu email')
    return data

def render(template,row):
    from string import Template
    # Use $ten, $email syntax; safe_substitute avoids interpreting HTML braces.
    return Template(template).safe_substitute(row)
