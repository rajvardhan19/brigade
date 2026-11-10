Two changes to this notes service:

1. Rename the note field `owner_id` to `author_id` everywhere: the model, the store, the note logic, the API responses and the tests. No `owner_id` should remain in the code.
2. Add tag filtering: GET /notes?tag=<tag> returns only the current user's notes that have that tag (case-insensitive), still newest first, and still honoring ?limit=.

Keep all existing tests passing (updated for the rename) and add tests for the tag filter.
