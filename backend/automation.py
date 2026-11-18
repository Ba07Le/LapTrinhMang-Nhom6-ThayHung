"""SQLite queue, drafts, templates and sending history. No credentials persisted."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB = Path.home() / '.smartmail' / 'automation.sqlite3'

@contextmanager
def connect():
    DB.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB,timeout=10)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    c.executescript('''CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY,account TEXT NOT NULL,kind TEXT NOT NULL,recipient TEXT NOT NULL,subject TEXT NOT NULL,body TEXT NOT NULL,attachments TEXT NOT NULL DEFAULT '[]',due TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',error TEXT NOT NULL DEFAULT '',created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY,account TEXT NOT NULL,recipient TEXT NOT NULL,subject TEXT NOT NULL,status TEXT NOT NULL,detail TEXT NOT NULL,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS drafts (id INTEGER PRIMARY KEY,account TEXT NOT NULL,recipient TEXT NOT NULL,subject TEXT NOT NULL,body TEXT NOT NULL,attachments TEXT NOT NULL,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS templates (id INTEGER PRIMARY KEY,account TEXT NOT NULL,name TEXT NOT NULL,subject TEXT NOT NULL,body TEXT NOT NULL,created TEXT NOT NULL);''')
    cols={row[1] for row in c.execute('PRAGMA table_info(jobs)')}
    if 'html_mode' not in cols:c.execute('ALTER TABLE jobs ADD COLUMN html_mode INTEGER NOT NULL DEFAULT 0')
    try:
        yield c
        c.commit()
    finally:
        c.close()

def now(): return datetime.now(timezone.utc).isoformat()
def rows(sql,args=()):
    with connect() as c:return [dict(r) for r in c.execute(sql,args).fetchall()]
def execute(sql,args=()):
    with connect() as c:
        cur=c.execute(sql,args)
        return cur.lastrowid

def queue(account,to,subject,body,attachments,due,html_mode=False):
    return execute('INSERT INTO jobs(account,kind,recipient,subject,body,attachments,due,created,html_mode) VALUES(?,?,?,?,?,?,?,?,?)',(account,'scheduled',to,subject,body,json.dumps(list(attachments)),due,now(),int(html_mode)))
def pending(account):return rows('SELECT * FROM jobs WHERE account=? AND status=? AND due<=? ORDER BY due',(account,'pending',now()))
def jobs(account):return rows('SELECT * FROM jobs WHERE account=? ORDER BY id DESC LIMIT 100',(account,))
def claim(job_id):
    with connect() as c:
        return c.execute("UPDATE jobs SET status='sending' WHERE id=? AND status='pending'",(job_id,)).rowcount==1
def finish(job_id,status,error=''):execute('UPDATE jobs SET status=?,error=? WHERE id=?',(status,error[:600],job_id))
def cancel(job_id,account):execute("UPDATE jobs SET status='cancelled' WHERE id=? AND account=? AND status='pending'",(job_id,account))
def recover_interrupted(account):
    execute("UPDATE jobs SET status='needs_review',error='Interrupted during sending; check Sent folder before retrying' WHERE account=? AND status='sending'",(account,))
def log(account,to,subject,status,detail=''):
    execute('INSERT INTO history(account,recipient,subject,status,detail,created) VALUES(?,?,?,?,?,?)',(account,to,subject,status,detail[:600],now()))
def history(account):return rows('SELECT * FROM history WHERE account=? ORDER BY id DESC LIMIT 150',(account,))
def save_draft(account,to,subject,body,attachments):
    return execute('INSERT INTO drafts(account,recipient,subject,body,attachments,created) VALUES(?,?,?,?,?,?)',(account,to,subject,body,json.dumps(list(attachments)),now()))
def drafts(account):return rows('SELECT * FROM drafts WHERE account=? ORDER BY id DESC',(account,))
def remove_draft(id,account):execute('DELETE FROM drafts WHERE id=? AND account=?',(id,account))
def save_template(account,name,subject,body):
    return execute('INSERT INTO templates(account,name,subject,body,created) VALUES(?,?,?,?,?)',(account,name,subject,body,now()))
def templates(account):return rows('SELECT * FROM templates WHERE account=? ORDER BY id DESC',(account,))


def remove_template(id,account):
    """Xóa một mẫu thuộc tài khoản hiện tại."""
    execute("DELETE FROM templates WHERE id=? AND account=?",(id,account))
