import unittest

from app import clock
from tests.helpers import make_app, signup


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.ada = signup(self.app, "ada@example.com")
        self.bob = signup(self.app, "bob@example.com")
        status, self.note = self.app.handle("POST", "/notes", {"title": "draft"}, token=self.ada)
        self.nid = self.note["id"]

    def history(self, token=None):
        return self.app.handle("GET", f"/notes/{self.nid}/history", token=token or self.ada)

    def test_create_and_updates_recorded_oldest_first(self):
        t0 = self.note["created_at"]
        clock.advance(10)
        self.app.handle("PATCH", f"/notes/{self.nid}", {"title": "v2"}, token=self.ada)
        self.app.handle("POST", f"/notes/{self.nid}/share", {"email": "bob@example.com", "permission": "edit"},
                        token=self.ada)
        clock.advance(5)
        self.app.handle("PATCH", f"/notes/{self.nid}", {"body": "more"}, token=self.bob)
        status, body = self.history()
        self.assertEqual(status, 200)
        entries = body["history"]
        self.assertEqual([(e["action"], e["by"], e["title"]) for e in entries],
                         [("created", "ada@example.com", "draft"),
                          ("updated", "ada@example.com", "v2"),
                          ("updated", "bob@example.com", "v2")])
        self.assertEqual(entries[0]["at"], t0)
        self.assertAlmostEqual(entries[1]["at"], t0 + 10, delta=1)
        self.assertAlmostEqual(entries[2]["at"], t0 + 15, delta=1)
        self.assertEqual(self.history(token=self.bob), (200, body))

    def test_failed_updates_record_nothing(self):
        self.app.handle("PATCH", f"/notes/{self.nid}", {"title": "  "}, token=self.ada)
        self.app.handle("PATCH", f"/notes/{self.nid}", {"title": "x"}, token=self.bob)  # no access
        self.app.handle("POST", f"/notes/{self.nid}/share", {"email": "bob@example.com", "permission": "view"},
                        token=self.ada)
        self.app.handle("PATCH", f"/notes/{self.nid}", {"title": "x"}, token=self.bob)  # view only
        self.assertEqual([e["action"] for e in self.history()[1]["history"]], ["created"])

    def test_no_access_404(self):
        self.assertEqual(self.history(token=self.bob), (404, {"error": "note not found"}))

    def test_delete_removes_history(self):
        self.app.handle("DELETE", f"/notes/{self.nid}", token=self.ada)
        self.assertEqual(self.history()[0], 404)
        self.assertNotIn(self.nid, self.app.store.history)

    def test_returned_history_is_a_copy(self):
        self.history()[1]["history"][0]["title"] = "tampered"
        self.assertEqual(self.history()[1]["history"][0]["title"], "draft")


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.ada = signup(self.app, "ada@example.com")
        self.bob = signup(self.app, "bob@example.com")

    def export(self, title, body="", tags=None):
        _, note = self.app.handle("POST", "/notes", {"title": title, "body": body, "tags": tags or []}, token=self.ada)
        status, out = self.app.handle("GET", f"/notes/{note['id']}/export", token=self.ada)
        self.assertEqual(status, 200)
        return out["markdown"]

    def test_full(self):
        self.assertEqual(self.export("Groceries", "milk\neggs", ["home", "weekly"]),
                         "# Groceries\n\nmilk\neggs\n\nTags: home, weekly\n")

    def test_title_only(self):
        self.assertEqual(self.export("Empty"), "# Empty\n")

    def test_no_tags(self):
        self.assertEqual(self.export("T", "body"), "# T\n\nbody\n")

    def test_no_body(self):
        self.assertEqual(self.export("T", tags=["a"]), "# T\n\nTags: a\n")

    def test_shared_user_can_export_and_others_cannot(self):
        _, note = self.app.handle("POST", "/notes", {"title": "Shared"}, token=self.ada)
        path = f"/notes/{note['id']}/export"
        self.assertEqual(self.app.handle("GET", path, token=self.bob), (404, {"error": "note not found"}))
        self.app.handle("POST", f"/notes/{note['id']}/share", {"email": "bob@example.com", "permission": "view"},
                        token=self.ada)
        self.assertEqual(self.app.handle("GET", path, token=self.bob), (200, {"markdown": "# Shared\n"}))


if __name__ == "__main__":
    unittest.main()
