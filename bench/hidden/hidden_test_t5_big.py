"""Hidden grader for task t5_big (sharing, history, export, login rate limiting). Not visible to the sessions under test."""
import unittest

from app import clock
from app.api import App

PW = "correct-horse-1"
ADA, BOB, CAT = "ada@example.com", "bob@example.com", "cat@example.com"


class Base(unittest.TestCase):
    def setUp(self):
        clock.reset()
        self.app = App()
        self.tok = {}
        for email in (ADA, BOB, CAT):
            self.app.handle("POST", "/register", {"email": email, "password": PW})
            self.tok[email] = self.app.handle("POST", "/login", {"email": email, "password": PW})[1]["token"]

    def req(self, who, method, path, body=None):
        return self.app.handle(method, path, body, token=self.tok[who])

    def note(self, who=ADA, title="apple pie", body="", tags=()):
        status, n = self.req(who, "POST", "/notes", {"title": title, "body": body, "tags": list(tags)})
        self.assertEqual(status, 201, n)
        return n["id"]

    def share(self, note_id, email, permission, who=ADA):
        return self.req(who, "POST", f"/notes/{note_id}/share", {"email": email, "permission": permission})


class SharingTests(Base):
    def test_view_share(self):
        nid = self.note()
        self.assertEqual(self.share(nid, BOB, "view"), (200, {"status": "ok"}))
        status, n = self.req(BOB, "GET", f"/notes/{nid}")
        self.assertEqual(status, 200)
        self.assertEqual(n["title"], "apple pie")
        self.assertEqual(self.req(BOB, "PATCH", f"/notes/{nid}", {"title": "x"}), (403, {"error": "forbidden"}))
        self.assertEqual(self.req(ADA, "GET", f"/notes/{nid}")[1]["title"], "apple pie")

    def test_owner_can_get_own_note(self):
        nid = self.note()
        self.assertEqual(self.req(ADA, "GET", f"/notes/{nid}")[0], 200)

    def test_edit_share(self):
        nid = self.note()
        self.share(nid, BOB, "edit")
        self.assertEqual(self.req(BOB, "PATCH", f"/notes/{nid}", {"body": "by bob"})[0], 200)
        self.assertEqual(self.req(ADA, "GET", "/notes")[1]["notes"][0]["body"], "by bob")

    def test_shared_list(self):
        nid1 = self.note(title="first")
        clock.advance(1)
        nid2 = self.note(title="second")
        self.share(nid1, BOB, "view")
        self.share(nid2, BOB, "edit")
        status, body = self.req(BOB, "GET", "/notes/shared")
        self.assertEqual(status, 200)
        self.assertEqual([(n["title"], n["permission"]) for n in body["notes"]], [("second", "edit"), ("first", "view")])
        self.assertEqual(self.req(BOB, "GET", "/notes")[1]["notes"], [])
        self.assertEqual(self.req(BOB, "GET", "/search?q=first")[1]["notes"], [])
        self.assertEqual(self.req(ADA, "GET", "/notes/shared")[1]["notes"], [])

    def test_no_access_is_404(self):
        nid = self.note()
        self.share(nid, BOB, "edit")
        for method, path, body in (("GET", f"/notes/{nid}", None), ("PATCH", f"/notes/{nid}", {"title": "x"}),
                                   ("DELETE", f"/notes/{nid}", None), ("GET", f"/notes/{nid}/history", None),
                                   ("GET", f"/notes/{nid}/export", None)):
            self.assertEqual(self.req(CAT, method, path, body), (404, {"error": "note not found"}), (method, path))
        self.assertEqual(self.share(nid, CAT, "view", who=CAT)[0], 404)

    def test_share_errors(self):
        nid = self.note()
        self.assertEqual(self.share(nid, "nobody@example.com", "view"), (400, {"error": "unknown user"}))
        self.assertEqual(self.share(nid, BOB, "admin"), (400, {"error": "invalid permission"}))
        self.assertEqual(self.share(nid, ADA, "view"), (400, {"error": "cannot share with yourself"}))
        self.assertEqual(self.req(BOB, "GET", f"/notes/{nid}")[0], 404)

    def test_share_email_case_insensitive(self):
        nid = self.note()
        self.assertEqual(self.share(nid, "BOB@Example.com", "view")[0], 200)
        self.assertEqual(self.req(BOB, "GET", f"/notes/{nid}")[0], 200)

    def test_reshare_replaces_permission(self):
        nid = self.note()
        self.share(nid, BOB, "view")
        self.share(nid, BOB, "edit")
        self.assertEqual(self.req(BOB, "PATCH", f"/notes/{nid}", {"title": "ok"})[0], 200)
        self.assertEqual(self.req(BOB, "GET", "/notes/shared")[1]["notes"][0]["permission"], "edit")
        self.share(nid, BOB, "view")
        self.assertEqual(self.req(BOB, "PATCH", f"/notes/{nid}", {"title": "no"})[0], 403)

    def test_unshare(self):
        nid = self.note()
        self.share(nid, BOB, "edit")
        self.assertEqual(self.req(ADA, "POST", f"/notes/{nid}/unshare", {"email": BOB}), (200, {"status": "ok"}))
        self.assertEqual(self.req(BOB, "GET", f"/notes/{nid}")[0], 404)
        self.assertEqual(self.req(BOB, "PATCH", f"/notes/{nid}", {"title": "x"})[0], 404)
        self.assertEqual(self.req(BOB, "GET", "/notes/shared")[1]["notes"], [])

    def test_only_owner_deletes_or_shares(self):
        nid = self.note()
        self.share(nid, BOB, "edit")
        self.assertEqual(self.req(BOB, "DELETE", f"/notes/{nid}"), (403, {"error": "forbidden"}))
        self.assertEqual(self.share(nid, CAT, "view", who=BOB), (403, {"error": "forbidden"}))
        self.assertEqual(self.req(BOB, "POST", f"/notes/{nid}/unshare", {"email": BOB}), (403, {"error": "forbidden"}))
        self.assertEqual(self.req(CAT, "GET", f"/notes/{nid}")[0], 404)
        self.assertEqual(self.req(ADA, "GET", f"/notes/{nid}")[0], 200)

    def test_owner_delete_removes_share(self):
        nid = self.note()
        self.share(nid, BOB, "view")
        self.assertEqual(self.req(ADA, "DELETE", f"/notes/{nid}")[0], 204)
        self.assertEqual(self.req(BOB, "GET", "/notes/shared")[1]["notes"], [])
        self.assertEqual(self.req(BOB, "GET", f"/notes/{nid}")[0], 404)

    def test_editor_change_visible_in_owner_search(self):
        nid = self.note(title="apple pie")
        self.share(nid, BOB, "edit")
        self.assertEqual(len(self.req(ADA, "GET", "/search?q=apple")[1]["notes"]), 1)
        self.req(BOB, "PATCH", f"/notes/{nid}", {"title": "banana bread"})
        self.assertEqual(self.req(ADA, "GET", "/search?q=apple")[1]["notes"], [])
        self.assertEqual(len(self.req(ADA, "GET", "/search?q=banana")[1]["notes"]), 1)


