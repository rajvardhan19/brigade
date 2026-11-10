import unittest

from app import clock
from tests.helpers import make_app, signup


class NotesTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.token = signup(self.app)

    def create(self, title, body="", tags=None, token=None):
        status, note = self.app.handle("POST", "/notes", {"title": title, "body": body, "tags": tags or []},
                                       token=token or self.token)
        self.assertEqual(status, 201, note)
        return note

    def test_create_and_list_newest_first(self):
        self.create("first")
        clock.advance(1)
        self.create("second")
        status, body = self.app.handle("GET", "/notes", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual([n["title"] for n in body["notes"]], ["second", "first"])

    def test_list_limit(self):
        for i in range(3):
            self.create(f"n{i}")
        status, body = self.app.handle("GET", "/notes?limit=2", token=self.token)
        self.assertEqual(len(body["notes"]), 2)

    def test_title_required(self):
        status, body = self.app.handle("POST", "/notes", {"title": "  "}, token=self.token)
        self.assertEqual(status, 400)

    def test_update(self):
        note = self.create("old", tags=["A"])
        status, body = self.app.handle("PATCH", f"/notes/{note['id']}", {"title": "new", "tags": ["B"]}, token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual((body["title"], body["tags"]), ("new", ["b"]))

    def test_delete(self):
        note = self.create("bye")
        self.assertEqual(self.app.handle("DELETE", f"/notes/{note['id']}", token=self.token)[0], 204)
        self.assertEqual(self.app.handle("GET", "/notes", token=self.token)[1]["notes"], [])

    def test_cannot_touch_other_users_notes(self):
        note = self.create("mine")
        other = signup(self.app, "bob@example.com")
        self.assertEqual(self.app.handle("PATCH", f"/notes/{note['id']}", {"title": "x"}, token=other)[0], 404)
        self.assertEqual(self.app.handle("DELETE", f"/notes/{note['id']}", token=other)[0], 404)
        self.assertEqual(self.app.handle("GET", "/notes", token=other)[1]["notes"], [])

    def test_search_title_body_and_tags(self):
        self.create("Apple pie")
        self.create("Shopping", body="buy apples")
        self.create("Misc", tags=["apple"])
        self.create("Unrelated")
        status, body = self.app.handle("GET", "/search?q=APPLE", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(len(body["notes"]), 3)

    def test_search_limit(self):
        for i in range(3):
            self.create(f"apple {i}")
        status, body = self.app.handle("GET", "/search?q=apple&limit=2", token=self.token)
        self.assertEqual(len(body["notes"]), 2)

    def test_search_sees_new_notes(self):
        self.create("apple one")
        self.assertEqual(len(self.app.handle("GET", "/search?q=apple", token=self.token)[1]["notes"]), 1)
        self.create("apple two")
        self.assertEqual(len(self.app.handle("GET", "/search?q=apple", token=self.token)[1]["notes"]), 2)

    def test_search_is_per_user(self):
        self.create("apple mine")
        other = signup(self.app, "bob@example.com")
        self.assertEqual(self.app.handle("GET", "/search?q=apple", token=other)[1]["notes"], [])


if __name__ == "__main__":
    unittest.main()
