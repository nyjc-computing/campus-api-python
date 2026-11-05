# Errors

Every non-2xx response raises an `APIError` subclass mapped from the
HTTP status code, parsed from the Campus error envelope (with a
legacy `error_code` fallback). Auth endpoints normalize to the same
hierarchy, and the OAuth protocol error survives even when the server
strips envelope details in production — it is recovered from the
`AUTH_*` error code and readable via `.oauth_error`.

```python
from campus_python import errors

try:
    campus.api.circles.new(name="dup", tag="project")
except errors.ValidationError as err:              # 422
    for field_err in err.get_errors_for_field("name"):
        print(field_err.code, field_err.message)   # e.g. CONFLICT / name collision
except errors.ConflictError as err:                # 409
    print(err.request_id)
except errors.AuthenticationError as err:          # 401
    if err.oauth_error == "invalid_grant":
        ...                                        # session gone — re-login
```

Common attributes on every error: `status_code`, `error` (machine
code), `error_description`, `request_id` (from the envelope, for
tracing), `details`, and `notes` (client-side headers/body for
debugging).

Naming note: the 501 class is this package's
`errors.NotImplementedError` — when catching broadly, qualify it
(`errors.NotImplementedError`) so it doesn't shadow the builtin.

| Status | Class | Typical cause |
|---|---|---|
| 400 | [`BadRequestError`][campus_python.errors.BadRequestError] | malformed request |
| 401 | [`AuthenticationError`][campus_python.errors.AuthenticationError] | missing/expired credentials, OAuth errors (`oauth_error`) |
| 403 | [`AccessDeniedError`][campus_python.errors.AccessDeniedError] | insufficient permission; broker `missing_scopes` in `details` |
| 404 | [`NotFoundError`][campus_python.errors.NotFoundError] | unknown id/slug/vault key |
| 409 | [`ConflictError`][campus_python.errors.ConflictError] | name collisions, duplicate resources |
| 422 | [`ValidationError`][campus_python.errors.ValidationError] | validation failure — inspect `.field_errors` |
| 429 | [`RateLimitExceededError`][campus_python.errors.RateLimitExceededError] | rate limited (traces ingest trips the client breaker first) |
| 500 | [`ServerError`][campus_python.errors.ServerError] | server-side failure (device-flow polls retry these) |
| 501 | [`errors.NotImplementedError`][campus_python.errors.NotImplementedError] | endpoint stubbed upstream |
| 502 | [`MalformedResponseError`][campus_python.errors.MalformedResponseError] | upstream returned garbage |
| 503 | [`UnavailableError`][campus_python.errors.UnavailableError] | service down |

::: campus_python.errors
