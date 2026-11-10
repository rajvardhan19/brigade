import re
import unittest

from app import clock
from tests.helpers import PASSWORD, make_app, signup

EMAIL = "ada@example.com"
NEW_PASSWORD = "brand-new-pass-2"


class PasswordResetTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.session = signup(self.app, EMAIL)

    def tearDown(self):
        clock.reset()

    def request(self, email=EMAIL):
        return self.app.handle("POST", "/password-reset/request", {"email": email})

    def confirm(self, token, new_password=NEW_PASSWORD):
        return self.app.handle("POST", "/password-reset/confirm", {"token": token, "new_password": new_password})

    def latest_token(self):
        body = self.app.outbox.sent[-1]["body"]
        match = re.search(r"^token: (\S+)$", body, re.MULTILINE)
        self.assertIsNotNone(match, body)
        return match.group(1)

    def login(self, password):
        return self.app.handle("POST", "/login", {"email": EMAIL, "password": password})[0]

    # request

    def test_request_sends_email_to_existing_account(self):
        self.assertEqual(self.request(), (200, {"status": "ok"}))
        self.assertEqual(len(self.app.outbox.sent), 1)
        mail = self.app.outbox.sent[0]
        self.assertEqual(mail["to"], EMAIL)
        self.assertEqual(mail["subject"], "Password reset")
        self.assertTrue(self.latest_token())

    def test_request_matches_email_case_insensitively(self):
        self.assertEqual(self.request("ADA@Example.com"), (200, {"status": "ok"}))
        self.assertEqual(len(self.app.outbox.sent), 1)

    def test_request_for_unknown_email_looks_the_same_and_sends_nothing(self):
        self.assertEqual(self.request("nobody@example.com"), self.request(EMAIL))
        self.assertEqual([m["to"] for m in self.app.outbox.sent], [EMAIL])

    def test_request_with_missing_or_bad_email_still_ok(self):
        for body in ({}, {"email": None}, {"email": 42}, {"email": ""}):
            self.assertEqual(self.app.handle("POST", "/password-reset/request", body), (200, {"status": "ok"}))
        self.assertEqual(self.app.outbox.sent, [])

    def test_raw_token_not_stored(self):
        self.request()
        token = self.latest_token()
        store = self.app.store
        dump = repr(store.reset_tokens) + repr(vars(store))
        self.assertNotIn(token, dump)

    # confirm

    def test_confirm_sets_new_password(self):
        self.request()
        self.assertEqual(self.confirm(self.latest_token()), (200, {"status": "ok"}))
        self.assertEqual(self.login(NEW_PASSWORD), 200)
        self.assertEqual(self.login(PASSWORD), 401)

    def test_confirm_logs_out_all_sessions(self):
        other_session = self.app.handle("POST", "/login", {"email": EMAIL, "password": PASSWORD})[1]["token"]
        bystander = signup(self.app, "bob@example.com")
        self.request()
        self.confirm(self.latest_token())
        self.assertEqual(self.app.handle("GET", "/notes", token=self.session)[0], 401)
        self.assertEqual(self.app.handle("GET", "/notes", token=other_session)[0], 401)
        self.assertEqual(self.app.handle("GET", "/notes", token=bystander)[0], 200)

    def test_unknown_token_rejected(self):
        self.assertEqual(self.confirm("not-a-real-token"), (400, {"error": "invalid token"}))
        for body in ({}, {"token": None, "new_password": NEW_PASSWORD}, {"token": 5, "new_password": NEW_PASSWORD}):
            self.assertEqual(self.app.handle("POST", "/password-reset/confirm", body), (400, {"error": "invalid token"}))

    def test_token_works_only_once(self):
        self.request()
        token = self.latest_token()
        self.assertEqual(self.confirm(token)[0], 200)
        self.assertEqual(self.confirm(token, "another-pass-3"), (400, {"error": "invalid token"}))
        self.assertEqual(self.login(NEW_PASSWORD), 200)

    def test_token_expires_after_30_minutes(self):
        self.request()
        token = self.latest_token()
        clock.advance(30 * 60)
        self.assertEqual(self.confirm(token), (400, {"error": "invalid token"}))
        self.assertEqual(self.login(PASSWORD), 200)

    def test_token_valid_just_before_expiry(self):
        self.request()
        token = self.latest_token()
        clock.advance(30 * 60 - 1)
        self.assertEqual(self.confirm(token), (200, {"status": "ok"}))

    def test_new_request_invalidates_earlier_token(self):
        self.request()
        first = self.latest_token()
        self.request()
        second = self.latest_token()
        self.assertNotEqual(first, second)
        self.assertEqual(self.confirm(first), (400, {"error": "invalid token"}))
        self.assertEqual(self.confirm(second), (200, {"status": "ok"}))

    def test_request_does_not_affect_other_users_tokens(self):
        signup(self.app, "bob@example.com")
        self.request()
        ada_token = self.latest_token()
        self.request("bob@example.com")
        self.assertEqual(self.confirm(ada_token), (200, {"status": "ok"}))

    def test_weak_password_rejected_and_token_stays_usable(self):
        self.request()
        token = self.latest_token()
        self.assertEqual(self.confirm(token, "short"), (400, {"error": "weak password"}))
        self.assertEqual(self.confirm(token, "nodigitshere"), (400, {"error": "weak password"}))
        self.assertEqual(self.app.handle("GET", "/notes", token=self.session)[0], 200)
        self.assertEqual(self.login(PASSWORD), 200)
        self.assertEqual(self.confirm(token), (200, {"status": "ok"}))


if __name__ == "__main__":
    unittest.main()
