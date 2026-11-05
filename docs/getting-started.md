# Getting started

## Requirements

- Python 3.11–3.13 (3.14 tested, unofficial bugfix tier)
- [Poetry](https://python-poetry.org/) (or pip, for consumers)
- Campus service URLs reachable from your environment

## Installation

Consumers pin the release wheel by URL (pip resolves it; the release
must exist first — see [Releases](#releases)):

```toml
# pyproject.toml
campus-api-python = {url = "https://github.com/nyjc-computing/campus-api-python/releases/download/vX.Y.Z/campus_api_python-X.Y.Z-py3-none-any.whl"}
```

Then `poetry install` / `poetry lock` as usual. The SDK depends only
on `requests` and the `campus-common` / `campus-model` wheels — it
imports no campus-suite module and holds no web framework.

## Configuration

The environment is the source of truth. Campus ships no baked-in
deployment topology: an unconfigured service raises `ValueError`
naming the variables to set.

| Variable | Required | Mode | Description |
|----------|----------|------|-------------|
| `CLIENT_ID` | Yes | Server | OAuth client ID from Campus auth |
| `CLIENT_SECRET` | Yes | Server | OAuth client secret from Campus auth |
| `CAMPUS_AUTH_URL` | No | All | Auth service base URL (highest precedence) |
| `CAMPUS_API_URL` | No | All | API service base URL (highest precedence) |
| `CAMPUS_AUDIT_URL` | No | All | Audit service base URL (highest precedence) |
| `AUDIT_API_KEY` | Yes (audit) | All | Audit API key (`audit_v1_...`), sent as the audit root's Bearer |
| `CAMPUS_CLIENT_TIMEOUT` | No | All | Request timeout in seconds (default 60); invalid values are logged and ignored |
| `CAMPUS_BASE_URL` / `BASE_URL` | No | All | One origin fronting every service (gateway deployments); consulted last |

Per-service precedence: `CAMPUS_<SERVICE>_URL` → `<SERVICE>_URL`
(bare alias) → `CAMPUS_BASE_URL` → `BASE_URL`. For local testing set
e.g. `CAMPUS_AUTH_URL=http://localhost:5000`.

## First calls

=== "Server mode"

    ```python
    from campus_python import Campus

    campus = Campus(timeout=30)   # mode="server" is the default

    # Campus API
    for assignment in campus.api.assignments.list():
        print(assignment.title)

    timetable_id = campus.api.timetable.get_current()

    # Campus Auth (requires CLIENT_ID/CLIENT_SECRET; Basic-authenticated)
    client = campus.auth.clients["client_myapp"]
    print(client.get().name)
    ```

=== "Device mode"

    ```python
    from campus_python import Campus

    campus = Campus(mode="device")   # no credentials required

    # Public, read-only registry — works without a token
    for integration in campus.integrations.list():
        print(integration.provider, integration.connectable)
    ```

    Authenticating a device client (no secret) is the
    [device flow](authentication.md#device-flow-public-clients) —
    after it returns a token, `wait_for_token()`'s result is applied
    with [`use_token()`][campus_python.Campus.use_token].

=== "User sessions (Flask hosts)"

    ```python
    with campus.with_user_session() as client:
        # every call inside acts as the logged-in user; an expired
        # bearer auto-refreshes once (401 hook, on by default)
        campus.api.submissions.new(assignment_id=aid, student_id=sid, course_id=cid)
    ```

    Requires a login session id — normally supplied by the
    `campus.flask_campus` middleware. See
    [Authentication](authentication.md#user-sessions).

## Error handling

Every non-2xx response raises an `APIError` subclass mapped by status
code — see the [Errors reference](reference/errors.md).

```python
from campus_python import errors

try:
    campus.api.assignments["assignment_404"].get()
except errors.NotFoundError as err:
    print("no such assignment:", err.error_description)
except errors.ValidationError as err:
    for field_err in err.field_errors:
        print(field_err.field, field_err.code, field_err.message)
```

Auth-related errors carry the OAuth protocol error where one exists:
`err.oauth_error` (e.g. `"invalid_grant"`) survives even when the
server strips envelope details in production.

## Releases

The SDK follows the fleet's strict 0.x scheme: patch releases are
additive, minor releases are the breaking line. Every release
publishes a wheel attached to its GitHub release; cut one by bumping
`version` in `pyproject.toml`, then pushing an annotated `v*` tag —
the tag message becomes the release body and CI builds the wheel
(with a fresh-venv install smoke) automatically.
