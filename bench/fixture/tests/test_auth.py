import unittest

from tests.helpers import PASSWORD, make_app, signup


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()

    def test_register_and_login(self):
        token = signup(self.app)
        self.assertTrue(token)

    def test_duplicate_email_rejected_case_insensitively(self):
        signup(self.app, "ada@example.com")
        status, body = self.app.handle("POST", "/register", {"email": "ADA@example.com", "password": PASSWORD})
        self.assertEqual(status, 400)

    def test_weak_password_rejected(self):
        status, body = self.app.handle("POST", "/register", {"email": "b@example.com", "password": "short"})
        self.assertEqual(status, 400)
        self.assertIn("weak password", body["error"])

    def test_wrong_password(self):
        signup(self.app)
        status, _ = self.app.handle("POST", "/login", {"email": "ada@example.com", "password": "nope-nope-1"})
        self.assertEqual(status, 401)

    def test_notes_require_login(self):
        status, _ = self.app.handle("GET", "/notes")
        self.assertEqual(status, 401)

    def test_logout_ends_session(self):
        token = signup(self.app)
        self.assertEqual(self.app.handle("POST", "/logout", token=token)[0], 200)
        self.assertEqual(self.app.handle("GET", "/notes", token=token)[0], 401)

    def test_password_not_stored_in_plain_text(self):
        signup(self.app)
        user = self.app.store.get_user_by_email("ada@example.com")
        self.assertNotIn(PASSWORD, user.password_hash)


if __name__ == "__main__":
    unittest.main()
