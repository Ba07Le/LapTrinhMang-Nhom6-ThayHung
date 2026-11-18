import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend import automation as store
from backend.bulk_mail import read_recipients,render
from backend.email_service import build_message

class AutomationTests(unittest.TestCase):
    def test_queue_and_history(self):
        with tempfile.TemporaryDirectory() as d,patch.object(store,'DB',Path(d)/'store.db'):
            j=store.queue('me@example.com','you@example.com','Hi','Body',[],'2000-01-01T00:00:00+00:00',True)
            self.assertEqual(store.pending('me@example.com')[0]['id'],j)
            self.assertTrue(store.claim(j))
            store.finish(j,'sent')
            self.assertEqual(store.jobs('me@example.com')[0]['status'],'sent')
            store.save_draft('me@example.com','to','sub','body',[])
            self.assertEqual(len(store.drafts('me@example.com')),1)
            store.save_template('me@example.com','hello','subject','<h1>Hi</h1>')
            self.assertEqual(len(store.templates('me@example.com')),1)
    def test_csv_merge(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'list.csv';path.write_text('email,ten\na@example.com,An\n',encoding='utf-8')
            rows=read_recipients(path)
            self.assertEqual(render('Chào $ten',rows[0]),'Chào An')
    def test_html_email(self):
        msg,_=build_message('me@example.com','you@example.com','Hello','Text',html_body='<b>Bold</b>')
        self.assertIn('<b>Bold</b>',msg.get_body(preferencelist=('html',)).get_content())

if __name__=='__main__':unittest.main()
