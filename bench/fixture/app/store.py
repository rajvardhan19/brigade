"""In-memory storage. Each App has its own Store."""
from app.models import Note, Session, User


class Store:
    def __init__(self):
        self.users = {}            # id -> User
        self.users_by_email = {}   # lowercased email -> user id
        self.notes = {}            # id -> Note
        self.sessions = {}         # token -> Session
        self._next_user_id = 1
        self._next_note_id = 1

    # users

    def add_user(self, email, password_hash, salt, created_at) -> User:
        user = User(self._next_user_id, email, password_hash, salt, created_at)
        self._next_user_id += 1
        self.users[user.id] = user
        self.users_by_email[email.lower()] = user.id
        return user

    def get_user(self, user_id):
        return self.users.get(user_id)

    def get_user_by_email(self, email):
        user_id = self.users_by_email.get(email.lower())
        return self.users.get(user_id) if user_id is not None else None

    # notes

    def add_note(self, owner_id, title, body, tags, now) -> Note:
        note = Note(self._next_note_id, owner_id, title, body, list(tags), now, now)
        self._next_note_id += 1
        self.notes[note.id] = note
        return note

    def get_note(self, note_id):
        return self.notes.get(note_id)

    def delete_note(self, note_id):
        self.notes.pop(note_id, None)

    def notes_for_owner(self, owner_id):
        return [n for n in self.notes.values() if n.owner_id == owner_id]

    # sessions

    def add_session(self, session: Session):
        self.sessions[session.token] = session

    def get_session(self, token):
        return self.sessions.get(token)

    def delete_session(self, token):
        self.sessions.pop(token, None)
