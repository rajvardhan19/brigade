import unittest

from app import clock
from tests.helpers import PASSWORD, make_app, signup

LOCKED = (429, {"error": "too many attempts"})


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        signup(self.app, "ada@example.com")

    def login(self, email="ada@example.com", password="wrong-pass-1"):
        return self.app.handle("POST", "/login", {"email": email, "password": password})

    def fail(self, n, email="ada@example.com"):
        for _ in range(n):
            self.assertEqual(self.login(email)[0], 401)

    def test_locked_after_five_failures_even_with_right_password(self):
        self.fail(5)
        self.assertEqual(self.login(password=PASSWORD), LOCKED)
        self.assertEqual(self.login(), LOCKED)

    def test_four_failures_then_success_resets(self):
        self.fail(4)
        self.assertEqual(self.login(password=PASSWORD)[0], 200)
        self.fail(4)
        self.assertEqual(self.login(password=PASSWORD)[0], 200)

    def test_case_insensitive(self):
        self.fail(3, "ADA@example.com")
        self.fail(2, "ada@EXAMPLE.com")
        self.assertEqual(self.login(password=PASSWORD), LOCKED)

    def test_lockout_lasts_15_minutes_from_fifth_failure_and_is_not_extended(self):
        self.fail(5)
        clock.advance(10 * 60)
        self.assertEqual(self.login(), LOCKED)  # does not extend the lockout
        clock.advance(5 * 60 - 1)
        self.assertEqual(self.login(password=PASSWORD), LOCKED)
        clock.advance(1)
        self.assertEqual(self.login(password=PASSWORD)[0], 200)

    def test_count_restarts_after_lockout(self):
        self.fail(5)
        clock.advance(15 * 60)
        self.fail(4)  # attempts during/after lockout start fresh
        self.assertEqual(self.login(password=PASSWORD)[0], 200)
        self.fail(5)
        self.assertEqual(self.login(password=PASSWORD), LOCKED)

    def test_other_emails_unaffected(self):
        signup(self.app, "bob@example.com")
        self.fail(5)
        self.assertEqual(self.login("bob@example.com", PASSWORD)[0], 200)

    def test_unknown_emails_limited_the_same_way(self):
        self.fail(5, "ghost@example.com")
        self.assertEqual(self.login("ghost@example.com"), LOCKED)
        clock.advance(15 * 60)
        self.assertEqual(self.login("ghost@example.com")[0], 401)


if __name__ == "__main__":
    unittest.main()
