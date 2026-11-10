Add a password reset feature to this notes service.

- POST /password-reset/request with {"email": ...} always returns 200 {"status": "ok"}, whether or not the account exists, so it never reveals which emails are registered. If the account exists, send an email through the app's outbox (app.outbox.send) to that address with the subject "Password reset" and a body containing a line `token: <token>`.
- POST /password-reset/confirm with {"token": ..., "new_password": ...} sets the new password and returns 200 {"status": "ok"}. It returns 400 {"error": "invalid token"} if the token is unknown, already used or expired, and 400 {"error": "weak password"} if the new password fails the existing password policy (in that case the token stays usable).
- Tokens expire 30 minutes after they are issued (use app.clock.now()), work only once, and requesting a new reset invalidates any earlier unused token for that user. Store only a hash of each token, never the raw token.
- After a successful reset, log the user out everywhere: all of their existing sessions must stop working.
- Add tests.
