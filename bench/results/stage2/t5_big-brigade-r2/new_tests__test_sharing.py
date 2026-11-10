import unittest

from app import clock
from tests.helpers import make_app, signup


class SharingTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.ada = signup(self.app, "ada@example.com")
        self.bob = signup(self.app, "bob@example.com")
        self.cat = signup(self.app, "cat@example.com")

    def h(self, method, path, body=None, token=None):
        return self.app.handle(method, path, body, token)

    def create(self, title, token=None, body="", tags=None):
        status, note = self.h("POST", "/notes", {"title": title, "body": body, "tags": tags or []}, token or self.ada)
        self.assertEqual(status, 201, note)
        return note

    def share(self, note, email, permission, token=None):
        return self.h("POST", f"/notes/{note['id']}/share", {"email": email, "permission": permission}, token or self.ada)

    def test_owner_and_shared_user_can_get(self):
        note = self.create("hello")
        self.assertEqual(self.share(note, "bob@example.com", "view"), (200, {"status": "ok"}))
        status, got = self.h("GET", f"/notes/{note['id']}", token=self.ada)
        self.assertEqual((status, got), (200, note))
        status, got = self.h("GET", f"/notes/{note['id']}", token=self.bob)
        self.assertEqual((status, got), (200, note))
        self.assertEqual(self.h("GET", f"/notes/{note['id']}", token=self.cat), (404, {"error": "note not found"}))

    def test_share_errors(self):
        note = self.create("x")
        self.assertEqual(self.share(note, "nobody@example.com", "view"), (400, {"error": "unknown user"}))
        self.assertEqual(self.share(note, "bob@example.com", "admin"), (400, {"error": "invalid permission"}))
        self.assertEqual(self.share(note, "ADA@example.com", "view"), (400, {"error": "cannot share with yourself"}))

    def test_email_is_case_insensitive(self):
        note = self.create("x")
        self.assertEqual(self.share(note, "BOB@Example.com", "view")[0], 200)
        self.assertEqual(self.h("GET", f"/notes/{note['id']}", token=self.bob)[0], 200)

    def test_reshare_replaces_permission(self):
        note = self.create("x")
        self.share(note, "bob@example.com", "view")
        self.assertEqual(self.h("PATCH", f"/notes/{note['id']}", {"title": "y"}, self.bob), (403, {"error": "forbidden"}))
        self.share(note, "bob@example.com", "edit")
        self.assertEqual(self.h("PATCH", f"/notes/{note['id']}", {"title": "y"}, self.bob)[0], 200)
        self.share(note, "bob@example.com", "view")
        self.assertEqual(self.h("PATCH", f"/notes/{note['id']}", {"title": "z"}, self.bob)[0], 403)
        shared = self.h("GET", "/notes/shared", token=self.bob)[1]["notes"]
        self.assertEqual([(n["title"], n["permission"]) for n in shared], [("y", "view")])

    def test_unshare_removes_access(self):
        note = self.create("x")
        self.share(note, "bob@example.com", "edit")
        self.assertEqual(self.h("POST", f"/notes/{note['id']}/unshare", {"email": "Bob@example.com"}, self.ada),
                         (200, {"status": "ok"}))
        self.assertEqual(self.h("GET", f"/notes/{note['id']}", token=self.bob), (404, {"error": "note not found"}))
        self.assertEqual(self.h("GET", "/notes/shared", token=self.bob)[1]["notes"], [])

    def test_only_owner_can_delete_share_unshare(self):
        note = self.create("x")
        self.share(note, "bob@example.com", "edit")
        forbidden = (403, {"error": "forbidden"})
        self.assertEqual(self.h("DELETE", f"/notes/{note['id']}", token=self.bob), forbidden)
        self.assertEqual(self.share(note, "cat@example.com", "view", token=self.bob), forbidden)
        self.assertEqual(self.h("POST", f"/notes/{note['id']}/unshare", {"email": "bob@example.com"}, self.bob), forbidden)
        # Users with no access still get 404 for everything.
        missing = (404, {"error": "note not found"})
        self.assertEqual(self.h("DELETE", f"/notes/{note['id']}", token=self.cat), missing)
        self.assertEqual(self.h("PATCH", f"/notes/{note['id']}", {"title": "q"}, self.cat), missing)
        self.assertEqual(self.share(note, "cat@example.com", "view", token=self.cat), missing)
        self.assertEqual(self.h("POST", f"/notes/{note['id']}/unshare", {"email": "bob@example.com"}, self.cat), missing)
        self.assertEqual(self.h("GET", f"/notes/{note['id']}/history", token=self.cat), missing)
        self.assertEqual(self.h("GET", f"/notes/{note['id']}/export", token=self.cat), missing)

    def test_shared_list_newest_first_with_permission(self):
        a = self.create("older")
        clock.advance(1)
        b = self.create("newer", token=self.cat)
        clock.advance(1)
        self.create("not shared")
        self.share(a, "bob@example.com", "view")
        self.share(b, "bob@example.com", "edit", token=self.cat)
        status, body = self.h("GET", "/notes/shared", token=self.bob)
        self.assertEqual(status, 200)
        self.assertEqual([(n["title"], n["permission"]) for n in body["notes"]], [("newer", "edit"), ("older", "view")])
        # Bob's own lists don't include shared notes.
        self.assertEqual(self.h("GET", "/notes", token=self.bob)[1]["notes"], [])
        self.assertEqual(self.h("GET", "/search?q=e", token=self.bob)[1]["notes"], [])

    def test_editor_changes_visible_to_owner_everywhere(self):
        note = self.create("apple pie")
        self.share(note, "bob@example.com", "edit")
        # Warm the owner's search cache.
        self.assertEqual(len(self.h("GET", "/search?q=apple", token=self.ada)[1]["notes"]), 1)
        self.assertEqual(self.h("GET", "/search?q=banana", token=self.ada)[1]["notes"], [])
        status, _ = self.h("PATCH", f"/notes/{note['id']}", {"title": "banana bread"}, self.bob)
        self.assertEqual(status, 200)
        self.assertEqual(self.h("GET", "/search?q=apple", token=self.ada)[1]["notes"], [])
        self.assertEqual([n["title"] for n in self.h("GET", "/search?q=banana", token=self.ada)[1]["notes"]],
                         ["banana bread"])
        self.assertEqual(self.h("GET", "/notes", token=self.ada)[1]["notes"][0]["title"], "banana bread")
        self.assertEqual(self.h("GET", f"/notes/{note['id']}", token=self.ada)[1]["title"], "banana bread")

    def test_search_limit_does_not_corrupt_cache(self):
        for i in range(3):
            self.create(f"apple {i}")
        self.assertEqual(len(self.h("GET", "/search?q=apple&limit=1", token=self.ada)[1]["notes"]), 1)
        self.assertEqual(len(self.h("GET", "/search?q=apple", token=self.ada)[1]["notes"]), 3)

    def test_delete_removes_shares(self):
        note = self.create("x")
        self.share(note, "bob@example.com", "view")
        self.assertEqual(self.h("DELETE", f"/notes/{note['id']}", token=self.ada)[0], 204)
        self.assertEqual(self.h("GET", "/notes/shared", token=self.bob)[1]["notes"], [])


if __name__ == "__main__":
    unittest.main()
