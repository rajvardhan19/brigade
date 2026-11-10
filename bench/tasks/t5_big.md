Grow this notes service with four features.

1. Sharing
- POST /notes/<id>/share with {"email": ..., "permission": "view" or "edit"} lets the note's owner share it with another registered user. Sharing again with the same user replaces the permission. Returns 200 {"status": "ok"}. Errors: 400 {"error": "unknown user"} if no account has that email (emails match case-insensitively), 400 {"error": "invalid permission"}, and 400 {"error": "cannot share with yourself"}.
- POST /notes/<id>/unshare with {"email": ...} removes that user's access. Returns 200 {"status": "ok"}.
- GET /notes/<id> returns the note (same shape as other note responses) to its owner and to anyone it is shared with.
- GET /notes/shared returns {"notes": [...]}: the notes other users have shared with the current user, newest first, each with an extra "permission" field. GET /notes and GET /search keep returning only the user's own notes.
- A user with "edit" permission can PATCH the note. A user with "view" permission who tries gets 403 {"error": "forbidden"}. Only the owner can delete, share or unshare; other users with access get 403 {"error": "forbidden"}. Users with no access get 404 {"error": "note not found"} for everything, as today.
- Changes made by an editor must show up for the owner everywhere immediately, including in search results.

2. Change history
- Every successful create or update of a note records an entry {"action": "created" or "updated", "by": <email of the user who made the change>, "at": <app.clock.now() at that moment>, "title": <the title after the change>}. Failed updates record nothing.
- GET /notes/<id>/history returns {"history": [...]}, oldest first, to the owner and to anyone the note is shared with. Deleting a note deletes its history.

3. Markdown export
- GET /notes/<id>/export returns {"markdown": ...} to the owner and to anyone the note is shared with. The format is the title as a level-1 heading, then the body, then a tags line, separated by blank lines and ending with a newline. Leave out the body or the tags line when it is empty. Example: a note titled "Groceries" with body "milk\neggs" and tags ["home", "weekly"] exports as "# Groceries\n\nmilk\neggs\n\nTags: home, weekly\n". A note titled "Empty" with no body and no tags exports as "# Empty\n".

4. Login rate limiting
- After 5 failed login attempts in a row for the same email (case-insensitive), every login attempt for that email gets 429 {"error": "too many attempts"} for the next 15 minutes, counted from the 5th failure, even with the right password. Attempts during the lockout don't extend it and don't count as failures. When the lockout ends, the count starts again from zero.
- A successful login resets the count. Failures for one email don't affect other emails.
- Count attempts for emails that have no account the same way, so the limiter doesn't reveal which emails are registered.

Keep all existing tests passing and add tests for each feature.
