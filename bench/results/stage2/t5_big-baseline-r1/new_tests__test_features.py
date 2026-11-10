import unittest

from app import clock
from tests.helpers import PASSWORD, make_app, signup


class Base(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.ada = signup(self.app, "ada@example.com")
        self.bob = signup(self.app, "bob@example.com")
        self.cy = signup(self.app, "cy@example.com")

    def req(self, method, path, body=None, token=None):
        return self.app.handle(method, path, body, token=token)

    def create(self, title, body="", tags=None, token=None):
        status, note = self.req("POST", "/notes", {"title": title, "body": body, "tags": tags or []}, token or self.ada)
        self.assertEqual(status, 201, note)
        return note

    def share(self, note_id, email, permission, token=None):
        return self.req("POST", f"/notes/{note_id}/share", {"email": email, "permission": permission}, token or self.ada)


class SharingTests(Base):
    def test_share_view_and_get(self):
        note = self.create("shared")
        self.assertEqual(self.share(note["id"], "BOB@example.com", "view"), (200, {"status": "ok"}))
        self.assertEqual(self.req("GET", f"/notes/{note['id']}", token=self.bob), (200, note))
        self.assertEqual(self.req("GET", f"/notes/{note['id']}", token=self.ada), (200, note))
        self.assertEqual(self.req("GET", f"/notes/{note['id']}", token=self.cy), (404, {"error": "note not found"}))

    def test_share_errors(self):
        note = self.create("n")
        self.assertEqual(self.share(note["id"], "nobody@example.com", "view"), (400, {"error": "unknown user"}))
        self.assertEqual(self.share(note["id"], "bob@example.com", "admin"), (400, {"error": "invalid permission"}))
        self.assertEqual(self.share(note["id"], "ADA@example.com", "view"),
                         (400, {"error": "cannot share with yourself"}))

    def test_view_cannot_edit_edit_can(self):
        note = self.create("n")
        self.share(note["id"], "bob@example.com", "view")
        self.assertEqual(self.req("PATCH", f"/notes/{note['id']}", {"title": "x"}, self.bob), (403, {"error": "forbidden"}))
        self.share(note["id"], "bob@example.com", "edit")  # replaces permission
        status, body = self.req("PATCH", f"/notes/{note['id']}", {"title": "x"}, self.bob)
        self.assertEqual((status, body["title"]), (200, "x"))
        self.assertEqual(self.req("GET", f"/notes/{note['id']}", token=self.ada)[1]["title"], "x")

    def test_only_owner_can_delete_share_unshare(self):
        note = self.create("n")
        self.share(note["id"], "bob@example.com", "edit")
        forbidden = (403, {"error": "forbidden"})
        self.assertEqual(self.req("DELETE", f"/notes/{note['id']}", token=self.bob), forbidden)
        self.assertEqual(self.share(note["id"], "cy@example.com", "view", self.bob), forbidden)
        self.assertEqual(self.req("POST", f"/notes/{note['id']}/unshare", {"email": "bob@example.com"}, self.bob), forbidden)
        # No access at all -> 404 everywhere.
        missing = (404, {"error": "note not found"})
        self.assertEqual(self.req("DELETE", f"/notes/{note['id']}", token=self.cy), missing)
        self.assertEqual(self.share(note["id"], "cy@example.com", "view", self.cy), missing)
        self.assertEqual(self.req("PATCH", f"/notes/{note['id']}", {"title": "x"}, self.cy), missing)
        self.assertEqual(self.req("GET", f"/notes/{note['id']}/history", token=self.cy), missing)
        self.assertEqual(self.req("GET", f"/notes/{note['id']}/export", token=self.cy), missing)

    def test_unshare_removes_access(self):
        note = self.create("n")
        self.share(note["id"], "bob@example.com", "edit")
        self.assertEqual(self.req("POST", f"/notes/{note['id']}/unshare", {"email": "Bob@example.com"}, self.ada),
                         (200, {"status": "ok"}))
        self.assertEqual(self.req("GET", f"/notes/{note['id']}", token=self.bob)[0], 404)
        self.assertEqual(self.req("GET", "/notes/shared", token=self.bob), (200, {"notes": []}))

    def test_shared_list_newest_first_with_permission(self):
        a = self.create("a")
        clock.advance(1)
        b = self.create("b")
        clock.advance(1)
        c = self.create("c", token=self.cy)
        self.share(a["id"], "bob@example.com", "edit")
        self.share(b["id"], "bob@example.com", "view")
        self.req("POST", f"/notes/{c['id']}/share", {"email": "bob@example.com", "permission": "view"}, self.cy)
        self.create("bob's own", token=self.bob)
        status, body = self.req("GET", "/notes/shared", token=self.bob)
        self.assertEqual(status, 200)
        self.assertEqual([(n["title"], n["permission"]) for n in body["notes"]],
                         [("c", "view"), ("b", "view"), ("a", "edit")])
        # Own lists stay own-only.
        self.assertEqual([n["title"] for n in self.req("GET", "/notes", token=self.bob)[1]["notes"]], ["bob's own"])
        self.assertEqual(self.req("GET", "/search?q=a", token=self.bob)[1]["notes"], [])

    def test_editor_changes_visible_in_owner_search(self):
        note = self.create("apple")
        self.share(note["id"], "bob@example.com", "edit")
        self.assertEqual(len(self.req("GET", "/search?q=apple", token=self.ada)[1]["notes"]), 1)
        self.assertEqual(len(self.req("GET", "/search?q=pear", token=self.ada)[1]["notes"]), 0)
        self.req("PATCH", f"/notes/{note['id']}", {"title": "pear"}, self.bob)
        self.assertEqual(self.req("GET", "/search?q=apple", token=self.ada)[1]["notes"], [])
        self.assertEqual([n["title"] for n in self.req("GET", "/search?q=pear", token=self.ada)[1]["notes"]], ["pear"])
        self.assertEqual(self.req("GET", "/notes", token=self.ada)[1]["notes"][0]["title"], "pear")

    def test_search_limit_does_not_corrupt_cache(self):
        for i in range(3):
            self.create(f"apple {i}")
        self.assertEqual(len(self.req("GET", "/search?q=apple&limit=1", token=self.ada)[1]["notes"]), 1)
        self.assertEqual(len(self.req("GET", "/search?q=apple", token=self.ada)[1]["notes"]), 3)

    def test_delete_removes_sharing(self):
        note = self.create("n")
        self.share(note["id"], "bob@example.com", "view")
        self.req("DELETE", f"/notes/{note['id']}", token=self.ada)
        self.assertEqual(self.req("GET", "/notes/shared", token=self.bob)[1]["notes"], [])


class HistoryTests(Base):
    def test_history_records_creates_and_updates(self):
        t0 = clock.now()
        note = self.create("v1")
        self.share(note["id"], "bob@example.com", "edit")
        clock.advance(10)
        self.req("PATCH", f"/notes/{note['id']}", {"title": "v2"}, self.bob)
        clock.advance(10)
        self.req("PATCH", f"/notes/{note['id']}", {"body": "text"}, self.ada)
        status, body = self.req("GET", f"/notes/{note['id']}/history", token=self.bob)
        self.assertEqual(status, 200)
        h = body["history"]
        self.assertEqual([(e["action"], e["by"], e["title"]) for e in h],
                         [("created", "ada@example.com", "v1"),
                          ("updated", "bob@example.com", "v2"),
                          ("updated", "ada@example.com", "v2")])
        self.assertAlmostEqual(h[1]["at"] - h[0]["at"], 10, places=1)
        self.assertGreaterEqual(h[0]["at"], t0)

    def test_failed_updates_record_nothing(self):
        note = self.create("v1")
        self.share(note["id"], "bob@example.com", "view")
        self.req("PATCH", f"/notes/{note['id']}", {"title": "  "}, self.ada)
        self.req("PATCH", f"/notes/{note['id']}", {"title": "x"}, self.bob)
        self.req("PATCH", f"/notes/{note['id']}", {"title": "x"}, self.cy)
        self.assertEqual(len(self.req("GET", f"/notes/{note['id']}/history", token=self.ada)[1]["history"]), 1)

    def test_failed_title_update_leaves_note_unchanged(self):
        note = self.create("v1", body="old")
        self.req("PATCH", f"/notes/{note['id']}", {"title": " ", "body": "new"}, self.ada)
        self.assertEqual(self.req("GET", f"/notes/{note['id']}", token=self.ada)[1]["body"], "old")

    def test_delete_deletes_history(self):
        note = self.create("v1")
        self.req("DELETE", f"/notes/{note['id']}", token=self.ada)
        self.assertEqual(self.req("GET", f"/notes/{note['id']}/history", token=self.ada)[0], 404)
        self.assertNotIn(note["id"], self.app.store.history)


class ExportTests(Base):
    def test_full_export(self):
        note = self.create("Groceries", body="milk\neggs", tags=["home", "weekly"])
        self.share(note["id"], "bob@example.com", "view")
        expected = (200, {"markdown": "# Groceries\n\nmilk\neggs\n\nTags: home, weekly\n"})
        self.assertEqual(self.req("GET", f"/notes/{note['id']}/export", token=self.ada), expected)
        self.assertEqual(self.req("GET", f"/notes/{note['id']}/export", token=self.bob), expected)

    def test_empty_export(self):
        note = self.create("Empty")
        self.assertEqual(self.req("GET", f"/notes/{note['id']}/export", token=self.ada)[1]["markdown"], "# Empty\n")

    def test_tags_only_and_body_only(self):
        a = self.create("A", tags=["x"])
        b = self.create("B", body="hi")
        self.assertEqual(self.req("GET", f"/notes/{a['id']}/export", token=self.ada)[1]["markdown"], "# A\n\nTags: x\n")
        self.assertEqual(self.req("GET", f"/notes/{b['id']}/export", token=self.ada)[1]["markdown"], "# B\n\nhi\n")


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        signup(self.app, "ada@example.com")

    def login(self, email="ada@example.com", password=PASSWORD):
        return self.app.handle("POST", "/login", {"email": email, "password": password})

    def fail(self, n, email="ada@example.com"):
        for _ in range(n):
            self.assertEqual(self.login(email, "wrong-pass-1")[0], 401)

    def test_lockout_after_five_failures(self):
        self.fail(5)
        self.assertEqual(self.login(), (429, {"error": "too many attempts"}))
        self.assertEqual(self.login("ADA@example.com", "wrong-pass-1")[0], 429)

    def test_four_failures_ok(self):
        self.fail(4)
        self.assertEqual(self.login()[0], 200)

    def test_success_resets_count(self):
        self.fail(4)
        self.assertEqual(self.login()[0], 200)
        self.fail(4)
        self.assertEqual(self.login()[0], 200)

    def test_lockout_lasts_15_minutes_from_fifth_failure_and_is_not_extended(self):
        self.fail(5)
        clock.advance(14 * 60)
        self.assertEqual(self.login("ada@example.com", "wrong-pass-1")[0], 429)
        clock.advance(59)
        self.assertEqual(self.login()[0], 429)
        clock.advance(1)
        self.assertEqual(self.login()[0], 200)

    def test_count_restarts_after_lockout(self):
        self.fail(5)
        clock.advance(15 * 60)
        self.fail(4)  # would be 429 if the old count carried over
        self.assertEqual(self.login()[0], 200)
        self.fail(5)
        self.assertEqual(self.login()[0], 429)

    def test_case_insensitive_and_per_email(self):
        signup(self.app, "bob@example.com")
        for e in ["ADA@example.com", "ada@EXAMPLE.com", "Ada@example.com", "ada@example.com", "aDa@example.com"]:
            self.assertEqual(self.login(e, "wrong-pass-1")[0], 401)
        self.assertEqual(self.login()[0], 429)
        self.assertEqual(self.login("bob@example.com")[0], 200)

    def test_unknown_emails_limited_the_same(self):
        self.fail(5, "ghost@example.com")
        self.assertEqual(self.login("ghost@example.com", "whatever-1"), (429, {"error": "too many attempts"}))


if __name__ == "__main__":
    unittest.main()
