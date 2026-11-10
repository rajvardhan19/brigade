"""Hidden grader for task t4_title (title length limit). Not visible to the sessions under test."""
import unittest

from app import clock
from app.api import App

PW = "correct-horse-1"


class TitleLimitTests(unittest.TestCase):
    def setUp(self):
        clock.reset()
        self.app = App()
        self.app.handle("POST", "/register", {"email": "ada@example.com", "password": PW})
        self.token = self.app.handle("POST", "/login", {"email": "ada@example.com", "password": PW})[1]["token"]

    def test_create_200_chars_ok(self):
        self.assertEqual(self.app.handle("POST", "/notes", {"title": "a" * 200}, token=self.token)[0], 201)

    def test_create_201_chars_rejected(self):
        self.assertEqual(self.app.handle("POST", "/notes", {"title": "a" * 201}, token=self.token),
                         (400, {"error": "title too long"}))
        self.assertEqual(self.app.handle("GET", "/notes", token=self.token)[1]["notes"], [])

    def test_update_201_chars_rejected_and_note_unchanged(self):
        note = self.app.handle("POST", "/notes", {"title": "short"}, token=self.token)[1]
        self.assertEqual(self.app.handle("PATCH", f"/notes/{note['id']}", {"title": "b" * 201}, token=self.token),
                         (400, {"error": "title too long"}))
        self.assertEqual(self.app.handle("GET", "/notes", token=self.token)[1]["notes"][0]["title"], "short")

    def test_update_200_chars_ok(self):
        note = self.app.handle("POST", "/notes", {"title": "short"}, token=self.token)[1]
        self.assertEqual(self.app.handle("PATCH", f"/notes/{note['id']}", {"title": "b" * 200}, token=self.token)[0], 200)

    def test_update_without_title_still_ok(self):
        note = self.app.handle("POST", "/notes", {"title": "short"}, token=self.token)[1]
        self.assertEqual(self.app.handle("PATCH", f"/notes/{note['id']}", {"body": "x"}, token=self.token)[0], 200)


if __name__ == "__main__":
    unittest.main()
