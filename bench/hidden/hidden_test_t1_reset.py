"""Hidden grader for task t1_reset (password reset). Not visible to the sessions under test."""
import re
import unittest

from app import clock
from app.api import App

PW = "correct-horse-1"
NEW_PW = "brand-new-pass-2"


def _walk_strings(obj, seen=None):
    """Yield every string reachable from obj (dicts, lists, sets, tuples, object attributes)."""
    seen = seen if seen is not None else set()
    if id(obj) in seen:
        return
    seen.add(id(obj))
    if isinstance(obj, (str, bytes)):
        yield obj if isinstance(obj, str) else obj.decode("latin-1")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_strings(k, seen)
            yield from _walk_strings(v, seen)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for v in obj:
            yield from _walk_strings(v, seen)
    elif hasattr(obj, "__dict__") and not isinstance(obj, type):
        for v in vars(obj).values():
            yield from _walk_strings(v, seen)


class PasswordResetTests(unittest.TestCase):
    def setUp(self):
        clock.reset()
        self.app = App()
        self.app.handle("POST", "/register", {"email": "ada@example.com", "password": PW})

    def login(self, password):
        return self.app.handle("POST", "/login", {"email": "ada@example.com", "password": password})

    def request(self, email="ada@example.com"):
        return self.app.handle("POST", "/password-reset/request", {"email": email})

    def confirm(self, token, new_password=NEW_PW):
        return self.app.handle("POST", "/password-reset/confirm", {"token": token, "new_password": new_password})

    def last_token(self):
        body = self.app.outbox.sent[-1]["body"]
        m = re.search(r"token:\s*(\S+)", body)
        self.assertIsNotNone(m, f"no 'token: <token>' line in email body: {body!r}")
        return m.group(1)

    def test_known_and_unknown_email_get_identical_response(self):
        known = self.request("ada@example.com")
        unknown = self.request("nobody@example.com")
        self.assertEqual(known, (200, {"status": "ok"}))
        self.assertEqual(unknown, known)
        self.assertEqual(len(self.app.outbox.sent), 1)

    def test_email_sent_to_user(self):
        self.request()
        msg = self.app.outbox.sent[-1]
        self.assertEqual(msg["to"].lower(), "ada@example.com")
        self.assertEqual(msg["subject"], "Password reset")

    def test_full_reset_flow(self):
        self.request()
        self.assertEqual(self.confirm(self.last_token()), (200, {"status": "ok"}))
        self.assertEqual(self.login(NEW_PW)[0], 200)
        self.assertEqual(self.login(PW)[0], 401)

    def test_unknown_token(self):
        self.assertEqual(self.confirm("not-a-real-token"), (400, {"error": "invalid token"}))

    def test_token_single_use(self):
        self.request()
        token = self.last_token()
        self.assertEqual(self.confirm(token)[0], 200)
        self.assertEqual(self.confirm(token, "another-pass-3"), (400, {"error": "invalid token"}))

    def test_token_valid_before_30_minutes(self):
        self.request()
        token = self.last_token()
        clock.advance(29 * 60)
        self.assertEqual(self.confirm(token)[0], 200)

    def test_token_expires_after_30_minutes(self):
        self.request()
        token = self.last_token()
        clock.advance(31 * 60)
        self.assertEqual(self.confirm(token), (400, {"error": "invalid token"}))
        self.assertEqual(self.login(PW)[0], 200)

    def test_new_request_invalidates_earlier_token(self):
        self.request()
        first = self.last_token()
        self.request()
        second = self.last_token()
        self.assertNotEqual(first, second)
        self.assertEqual(self.confirm(first), (400, {"error": "invalid token"}))
        self.assertEqual(self.confirm(second)[0], 200)

    def test_weak_password_rejected_and_token_still_usable(self):
        self.request()
        token = self.last_token()
        self.assertEqual(self.confirm(token, "short"), (400, {"error": "weak password"}))
        self.assertEqual(self.confirm(token)[0], 200)

    def test_reset_logs_out_existing_sessions(self):
        session_a = self.login(PW)[1]["token"]
        session_b = self.login(PW)[1]["token"]
        self.request()
        self.confirm(self.last_token())
        self.assertEqual(self.app.handle("GET", "/notes", token=session_a)[0], 401)
        self.assertEqual(self.app.handle("GET", "/notes", token=session_b)[0], 401)

    def test_other_users_sessions_survive(self):
        self.app.handle("POST", "/register", {"email": "bob@example.com", "password": PW})
        bob = self.app.handle("POST", "/login", {"email": "bob@example.com", "password": PW})[1]["token"]
        self.request()
        self.confirm(self.last_token())
        self.assertEqual(self.app.handle("GET", "/notes", token=bob)[0], 200)

    def test_raw_token_not_stored(self):
        self.request()
        token = self.last_token()
        state = {k: v for k, v in vars(self.app).items() if k != "outbox"}
        leaks = [s for s in _walk_strings(state) if token in s]
        self.assertEqual(leaks, [], "raw reset token found in app state")

    def test_existing_behaviour_intact(self):
        token = self.login(PW)[1]["token"]
        self.assertEqual(self.app.handle("POST", "/notes", {"title": "x"}, token=token)[0], 201)
        self.assertEqual(self.app.handle("GET", "/notes")[0], 401)


if __name__ == "__main__":
    unittest.main()
