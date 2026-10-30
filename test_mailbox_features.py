"""Offline unit tests for IMAP mailbox search and new-mail polling logic."""
import unittest
from backend.imap_client import ImapClient


class FakeSearchClient(ImapClient):
    def __init__(self):
        super().__init__()
        self.calls = []
        self.results = {
            ("TEXT", "project"): [10, 11, 12],
            ("FROM", "teacher@example.com"): [11, 12],
            ("SUBJECT", "deadline"): [12],
            ("UNSEEN",): [10, 12],
        }

    def _select(self, folder, readonly=True):
        self.calls.append(("select", folder))
        return 3

    def _search_text(self, key, value):
        self.calls.append((key, value))
        return self.results[(key, value)]

    def _search(self, *criteria):
        self.calls.append(tuple(criteria))
        return self.results[tuple(criteria)]

    def _fetch_headers(self, uids):
        self.calls.append(("fetch", uids))
        return [{"uid": uid, "from": "", "subject": "", "date": "", "seen": True}
                for uid in uids]


class MailboxSearchTests(unittest.TestCase):
    def test_search_by_sender_and_subject_combines_criteria(self):
        client = FakeSearchClient()
        result = client.search(sender="teacher@example.com", subject="deadline")
        self.assertEqual([row["uid"] for row in result], [12])

    def test_search_unread_only(self):
        client = FakeSearchClient()
        result = client.search(unseen_only=True)
        self.assertEqual([row["uid"] for row in result], [12, 10])

    def test_general_keyword_search(self):
        client = FakeSearchClient()
        result = client.search(keyword="project")
        self.assertEqual([row["uid"] for row in result], [12, 11, 10])


if __name__ == "__main__":
    unittest.main()
