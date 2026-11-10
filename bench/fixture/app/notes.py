from app import clock


class NoteError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def _clean_tags(tags):
    return [str(t).strip().lower() for t in (tags or []) if str(t).strip()]


class NoteService:
    def __init__(self, store):
        self.store = store
        self._search_cache = {}  # (owner_id, query) -> list of Note

    def _invalidate(self, owner_id):
        for key in [k for k in self._search_cache if k[0] == owner_id]:
            del self._search_cache[key]

    def _owned(self, user, note_id):
        note = self.store.get_note(note_id)
        if note is None or note.owner_id != user.id:
            raise NoteError(404, "note not found")
        return note

    def create(self, user, title, body="", tags=None):
        if not title or not str(title).strip():
            raise NoteError(400, "title required")
        note = self.store.add_note(user.id, str(title).strip(), body or "", _clean_tags(tags), clock.now())
        self._invalidate(user.id)
        return note

    def update(self, user, note_id, title=None, body=None, tags=None):
        note = self._owned(user, note_id)
        if title is not None:
            if not str(title).strip():
                raise NoteError(400, "title required")
            note.title = str(title).strip()
        if body is not None:
            note.body = body
        if tags is not None:
            note.tags = _clean_tags(tags)
        note.updated_at = clock.now()
        self._invalidate(user.id)
        return note

    def delete(self, user, note_id):
        self._owned(user, note_id)
        self.store.delete_note(note_id)
        self._invalidate(user.id)

    def list(self, user):
        """The user's notes, newest first."""
        return sorted(self.store.notes_for_owner(user.id), key=lambda n: (n.created_at, n.id), reverse=True)

    def search(self, user, query):
        """Notes whose title, body or tags contain the query (case-insensitive)."""
        key = (user.id, (query or "").strip().lower())
        if key not in self._search_cache:
            q = key[1]
            self._search_cache[key] = [
                n for n in self.list(user)
                if q in n.title.lower() or q in n.body.lower() or q in n.tags
            ]
        return self._search_cache[key]
