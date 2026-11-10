import unittest

from app import clock
from tests.helpers import PASSWORD, make_app, signup

LOCKED = (429, {"error": "too many attempts"})


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        signup(self.app, "ada@example.com")
        signup(self.app, "bob@example.com")

    def login(self, email, password=PASSWORD):
        return self.app.handle("POST", "/login", {"email": email, "password": password})

    def fail(self, email, times):
        for _ in range(times):
            self.assertEqual(self.login(email, "wrong-password-1"), (401, {"error": "invalid credentials"}))

    def test_locks_after_five_failures_even_with_right_password(self):
        self.fail("ada@example.com", 5)
        self.assertEqual(self.login("ada@example.com"), LOCKED)
        self.assertEqual(self.login("ADA@example.com", "wrong"), LOCKED)

    def test_four_failures_do_not_lock(self):
        self.fail("ada@example.com", 4)
        self.assertEqual(self.login("ada@example.com")[0], 200)

    def test_case_insensitive(self):
        self.fail("Ada@Example.com", 3)
        self.fail("ada@example.com", 2)
        self.assertEqual(self.login("ADA@EXAMPLE.COM"), LOCKED)

    def test_lockout_lasts_15_minutes_from_fifth_failure_and_is_not_extended(self):
        self.fail("ada@example.com", 5)
        clock.advance(14 * 60)
        self.assertEqual(self.login("ada@example.com", "wrong"), LOCKED)
        self.assertEqual(self.login("ada@example.com"), LOCKED)
        clock.advance(59)
        self.assertEqual(self.login("ada@example.com"), LOCKED)
        clock.advance(2)
        self.assertEqual(self.login("ada@example.com")[0], 200)

    def test_count_restarts_after_lockout(self):
        self.fail("ada@example.com", 5)
        clock.advance(15 * 60 + 1)
        self.fail("ada@example.com", 4)  # would be 429 if lockout attempts or old failures counted
        self.assertEqual(self.login("ada@example.com")[0], 200)
        self.fail("ada@example.com", 4)
        self.fail("ada@example.com", 1)
        self.assertEqual(self.login("ada@example.com"), LOCKED)

    def test_success_resets_count(self):
        self.fail("ada@example.com", 4)
        self.assertEqual(self.login("ada@example.com")[0], 200)
        self.fail("ada@example.com", 4)
        self.assertEqual(self.login("ada@example.com")[0], 200)

    def test_other_emails_unaffected(self):
        self.fail("ada@example.com", 5)
        self.assertEqual(self.login("bob@example.com")[0], 200)

    def test_unknown_emails_limited_the_same_way(self):
        self.fail("ghost@example.com", 5)
        self.assertEqual(self.login("ghost@example.com"), LOCKED)
        self.assertEqual(self.login("ada@example.com")[0], 200)


if __name__ == "__main__":
    unittest.main()
