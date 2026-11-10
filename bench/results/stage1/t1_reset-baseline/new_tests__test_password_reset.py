import re
import unittest

from tests.helpers import PASSWORD, make_app, signup

NEW_PASSWORD = "brand-new-pass-2"


class PasswordResetTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.token = signup(self.app, "ada@example.com")

    def request(self, email="ada@example.com"):
        return self.app.handle("POST", "/password-reset/request", {"email": email})

    def confirm(self, token, new_password=NEW_PASSWORD):
        return self.app.handle("POST", "/password-reset/confirm", {"token": token, "new_password": new_password})

    def issue(self, email="ada@example.com"):
        self.assertEqual(self.request(email), (200, {"status": "ok"}))
        body = self.app.outbox.sent[-1]["body"]
        match = re.search(r"^token: (\S+)$", body, re.MULTILINE)
        self.assertIsNotNone(match, body)
        return match.group(1)

    def login(self, password):
        return self.app.handle("POST", "/login", {"email": "ada@example.com", "password": password})[0]

    # request

    def test_request_sends_email(self):
        self.issue()
        self.assertEqual(len(self.app.outbox.sent), 1)
        msg = self.app.outbox.sent[0]
        self.assertEqual(msg["to"], "ada@example.com")
        self.assertEqual(msg["subject"], "Password reset")

    def test_request_email_is_case_insensitive(self):
        self.issue("ADA@Example.com")
        self.assertEqual(self.app.outbox.sent[0]["to"], "ada@example.com")

    def test_request_unknown_email_looks_identical(self):
        self.assertEqual(self.request("nobody@example.com"), (200, {"status": "ok"}))
        self.assertEqual(self.app.outbox.sent, [])

    def test_request_bad_input_still_ok(self):
        for body in ({}, {"email": None}, {"email": 42}, {"email": ""}):
            self.assertEqual(self.app.handle("POST", "/password-reset/request", body), (200, {"status": "ok"}))
        self.assertEqual(self.app.outbox.sent, [])

    def test_raw_token_not_stored(self):
        token = self.issue()
        stored = repr(self.app.store.__dict__)
        self.assertNotIn(token, stored)

    # confirm

    def test_confirm_changes_password(self):
        token = self.issue()
        self.assertEqual(self.confirm(token), (200, {"status": "ok"}))
        self.assertEqual(self.login(PASSWORD), 401)
        self.assertEqual(self.login(NEW_PASSWORD), 200)

    def test_confirm_logs_out_all_sessions(self):
        second = self.app.handle("POST", "/login", {"email": "ada@example.com", "password": PASSWORD})[1]["token"]
        other_user = signup(self.app, "bob@example.com")
        self.confirm(self.issue())
        self.assertEqual(self.app.handle("GET", "/notes", token=self.token)[0], 401)
        self.assertEqual(self.app.handle("GET", "/notes", token=second)[0], 401)
        self.assertEqual(self.app.handle("GET", "/notes", token=other_user)[0], 200)

    def test_token_single_use(self):
        token = self.issue()
        self.assertEqual(self.confirm(token)[0], 200)
        self.assertEqual(self.confirm(token, "another-pass-3"), (400, {"error": "invalid token"}))
        self.assertEqual(self.login(NEW_PASSWORD), 200)

    def test_unknown_token(self):
        self.issue()
        self.assertEqual(self.confirm("not-a-real-token"), (400, {"error": "invalid token"}))
        self.assertEqual(self.confirm(None), (400, {"error": "invalid token"}))
        self.assertEqual(self.app.handle("POST", "/password-reset/confirm", {}), (400, {"error": "invalid token"}))

    def test_token_expires_after_30_minutes(self):
        token = self.issue()
        self.app.clock.advance(30 * 60)
        self.assertEqual(self.confirm(token), (400, {"error": "invalid token"}))
        self.assertEqual(self.login(PASSWORD), 200)

    def test_token_valid_just_before_expiry(self):
        token = self.issue()
        self.app.clock.advance(30 * 60 - 1)
        self.assertEqual(self.confirm(token)[0], 200)

    def test_new_request_invalidates_earlier_token(self):
        first = self.issue()
        second = self.issue()
        self.assertNotEqual(first, second)
        self.assertEqual(self.confirm(first), (400, {"error": "invalid token"}))
        self.assertEqual(self.confirm(second)[0], 200)

    def test_tokens_are_per_user(self):
        signup(self.app, "bob@example.com")
        ada = self.issue("ada@example.com")
        bob = self.issue("bob@example.com")
        # Bob's request must not invalidate Ada's token.
        self.assertEqual(self.confirm(ada)[0], 200)
        self.assertEqual(self.confirm(bob)[0], 200)
        self.assertEqual(self.login(NEW_PASSWORD), 200)

    def test_weak_password_keeps_token_usable(self):
        token = self.issue()
        self.assertEqual(self.confirm(token, "short"), (400, {"error": "weak password"}))
        self.assertEqual(self.confirm(token, None), (400, {"error": "weak password"}))
        self.assertEqual(self.login(PASSWORD), 200)
        self.assertEqual(self.app.handle("GET", "/notes", token=self.token)[0], 200)
        self.assertEqual(self.confirm(token)[0], 200)

    def test_expired_token_with_weak_password_reports_invalid_token(self):
        token = self.issue()
        self.app.clock.advance(31 * 60)
        self.assertEqual(self.confirm(token, "short"), (400, {"error": "invalid token"}))


if __name__ == "__main__":
    unittest.main()