class HistoryTests(Base):
    def test_history_records_changes(self):
        nid = self.note(title="v1")
        clock.advance(5)
        self.req(ADA, "PATCH", f"/notes/{nid}", {"title": "v2"})
        clock.advance(5)
        self.req(ADA, "PATCH", f"/notes/{nid}", {"body": "text"})
        status, body = self.req(ADA, "GET", f"/notes/{nid}/history")
        self.assertEqual(status, 200)
        h = body["history"]
        self.assertEqual([(e["action"], e["by"], e["title"]) for e in h],
                         [("created", ADA, "v1"), ("updated", ADA, "v2"), ("updated", ADA, "v2")])
        self.assertLess(h[0]["at"], h[1]["at"])
        self.assertLess(h[1]["at"], h[2]["at"])

    def test_editor_changes_recorded_with_editor_email(self):
        nid = self.note(title="v1")
        self.share(nid, BOB, "edit")
        self.req(BOB, "PATCH", f"/notes/{nid}", {"title": "bob's"})
        h = self.req(ADA, "GET", f"/notes/{nid}/history")[1]["history"]
        self.assertEqual((h[-1]["action"], h[-1]["by"], h[-1]["title"]), ("updated", BOB, "bob's"))

    def test_failed_updates_not_recorded(self):
        nid = self.note(title="v1")
        self.share(nid, BOB, "view")
        self.req(ADA, "PATCH", f"/notes/{nid}", {"title": "   "})
        self.req(BOB, "PATCH", f"/notes/{nid}", {"title": "nope"})
        self.assertEqual(len(self.req(ADA, "GET", f"/notes/{nid}/history")[1]["history"]), 1)

    def test_viewer_sees_history(self):
        nid = self.note()
        self.share(nid, BOB, "view")
        self.assertEqual(self.req(BOB, "GET", f"/notes/{nid}/history")[0], 200)

    def test_delete_removes_history(self):
        nid = self.note()
        self.req(ADA, "DELETE", f"/notes/{nid}")
        self.assertEqual(self.req(ADA, "GET", f"/notes/{nid}/history")[0], 404)


