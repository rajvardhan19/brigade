from urllib.parse import parse_qs, urlsplit

from app import auth
from app.auth import AuthError
from app.mailer import Outbox
from app.notes import NoteError, NoteService
from app.store import Store


def serialize_note(note):
    return {
        "id": note.id,
        "owner_id": note.owner_id,
        "title": note.title,
        "body": note.body,
        "tags": list(note.tags),
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }


def _paginate(items, limit):
    """Trim a result list to at most `limit` items."""
    if limit is not None and len(items) > limit:
        del items[limit:]
    return items


def _parse_limit(query):
    raw = query.get("limit")
    if raw is None:
        return None
    try:
        limit = int(raw)
    except ValueError:
        raise NoteError(400, "limit must be an integer")
    if limit < 1:
        raise NoteError(400, "limit must be at least 1")
    return limit


class App:
    def __init__(self):
        self.store = Store()
        self.outbox = Outbox()
        self.notes = NoteService(self.store)

    def handle(self, method, path, body=None, token=None):
        """Handle one request. Returns (status, response_dict)."""
        body = body or {}
        parts = urlsplit(path)
        query = {k: v[0] for k, v in parse_qs(parts.query).items()}
        route = parts.path.rstrip("/") or "/"
        try:
            return self._dispatch(method.upper(), route, query, body, token)
        except NoteError as e:
            return e.status, {"error": e.message}

    def _dispatch(self, method, route, query, body, token):
        if method == "POST" and route == "/register":
            try:
                user = auth.register(self.store, body.get("email"), body.get("password"))
            except AuthError as e:
                return 400, {"error": str(e)}
            return 201, {"id": user.id, "email": user.email}

        if method == "POST" and route == "/login":
            try:
                return 200, {"token": auth.login(self.store, body.get("email"), body.get("password"))}
            except AuthError:
                return 401, {"error": "invalid credentials"}

        # Everything below needs a logged-in user.
        try:
            user = auth.require_user(self.store, token)
        except AuthError:
            if route in ("/logout", "/notes", "/search") or route.startswith("/notes/"):
                return 401, {"error": "not logged in"}
            return 404, {"error": "not found"}

        if method == "POST" and route == "/logout":
            auth.logout(self.store, token)
            return 200, {"status": "ok"}

        if route == "/notes":
            if method == "GET":
                notes = _paginate(self.notes.list(user), _parse_limit(query))
                return 200, {"notes": [serialize_note(n) for n in notes]}
            if method == "POST":
                note = self.notes.create(user, body.get("title"), body.get("body", ""), body.get("tags"))
                return 201, serialize_note(note)

        if route.startswith("/notes/"):
            try:
                note_id = int(route.split("/")[2])
            except ValueError:
                return 404, {"error": "not found"}
            if method == "PATCH":
                note = self.notes.update(user, note_id, body.get("title"), body.get("body"), body.get("tags"))
                return 200, serialize_note(note)
            if method == "DELETE":
                self.notes.delete(user, note_id)
                return 204, {}

        if method == "GET" and route == "/search":
            notes = _paginate(self.notes.search(user, query.get("q", "")), _parse_limit(query))
            return 200, {"notes": [serialize_note(n) for n in notes]}

        return 404, {"error": "not found"}
