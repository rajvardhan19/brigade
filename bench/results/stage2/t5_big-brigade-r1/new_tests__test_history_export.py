import unittest

from app import clock
from tests.helpers import make_app, signup


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.owner = signup(self.app, "owner@example.com")
        self.bob = signup(self.app, "Bob@Example.com")

    def test_history_records_creates_and_updates(self):
        t0 = clock.now()
        _, note = self.app.handle("POST", "/notes", {"title": "First"}, token=self.owner)
        nid = note["id"]
        self.app.handle("POST", f"/notes/{nid}/share", {"email": "bob@example.com", "permission": "edit"},
                        token=self.owner)
        clock.advance(10)
        t1 = clock.now()
        self.app.handle("PATCH", f"/notes/{nid}", {"title": "Second"}, token=self.bob)
        clock.advance(5)
        t2 = clock.now()
        self.app.handle("PATCH", f"/notes/{nid}", {"body": "only body"}, token=self.owner)
        status, body = self.app.handle("GET", f"/notes/{nid}/history", token=self.owner)
        self.assertEqual(status, 200)
        h = body["history"]
        self.assertEqual([(e["action"], e["by"], e["title"]) for e in h], [
            ("created", "owner@example.com", "First"),
            ("updated", "Bob@Example.com", "Second"),
            ("updated", "owner@example.com", "Second"),
        ])
        self.assertAlmostEqual(h[0]["at"], t0, delta=1)
        self.assertAlmostEqual(h[1]["at"], t1, delta=1)
        self.assertAlmostEqual(h[2]["at"], t2, delta=1)
        self.assertLess(h[0]["at"], h[1]["at"])
        self.assertEqual(set(h[0]), {"action", "by", "at", "title"})
        # Shared users can read it too.
        self.assertEqual(self.app.handle("GET", f"/notes/{nid}/history", token=self.bob), (200, body))

    def test_failed_updates_record_nothing(self):
        _, note = self.app.handle("POST", "/notes", {"title": "T"}, token=self.owner)
        nid = note["id"]
        self.app.handle("POST", f"/notes/{nid}/share", {"email": "bob@example.com", "permission": "view"},
                        token=self.owner)
        self.assertEqual(self.app.handle("PATCH", f"/notes/{nid}", {"title": "  "}, token=self.owner)[0], 400)
        self.assertEqual(self.app.handle("PATCH", f"/notes/{nid}", {"title": "X"}, token=self.bob)[0], 403)
        _, body = self.app.handle("GET", f"/notes/{nid}/history", token=self.owner)
        self.assertEqual([e["action"] for e in body["history"]], ["created"])
        _, body = self.app.handle("GET", f"/notes/{nid}", token=self.owner)
        self.assertEqual(body["title"], "T")

    def test_delete_removes_history(self):
        _, note = self.app.handle("POST", "/notes", {"title": "T"}, token=self.owner)
        nid = note["id"]
        self.app.handle("DELETE", f"/notes/{nid}", token=self.owner)
        self.assertEqual(self.app.handle("GET", f"/notes/{nid}/history", token=self.owner),
                         (404, {"error": "note not found"}))
        self.assertNotIn(nid, self.app.store.history)


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.owner = signup(self.app, "owner@example.com")
        self.bob = signup(self.app, "bob@example.com")

    def export(self, title, body="", tags=None, token=None):
        _, note = self.app.handle("POST", "/notes", {"title": title, "body": body, "tags": tags or []},
                                  token=self.owner)
        return self.app.handle("GET", f"/notes/{note['id']}/export", token=token or self.owner)

    def test_full_export(self):
        self.assertEqual(self.export("Groceries", "milk\neggs", ["home", "weekly"]),
                         (200, {"markdown": "# Groceries\n\nmilk\neggs\n\nTags: home, weekly\n"}))

    def test_empty_export(self):
        self.assertEqual(self.export("Empty"), (200, {"markdown": "# Empty\n"}))

    def test_omits_empty_parts(self):
        self.assertEqual(self.export("T", "b")[1]["markdown"], "# T\n\nb\n")
        self.assertEqual(self.export("T", tags=["x"])[1]["markdown"], "# T\n\nTags: x\n")

    def test_export_access(self):
        _, note = self.app.handle("POST", "/notes", {"title": "T"}, token=self.owner)
        path = f"/notes/{note['id']}/export"
        self.assertEqual(self.app.handle("GET", path, token=self.bob), (404, {"error": "note not found"}))
        self.app.handle("POST", f"/notes/{note['id']}/share", {"email": "bob@example.com", "permission": "view"},
                        token=self.owner)
        self.assertEqual(self.app.handle("GET", path, token=self.bob), (200, {"markdown": "# T\n"}))


if __name__ == "__main__":
    unittest.main()
