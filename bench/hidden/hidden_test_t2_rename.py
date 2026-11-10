"""Hidden grader for task t2_rename (owner_id -> author_id, plus tag filter). Not visible to the sessions under test."""
import os
import unittest

from app import clock
from app.api import App

PW = "correct-horse-1"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class RenameAndTagFilterTests(unittest.TestCase):
    def setUp(self):
        clock.reset()
        self.app = App()
        self.app.handle("POST", "/register", {"email": "ada@example.com", "password": PW})
        self.token = self.app.handle("POST", "/login", {"email": "ada@example.com", "password": PW})[1]["token"]

    def create(self, title, tags=(), token=None):
        status, note = self.app.handle("POST", "/notes", {"title": title, "tags": list(tags)}, token=token or self.token)
        self.assertEqual(status, 201, note)
        return note

    def test_api_uses_author_id(self):
        note = self.create("x")
        self.assertIn("author_id", note)
        self.assertNotIn("owner_id", note)
        listed = self.app.handle("GET", "/notes", token=self.token)[1]["notes"][0]
        self.assertIn("author_id", listed)
        self.assertNotIn("owner_id", listed)

    def test_model_field_renamed(self):
        note = self.create("x")
        obj = self.app.store.get_note(note["id"])
        self.assertTrue(hasattr(obj, "author_id"))
        self.assertFalse(hasattr(obj, "owner_id"))

    def test_no_owner_id_left_in_code(self):
        hits = []
        for folder in ("app", "tests"):
            for dirpath, _, files in os.walk(os.path.join(ROOT, folder)):
                for name in files:
                    if name.endswith(".py") and not name.startswith("hidden_test_"):
                        path = os.path.join(dirpath, name)
                        with open(path, encoding="utf-8") as f:
                            if "owner_id" in f.read():
                                hits.append(os.path.relpath(path, ROOT))
        self.assertEqual(hits, [])

    def test_ownership_still_enforced(self):
        note = self.create("mine")
        self.app.handle("POST", "/register", {"email": "bob@example.com", "password": PW})
        bob = self.app.handle("POST", "/login", {"email": "bob@example.com", "password": PW})[1]["token"]
        self.assertEqual(self.app.handle("PATCH", f"/notes/{note['id']}", {"title": "y"}, token=bob)[0], 404)

    def test_tag_filter(self):
        self.create("a", ["work"])
        clock.advance(1)
        self.create("b", ["home"])
        clock.advance(1)
        self.create("c", ["Work", "urgent"])
        status, body = self.app.handle("GET", "/notes?tag=work", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual([n["title"] for n in body["notes"]], ["c", "a"])

    def test_tag_filter_case_insensitive_query(self):
        self.create("a", ["work"])
        self.assertEqual(len(self.app.handle("GET", "/notes?tag=WORK", token=self.token)[1]["notes"]), 1)

    def test_tag_filter_with_limit(self):
        for i in range(3):
            clock.advance(1)
            self.create(f"n{i}", ["work"])
        self.create("other", ["home"])
        body = self.app.handle("GET", "/notes?tag=work&limit=2", token=self.token)[1]
        self.assertEqual([n["title"] for n in body["notes"]], ["n2", "n1"])

    def test_tag_filter_only_own_notes(self):
        self.create("mine", ["work"])
        self.app.handle("POST", "/register", {"email": "bob@example.com", "password": PW})
        bob = self.app.handle("POST", "/login", {"email": "bob@example.com", "password": PW})[1]["token"]
        self.create("bobs", ["work"], token=bob)
        self.assertEqual([n["title"] for n in self.app.handle("GET", "/notes?tag=work", token=self.token)[1]["notes"]], ["mine"])

    def test_no_tag_param_returns_all(self):
        self.create("a", ["work"])
        self.create("b")
        self.assertEqual(len(self.app.handle("GET", "/notes", token=self.token)[1]["notes"]), 2)


if __name__ == "__main__":
    unittest.main()
