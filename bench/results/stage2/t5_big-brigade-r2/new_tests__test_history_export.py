import unittest

from app import clock
from tests.helpers import make_app, signup


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.ada = signup(self.app, "ada@example.com")
        self.bob = signup(self.app, "bob@example.com")

    def test_history_records_creates_and_updates(self):
        t0 = clock.now()
        _, note = self.app.handle("POST", "/notes", {"title": "v1"}, token=self.ada)
        t1 = clock.now()
        clock.advance(100)
        self.app.handle("POST", f"/notes/{note['id']}/share", {"email": "bob@example.com", "permission": "edit"},
                        token=self.ada)
        self.assertEqual(self.app.handle("PATCH", f"/notes/{note['id']}", {"body": "b"}, token=self.bob)[0], 200)
        # Failed updates record nothing.
        self.assertEqual(self.app.handle("PATCH", f"/notes/{note['id']}", {"title": " "}, token=self.bob)[0], 400)
        status, body = self.app.handle("GET", f"/notes/{note['id']}/history", token=self.ada)
        self.assertEqual(status, 200)
        history = body["history"]
        self.assertEqual([(e["action"], e["by"], e["title"]) for e in history],
                         [("created", "ada@example.com", "v1"), ("updated", "bob@example.com", "v1")])
        self.assertTrue(t0 <= history[0]["at"] <= t1)
        self.assertGreaterEqual(history[1]["at"], t0 + 100)
        self.assertEqual(set(history[0]), {"action", "by", "at", "title"})
        # Shared users can read it too.
        self.assertEqual(self.app.handle("GET", f"/notes/{note['id']}/history", token=self.bob)[1], body)

    def test_view_user_failed_patch_records_nothing(self):
        _, note = self.app.handle("POST", "/notes", {"title": "v1"}, token=self.ada)
        self.app.handle("POST", f"/notes/{note['id']}/share", {"email": "bob@example.com", "permission": "view"},
                        token=self.ada)
        self.assertEqual(self.app.handle("PATCH", f"/notes/{note['id']}", {"title": "v2"}, token=self.bob)[0], 403)
        history = self.app.handle("GET", f"/notes/{note['id']}/history", token=self.bob)[1]["history"]
        self.assertEqual([e["action"] for e in history], ["created"])

    def test_delete_removes_history(self):
        _, note = self.app.handle("POST", "/notes", {"title": "v1"}, token=self.ada)
        self.app.handle("DELETE", f"/notes/{note['id']}", token=self.ada)
        self.assertEqual(self.app.handle("GET", f"/notes/{note['id']}/history", token=self.ada)[0], 404)
        self.assertNotIn(note["id"], self.app.store.history)


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.ada = signup(self.app, "ada@example.com")
        self.bob = signup(self.app, "bob@example.com")

    def export(self, title, body="", tags=None, token=None):
        _, note = self.app.handle("POST", "/notes", {"title": title, "body": body, "tags": tags or []}, token=self.ada)
        return self.app.handle("GET", f"/notes/{note['id']}/export", token=token or self.ada)

    def test_full_note(self):
        self.assertEqual(self.export("Groceries", "milk\neggs", ["home", "weekly"]),
                         (200, {"markdown": "# Groceries\n\nmilk\neggs\n\nTags: home, weekly\n"}))

    def test_empty_note(self):
        self.assertEqual(self.export("Empty"), (200, {"markdown": "# Empty\n"}))

    def test_body_only_and_tags_only(self):
        self.assertEqual(self.export("A", "text")[1]["markdown"], "# A\n\ntext\n")
        self.assertEqual(self.export("B", tags=["x"])[1]["markdown"], "# B\n\nTags: x\n")

    def test_shared_user_can_export_others_cannot(self):
        _, note = self.app.handle("POST", "/notes", {"title": "T"}, token=self.ada)
        path = f"/notes/{note['id']}/export"
        self.assertEqual(self.app.handle("GET", path, token=self.bob), (404, {"error": "note not found"}))
        self.app.handle("POST", f"/notes/{note['id']}/share", {"email": "bob@example.com", "permission": "view"},
                        token=self.ada)
        self.assertEqual(self.app.handle("GET", path, token=self.bob), (200, {"markdown": "# T\n"}))


if __name__ == "__main__":
    unittest.main()
