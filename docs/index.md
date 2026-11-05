# Campus API Python

Python SDK for the NYJC Campus school platform: one client for the
Campus API (assignments, circles, files, hosted apps, submissions,
timetable), Campus Auth (OAuth, login sessions, clients, grants,
vaults), Campus Audit (traces, API keys), and the first-party
integrations registry.

```python
from campus_python import Campus

campus = Campus()                      # server mode (CLIENT_ID/CLIENT_SECRET)

for assignment in campus.api.assignments.list():
    print(assignment.title)

with campus.with_user_session():       # acting as the logged-in user
    campus.api.circles["circle_ab12cd34"].members.add("user_jane", 15)
```

## Why it looks like this

- **One facade, four service roots.** [`campus.api`][campus_python.api.v1.ApiRoot],
  [`campus.auth`][campus_python.auth.v1.AuthRoot],
  [`campus.audit`][campus_python.audit.v1.AuditRoot], and
  [`campus.integrations`][campus_python.integrations.v1.IntegrationsRoot]
  each resolve their own base URL from the environment and carry their
  own resource tree.
- **Resources are addressable objects.** `campus.api.circles["circle_ab12cd34"]`
  is a resource you can `.get()`, `.update()`, `.delete()` — and drill
  into (` members`, `entries`, `responses`, ...). See the
  [Campus API reference](reference/api.md).
- **Framework-free.** The SDK holds no web-framework dependency and no
  request state. Flask apps join it through the `campus.flask_campus`
  middleware via two injectable seams — see
  [Authentication](authentication.md#hosting-in-a-flask-app) and
  [Tracing](tracing.md).
- **Errors are typed by status.** Every non-2xx response raises an
  [`APIError`][campus_python.errors.APIError] subclass
  ([`NotFoundError`][campus_python.errors.NotFoundError],
  [`ValidationError`][campus_python.errors.ValidationError] with
  field details, ...). See [Errors](reference/errors.md).

## Where to go next

| If you want to... | Read |
|---|---|
| install and make a first call | [Getting started](getting-started.md) |
| authenticate (server, device, user sessions) | [Authentication](authentication.md) |
| attribute calls to journeys/deployments in audit | [Tracing](tracing.md) |
| run the SDK against your own transport | [Custom clients](custom-clients.md) |
| add a resource or endpoint | [Extending the SDK](extending.md) |
| look up any method | [Reference](reference/campus.md) |
