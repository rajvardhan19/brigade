import unittest

from app import clock
from tests.helpers import make_app, signup


class SharingTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.ada = signup(self.app, "ada@example.com")
        self.bob = signup(self.app, "bob@example.com")
        self.cy = signup(self.app, "cy@example.com")

    def create(self, title, body="", tags=None, token=None):
        status, note = self.app.handle("POST", "/notes", {"title": title, "body": body, "tags": tags or []},
                                       token=token or self.ada)
        self.assertEqual(status, 201, note)
        return note

    def share(self, note_id, email, permission, token=None):
        return self.app.handle("POST", f"/notes/{note_id}/share", {"email": email, "permission": permission},
                               token=token or self.ada)

    def test_share_and_get(self):
        note = self.create("plan")
        self.assertEqual(self.share(note["id"], "BOB@example.com", "view"), (200, {"status": "ok"}))
        status, body = self.app.handle("GET", f"/notes/{note['id']}", token=self.bob)
        self.assertEqual(status, 200)
        self.assertEqual(body, note)
        self.assertEqual(self.app.handle("GET", f"/notes/{note['id']}", token=self.ada), (200, note))

    def test_share_errors(self):
        note = self.create("plan")
        self.assertEqual(self.share(note["id"], "nobody@example.com", "view"), (400, {"error": "unknown user"}))
        self.assertEqual(self.share(note["id"], "bob@example.com", "admin"), (400, {"error": "invalid permission"}))
        self.assertEqual(self.share(note["id"], "ADA@example.com", "view"),
                         (400, {"error": "cannot share with yourself"}))

    def test_no_access_is_404(self):
        note = self.create("plan")
        nid = note["id"]
        for method, path, body in [("GET", f"/notes/{nid}", None), ("PATCH", f"/notes/{nid}", {"title": "x"}),
                                   ("DELETE", f"/notes/{nid}", None), ("GET", f"/notes/{nid}/history", None),
                                   ("GET", f"/notes/{nid}/export", None),
                                   ("POST", f"/notes/{nid}/share", {"email": "cy@example.com", "permission": "view"}),
                                   ("POST", f"/notes/{nid}/unshare", {"email": "bob@example.com"})]:
            self.assertEqual(self.app.handle(method, path, body, token=self.bob),
                             (404, {"error": "note not found"}), (method, path))

    def test_viewer_cannot_edit_delete_or_share(self):
        note = self.create("plan")
        nid = note["id"]
        self.share(nid, "bob@example.com", "view")
        forbidden = (403, {"error": "forbidden"})
        self.assertEqual(self.app.handle("PATCH", f"/notes/{nid}", {"title": "x"}, token=self.bob), forbidden)
        self.assertEqual(self.app.handle("DELETE", f"/notes/{nid}", token=self.bob), forbidden)
        self.assertEqual(self.share(nid, "cy@example.com", "view", token=self.bob), forbidden)
        self.assertEqual(self.app.handle("POST", f"/notes/{nid}/unshare", {"email": "bob@example.com"},
                                         token=self.bob), forbidden)
        self.assertEqual(self.app.handle("GET", f"/notes/{nid}", token=self.ada)[1]["title"], "plan")

    def test_editor_can_patch_but_not_delete_or_share(self):
        note = self.create("plan")
        nid = note["id"]
        self.share(nid, "bob@example.com", "edit")
        status, body = self.app.handle("PATCH", f"/notes/{nid}", {"body": "details"}, token=self.bob)
        self.assertEqual(status, 200)
        self.assertEqual(body["body"], "details")
        self.assertEqual(body["owner_id"], note["owner_id"])
        self.assertEqual(self.app.handle("DELETE", f"/notes/{nid}", token=self.bob)[0], 403)
        self.assertEqual(self.share(nid, "cy@example.com", "view", token=self.bob)[0], 403)

    def test_resharing_replaces_permission(self):
        note = self.create("plan")
        nid = note["id"]
        self.share(nid, "bob@example.com", "edit")
        self.share(nid, "bob@example.com", "view")
        self.assertEqual(self.app.handle("PATCH", f"/notes/{nid}", {"title": "x"}, token=self.bob)[0], 403)
        shared = self.app.handle("GET", "/notes/shared", token=self.bob)[1]["notes"]
        self.assertEqual([(n["id"], n["permission"]) for n in shared], [(nid, "view")])

    def test_unshare_removes_access(self):
        note = self.create("plan")
        nid = note["id"]
        self.share(nid, "bob@example.com", "edit")
        self.assertEqual(self.app.handle("POST", f"/notes/{nid}/unshare", {"email": "Bob@example.com"},
                                         token=self.ada), (200, {"status": "ok"}))
        self.assertEqual(self.app.handle("GET", f"/notes/{nid}", token=self.bob)[0], 404)
        self.assertEqual(self.app.handle("GET", "/notes/shared", token=self.bob)[1]["notes"], [])

    def test_shared_list_newest_first_and_own_lists_unchanged(self):
        first = self.create("apple first")
        clock.advance(1)
        second = self.create("apple second", token=self.cy)
        self.create("apple private")
        self.share(first["id"], "bob@example.com", "view")
        self.share(second["id"], "bob@example.com", "edit", token=self.cy)
        status, body = self.app.handle("GET", "/notes/shared", token=self.bob)
        self.assertEqual(status, 200)
        self.assertEqual([(n["title"], n["permission"]) for n in body["notes"]],
                         [("apple second", "edit"), ("apple first", "view")])
        self.assertEqual(self.app.handle("GET", "/notes", token=self.bob)[1]["notes"], [])
        self.assertEqual(self.app.handle("GET", "/search?q=apple", token=self.bob)[1]["notes"], [])
        self.assertEqual(self.app.handle("GET", "/notes/shared", token=self.ada)[1]["notes"], [])

    def test_editor_changes_visible_to_owner_in_search(self):
        note = self.create("groceries")
        nid = note["id"]
        self.share(nid, "bob@example.com", "edit")
        # Prime the owner's search cache.
        self.assertEqual(len(self.app.handle("GET", "/search?q=groceries", token=self.ada)[1]["notes"]), 1)
        self.assertEqual(self.app.handle("GET", "/search?q=hardware", token=self.ada)[1]["notes"], [])
        self.app.handle("PATCH", f"/notes/{nid}", {"title": "hardware"}, token=self.bob)
        self.assertEqual(self.app.handle("GET", "/search?q=groceries", token=self.ada)[1]["notes"], [])
        hits = self.app.handle("GET", "/search?q=hardware", token=self.ada)[1]["notes"]
        self.assertEqual([n["id"] for n in hits], [nid])
        self.assertEqual(self.app.handle("GET", "/notes", token=self.ada)[1]["notes"][0]["title"], "hardware")
        self.assertEqual(self.app.handle("GET", f"/notes/{nid}", token=self.ada)[1]["title"], "hardware")

    def test_owner_delete_removes_share(self):
        note = self.create("plan")
        self.share(note["id"], "bob@example.com", "view")
        self.assertEqual(self.app.handle("DELETE", f"/notes/{note['id']}", token=self.ada)[0], 204)
        self.assertEqual(self.app.handle("GET", "/notes/shared", token=self.bob)[1]["notes"], [])
        self.assertEqual(self.app.handle("GET", f"/notes/{note['id']}", token=self.bob)[0], 404)

    def test_shared_requires_login(self):
        self.assertEqual(self.app.handle("GET", "/notes/shared")[0], 401)


class SearchLimitTests(unittest.TestCase):
    def test_limit_does_not_truncate_cached_results(self):
        app = make_app()
        token = signup(app)
        for i in range(3):
            app.handle("POST", "/notes", {"title": f"apple {i}"}, token=token)
        self.assertEqual(len(app.handle("GET", "/search?q=apple&limit=1", token=token)[1]["notes"]), 1)
        self.assertEqual(len(app.handle("GET", "/search?q=apple", token=token)[1]["notes"]), 3)


if __name__ == "__main__":
    unittest.main()
