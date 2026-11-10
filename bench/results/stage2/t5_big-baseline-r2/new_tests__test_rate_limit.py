import unittest

from app import clock
from tests.helpers import PASSWORD, make_app, signup

LOCKED = (429, {"error": "too many attempts"})


class LoginRateLimitTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        signup(self.app, "ada@example.com")

    def login(self, email="ada@example.com", password=PASSWORD):
        return self.app.handle("POST", "/login", {"email": email, "password": password})

    def fail(self, n, email="ada@example.com"):
        for _ in range(n):
            self.assertEqual(self.login(email, "wrong-pass-1")[0], 401)

    def test_locked_after_five_failures_even_with_right_password(self):
        self.fail(5)
        self.assertEqual(self.login(), LOCKED)
        self.assertEqual(self.login("ADA@example.com", "wrong-pass-1"), LOCKED)

    def test_four_failures_not_locked(self):
        self.fail(4)
        self.assertEqual(self.login()[0], 200)

    def test_success_resets_count(self):
        self.fail(4)
        self.assertEqual(self.login()[0], 200)
        self.fail(4)
        self.assertEqual(self.login()[0], 200)

    def test_case_insensitive_counting(self):
        for email in ["ada@example.com", "ADA@example.com", "Ada@Example.com", "ada@EXAMPLE.com", "aDa@example.com"]:
            self.fail(1, email)
        self.assertEqual(self.login(), LOCKED)

    def test_lockout_lasts_15_minutes_from_fifth_failure_and_is_not_extended(self):
        self.fail(5)
        clock.advance(10 * 60)
        self.assertEqual(self.login(), LOCKED)
        self.assertEqual(self.login(password="wrong-pass-1"), LOCKED)
        clock.advance(5 * 60 - 1)
        self.assertEqual(self.login(), LOCKED)
        clock.advance(2)
        self.assertEqual(self.login()[0], 200)

    def test_count_restarts_after_lockout(self):
        self.fail(5)
        clock.advance(15 * 60 + 1)
        self.fail(4)  # attempts during the lockout didn't count; four fresh failures don't lock
        self.assertEqual(self.login()[0], 200)
        self.fail(5)
        self.assertEqual(self.login(), LOCKED)

    def test_other_emails_unaffected(self):
        signup(self.app, "bob@example.com")
        self.fail(5)
        self.assertEqual(self.login("bob@example.com")[0], 200)

    def test_unknown_emails_limited_the_same_way(self):
        self.fail(5, "ghost@example.com")
        self.assertEqual(self.login("ghost@example.com", "anything-1"), LOCKED)
        self.assertEqual(self.login()[0], 200)


if __name__ == "__main__":
    unittest.main()