class ExportTests(Base):
    def test_full_export(self):
        nid = self.note(title="Groceries", body="milk\neggs", tags=["home", "weekly"])
        self.assertEqual(self.req(ADA, "GET", f"/notes/{nid}/export"),
                         (200, {"markdown": "# Groceries\n\nmilk\neggs\n\nTags: home, weekly\n"}))

    def test_minimal_export(self):
        nid = self.note(title="Empty")
        self.assertEqual(self.req(ADA, "GET", f"/notes/{nid}/export")[1], {"markdown": "# Empty\n"})

    def test_tags_without_body(self):
        nid = self.note(title="T", tags=["x"])
        self.assertEqual(self.req(ADA, "GET", f"/notes/{nid}/export")[1], {"markdown": "# T\n\nTags: x\n"})

    def test_viewer_can_export(self):
        nid = self.note(title="Shared", body="b")
        self.share(nid, BOB, "view")
        self.assertEqual(self.req(BOB, "GET", f"/notes/{nid}/export"), (200, {"markdown": "# Shared\n\nb\n"}))


class RateLimitTests(Base):
    def login(self, email, password):
        return self.app.handle("POST", "/login", {"email": email, "password": password})

    def fail(self, email, n):
        for _ in range(n):
            self.assertEqual(self.login(email, "wrong-pass-9")[0], 401)

    def test_lockout_after_five_failures(self):
        self.fail(ADA, 5)
        self.assertEqual(self.login(ADA, PW), (429, {"error": "too many attempts"}))
        self.assertEqual(self.login("ADA@example.com", PW)[0], 429)

    def test_other_email_unaffected(self):
        self.fail(ADA, 5)
        self.assertEqual(self.login(BOB, PW)[0], 200)

    def test_lockout_expires(self):
        self.fail(ADA, 5)
        clock.advance(15 * 60 + 1)
        self.assertEqual(self.login(ADA, PW)[0], 200)

    def test_count_restarts_after_lockout(self):
        self.fail(ADA, 5)
        clock.advance(15 * 60 + 1)
        self.fail(ADA, 4)
        self.assertEqual(self.login(ADA, PW)[0], 200)

    def test_attempts_during_lockout_do_not_extend_it(self):
        self.fail(ADA, 5)
        clock.advance(10 * 60)
        self.assertEqual(self.login(ADA, PW)[0], 429)
        self.assertEqual(self.login(ADA, "wrong-pass-9")[0], 429)
        clock.advance(5 * 60 + 1)
        self.assertEqual(self.login(ADA, PW)[0], 200)

    def test_success_resets_count(self):
        self.fail(ADA, 4)
        self.assertEqual(self.login(ADA, PW)[0], 200)
        self.fail(ADA, 4)
        self.assertEqual(self.login(ADA, PW)[0], 200)

    def test_unknown_email_limited_the_same_way(self):
        self.fail("ghost@example.com", 5)
        self.assertEqual(self.login("ghost@example.com", PW), (429, {"error": "too many attempts"}))

    def test_sessions_still_work_during_lockout(self):
        self.fail(ADA, 5)
        self.assertEqual(self.req(ADA, "GET", "/notes")[0], 200)


if __name__ == "__main__":
    unittest.main()
