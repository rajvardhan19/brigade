# notes-service

A small note-taking service with accounts, login sessions, notes, tags and
search. Everything is in memory. `App.handle(method, path, body, token)` stands
in for an HTTP server: it takes a request and returns `(status, response_dict)`.

## Run the tests

    python3 -m unittest discover -s tests

Standard library only; no dependencies.

## Layout

| File | What it does |
|---|---|
| `app/api.py` | `App`: routes requests to the services, serializes responses |
| `app/auth.py` | register, login, logout, `require_user` |
| `app/passwords.py` | password hashing and the password policy |
| `app/notes.py` | `NoteService`: create, update, delete, list, search (cached) |
| `app/store.py` | in-memory storage for users, notes and sessions |
| `app/models.py` | `User`, `Note`, `Session` dataclasses |
| `app/mailer.py` | `Outbox`: fake mail transport that records sent messages |
| `app/clock.py` | time source; tests move time with `clock.advance()` |

## Routes

| Method and path | Auth | Result |
|---|---|---|
| `POST /register` `{email, password}` | no | 201 `{id, email}` |
| `POST /login` `{email, password}` | no | 200 `{token}` |
| `POST /logout` | yes | 200 `{status: "ok"}` |
| `GET /notes?limit=` | yes | 200 `{notes: [...]}`, newest first |
| `POST /notes` `{title, body, tags}` | yes | 201 note |
| `PATCH /notes/<id>` `{title?, body?, tags?}` | yes | 200 note |
| `DELETE /notes/<id>` | yes | 204 |
| `GET /search?q=&limit=` | yes | 200 `{notes: [...]}` |

Errors come back as `{"error": "<message>"}`.

## Conventions

- Always get the time from `app.clock.now()`, never `time.time()`.
- Emails are matched case-insensitively.
