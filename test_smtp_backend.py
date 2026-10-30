import os
import tempfile
import unittest
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

from backend.email_service import build_message, send_email
from backend.mail_utils import MailError


class EmailServiceTests(unittest.TestCase):
    def test_build_message_and_attachment(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
            f.write('hello attachment'.encode())
            path = f.name
        try:
            msg, recipients = build_message(
                'sender@gmail.com', 'one@gmail.com; two@gmail.com',
                'Xin chào', 'Nội dung tiếng Việt', [path], cc='three@gmail.com')
            self.assertEqual(recipients, ['one@gmail.com', 'two@gmail.com', 'three@gmail.com'])
            self.assertEqual(str(msg['Subject']), 'Xin chào')
            self.assertEqual(len(list(msg.iter_attachments())), 1)
            self.assertTrue(msg.get_body(preferencelist=('html',)))
        finally:
            os.unlink(path)

    def test_invalid_recipient_rejected(self):
        with self.assertRaises(MailError):
            build_message('sender@gmail.com', 'not-an-email', 'subject', 'body')

    @patch('backend.smtp_client.smtplib.SMTP')
    def test_smtp_oauth_flow(self, smtp_cls):
        smtp = MagicMock()
        smtp.__enter__.return_value = smtp
        smtp_cls.return_value = smtp
        smtp.send_message.return_value = {}
        result = send_email(
            sender='sender@gmail.com', to='receiver@gmail.com', subject='Test', body='Body',
            token_provider=lambda: 'test-access-token')
        smtp.starttls.assert_called_once()
        smtp.auth.assert_called_once()
        self.assertEqual(result['accepted'], ['receiver@gmail.com'])
        auth_mechanism = smtp.auth.call_args.args[0]
        auth_response = smtp.auth.call_args.args[1](None)
        challenge_response = smtp.auth.call_args.args[1](b'error')
        self.assertEqual(auth_mechanism, 'XOAUTH2')
        self.assertIn('auth=Bearer test-access-token', auth_response)
        self.assertEqual(challenge_response, '')

    @patch('backend.smtp_client.smtplib.SMTP')
    def test_smtp_app_password_flow(self, smtp_cls):
        smtp = MagicMock()
        smtp.__enter__.return_value = smtp
        smtp_cls.return_value = smtp
        smtp.send_message.return_value = {}
        send_email(sender='sender@gmail.com', to='receiver@gmail.com', subject='Test', body='Body',
                   password='app-password')
        smtp.login.assert_called_once_with('sender@gmail.com', 'app-password')


if __name__ == '__main__':
    unittest.main()
