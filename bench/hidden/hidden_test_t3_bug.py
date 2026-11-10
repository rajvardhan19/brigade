"""Hidden grader for task t3_bug (search loses results after a limited search). Not visible to the sessions under test."""
import unittest

from app import clock
from app.api import App

PW = "correct-horse-1"


class SearchCacheBugTests(unittest.TestCase):
    def setUp(self):
        clock.reset()
        self.app = App()
        self.app.handle("POST", "/register", {"email": "ada@example.com", "password": PW})
        self.token = self.app.handle("POST", "/login", {"email": "ada@example.com", "password": PW})[1]["token"]
        for i in range(4):
            clock.advance(1)
            self.app.handle("POST", "/notes", {"title": f"apple {i}"}, token=self.token)

    def search(self, path):
        status, body = self.app.handle("GET", path, token=self.token)
        self.assertEqual(status, 200)
        return [n["title"] for n in body["notes"]]

    def test_limited_search_does_not_shrink_later_results(self):
        self.assertEqual(len(self.search("/search?q=apple&limit=1")), 1)
        self.assertEqual(len(self.search("/search?q=apple")), 4)

    def test_growing_limits(self):
        self.assertEqual(len(self.search("/search?q=apple&limit=2")), 2)
        self.assertEqual(len(self.search("/search?q=apple&limit=3")), 3)
        self.assertEqual(len(self.search("/search?q=apple&limit=10")), 4)

    def test_order_preserved_newest_first(self):
        self.search("/search?q=apple&limit=1")
        self.assertEqual(self.search("/search?q=apple"), ["apple 3", "apple 2", "apple 1", "apple 0"])

    def test_list_limit_unaffected(self):
        self.assertEqual(len(self.search("/notes?limit=1")), 1)
        self.assertEqual(len(self.search("/notes")), 4)

    def test_search_still_sees_edits(self):
        self.search("/search?q=apple&limit=1")
        note_id = self.app.handle("GET", "/notes", token=self.token)[1]["notes"][0]["id"]
        self.app.handle("PATCH", f"/notes/{note_id}", {"title": "banana"}, token=self.token)
        self.assertEqual(len(self.search("/search?q=apple")), 3)

    def test_search_per_user(self):
        self.app.handle("POST", "/register", {"email": "bob@example.com", "password": PW})
        bob = self.app.handle("POST", "/login", {"email": "bob@example.com", "password": PW})[1]["token"]
        self.assertEqual(self.app.handle("GET", "/search?q=apple", token=bob)[1]["notes"], [])


if __name__ == "__main__":
    unittest.main()
