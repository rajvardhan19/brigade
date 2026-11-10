import unittest

from app import clock
from tests.helpers import make_app, signup


class SharingTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.owner = signup(self.app, "owner@example.com")
        self.bob = signup(self.app, "bob@example.com")
        self.eve = signup(self.app, "eve@example.com")
        self.note = self.create("Plan", "secret body", ["work"])

    def create(self, title, body="", tags=None, token=None):
        status, note = self.app.handle("POST", "/notes", {"title": title, "body": body, "tags": tags or []},
                                       token=token or self.owner)
        self.assertEqual(status, 201, note)
        return note

    def share(self, email, permission, token=None, note_id=None):
        return self.app.handle("POST", f"/notes/{note_id or self.note['id']}/share",
                               {"email": email, "permission": permission}, token=token or self.owner)

    def test_share_and_get(self):
        self.assertEqual(self.share("BOB@Example.com", "view"), (200, {"status": "ok"}))
        status, body = self.app.handle("GET", f"/notes/{self.note['id']}", token=self.bob)
        self.assertEqual(status, 200)
        self.assertEqual(body, self.note)
        status, body = self.app.handle("GET", f"/notes/{self.note['id']}", token=self.owner)
        self.assertEqual((status, body), (200, self.note))

    def test_share_errors(self):
        self.assertEqual(self.share("nobody@example.com", "view"), (400, {"error": "unknown user"}))
        self.assertEqual(self.share("bob@example.com", "admin"), (400, {"error": "invalid permission"}))
        self.assertEqual(self.share("OWNER@example.com", "edit"), (400, {"error": "cannot share with yourself"}))

    def test_no_access_is_404_everywhere(self):
        nid = self.note["id"]
        for method, path, body in [
            ("GET", f"/notes/{nid}", None),
            ("PATCH", f"/notes/{nid}", {"title": "x"}),
            ("DELETE", f"/notes/{nid}", None),
            ("POST", f"/notes/{nid}/share", {"email": "bob@example.com", "permission": "view"}),
            ("POST", f"/notes/{nid}/unshare", {"email": "bob@example.com"}),
            ("GET", f"/notes/{nid}/history", None),
            ("GET", f"/notes/{nid}/export", None),
        ]:
            self.assertEqual(self.app.handle(method, path, body, token=self.eve),
                             (404, {"error": "note not found"}), (method, path))

    def test_viewer_cannot_patch(self):
        self.share("bob@example.com", "view")
        status, body = self.app.handle("PATCH", f"/notes/{self.note['id']}", {"title": "hacked"}, token=self.bob)
        self.assertEqual((status, body), (403, {"error": "forbidden"}))
        _, note = self.app.handle("GET", f"/notes/{self.note['id']}", token=self.owner)
        self.assertEqual(note["title"], "Plan")

    def test_only_owner_can_delete_share_unshare(self):
        nid = self.note["id"]
        for permission in ("view", "edit"):
            self.share("bob@example.com", permission)
            forbidden = (403, {"error": "forbidden"})
            self.assertEqual(self.app.handle("DELETE", f"/notes/{nid}", token=self.bob), forbidden)
            self.assertEqual(self.share("eve@example.com", "view", token=self.bob), forbidden)
            self.assertEqual(self.app.handle("POST", f"/notes/{nid}/unshare", {"email": "bob@example.com"},
                                             token=self.bob), forbidden)
        self.assertEqual(self.app.handle("GET", f"/notes/{nid}", token=self.owner)[0], 200)

    def test_resharing_replaces_permission(self):
        self.share("bob@example.com", "edit")
        self.share("bob@example.com", "view")
        status, _ = self.app.handle("PATCH", f"/notes/{self.note['id']}", {"title": "x"}, token=self.bob)
        self.assertEqual(status, 403)
        _, body = self.app.handle("GET", "/notes/shared", token=self.bob)
        self.assertEqual([n["permission"] for n in body["notes"]], ["view"])

    def test_unshare_removes_access(self):
        self.share("bob@example.com", "edit")
        self.assertEqual(self.app.handle("POST", f"/notes/{self.note['id']}/unshare",
                                         {"email": "Bob@example.com"}, token=self.owner), (200, {"status": "ok"}))
        self.assertEqual(self.app.handle("GET", f"/notes/{self.note['id']}", token=self.bob)[0], 404)
        _, body = self.app.handle("GET", "/notes/shared", token=self.bob)
        self.assertEqual(body["notes"], [])

    def test_shared_list_newest_first_and_own_lists_unchanged(self):
        clock.advance(1)
        newer = self.create("Newer")
        self.share("bob@example.com", "view")
        self.share("bob@example.com", "edit", note_id=newer["id"])
        self.create("Bob's own", token=self.bob)
        _, body = self.app.handle("GET", "/notes/shared", token=self.bob)
        self.assertEqual([(n["title"], n["permission"]) for n in body["notes"]], [("Newer", "edit"), ("Plan", "view")])
        self.assertEqual(body["notes"][0]["owner_id"], newer["owner_id"])
        _, body = self.app.handle("GET", "/notes", token=self.bob)
        self.assertEqual([n["title"] for n in body["notes"]], ["Bob's own"])
        _, body = self.app.handle("GET", "/search?q=plan", token=self.bob)
        self.assertEqual(body["notes"], [])
        _, body = self.app.handle("GET", "/notes/shared", token=self.owner)
        self.assertEqual(body["notes"], [])

    def test_editor_changes_visible_to_owner_including_search(self):
        self.share("bob@example.com", "edit")
        # Warm the owner's search cache first.
        _, body = self.app.handle("GET", "/search?q=plan", token=self.owner)
        self.assertEqual(len(body["notes"]), 1)
        _, body = self.app.handle("GET", "/search?q=roadmap", token=self.owner)
        self.assertEqual(body["notes"], [])
        status, body = self.app.handle("PATCH", f"/notes/{self.note['id']}", {"title": "Roadmap"}, token=self.bob)
        self.assertEqual((status, body["title"]), (200, "Roadmap"))
        _, body = self.app.handle("GET", "/search?q=roadmap", token=self.owner)
        self.assertEqual([n["title"] for n in body["notes"]], ["Roadmap"])
        _, body = self.app.handle("GET", "/search?q=plan", token=self.owner)
        self.assertEqual(body["notes"], [])
        _, body = self.app.handle("GET", "/notes", token=self.owner)
        self.assertEqual(body["notes"][0]["title"], "Roadmap")
        _, body = self.app.handle("GET", f"/notes/{self.note['id']}", token=self.owner)
        self.assertEqual(body["title"], "Roadmap")

    def test_deleted_note_disappears_from_shared(self):
        self.share("bob@example.com", "view")
        self.assertEqual(self.app.handle("DELETE", f"/notes/{self.note['id']}", token=self.owner)[0], 204)
        _, body = self.app.handle("GET", "/notes/shared", token=self.bob)
        self.assertEqual(body["notes"], [])

    def test_search_limit_does_not_corrupt_cache(self):
        self.create("plan two")
        _, body = self.app.handle("GET", "/search?q=plan&limit=1", token=self.owner)
        self.assertEqual(len(body["notes"]), 1)
        _, body = self.app.handle("GET", "/search?q=plan", token=self.owner)
        self.assertEqual(len(body["notes"]), 2)


if __name__ == "__main__":
    unittest.main()
