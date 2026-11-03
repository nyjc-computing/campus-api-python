# Campus API Python

Python client library for NYJC Campus API, providing unified access to campus services including authentication, assignments, circles, submissions, and timetable management.

## Overview

The Campus API Python library (`campus_python`) is a comprehensive client for interacting with the NYJC Campus backend services. It provides a unified interface for server-to-server and device-based authentication, enabling secure access to various campus resources through a consistent API.

**The SDK is framework-free**: it holds no web-framework dependency and no request state of its own. The browser login flow and client-side session storage live in the [`campus.flask_campus`](https://github.com/nyjc-computing/campus) middleware (see [Session & trace integration](#session--trace-integration-the-flask_campus-boundary) below); this library owns transport, tokens, and the injectable seams that let any host supply request-scoped identity.

## Features

- Unified client interface for all Campus services
- Support for server-to-server and device authentication modes
- OAuth2 integration with Google Workspace (nyjc.edu.sg domain)
- Comprehensive API coverage for assignments, circles, submissions, and timetable
- Campus Audit client: API keys (mint, scope, rotate, revoke) and traces
- User-session token lane (`with_user_session`) with one-shot 401 auto-refresh
- Injectable session-id / request-context providers — request-scoped identity without any web-framework coupling (flask_campus installs both)
- Error handling and logging support

## Tech Stack

- **Language:** Python 3.11–3.13 (3.14 tested, unofficial)
- **Package Management:** Poetry
- **Dependencies:**
  - `requests` - HTTP client (`json_client`)
  - `campus-common` / `campus-model` - Campus shared kernel and domain models (version-pinned release wheels)

  (flask was removed in 0.5.0 — the browser login flow moved to the flask_campus middleware; see `campus.auth.v1.sessionstore` for the history.)

## Setup

### Prerequisites

- Python 3.11 or 3.12
- Poetry
- Access to Campus development environment (for server mode)

This library is intended to support both Python 3.11 and Python 3.12.

### Installation

1. **Clone the repository** (if not already done):
   ```bash
   git clone https://github.com/nyjc-computing/campus-api-python.git
   cd campus-api-python
   ```

2. **Install dependencies**:
   ```bash
   poetry install
   ```

3. **Configure environment variables** (for server mode):

   Set the following environment variables:
   ```bash
   # Campus OAuth credentials (required for server mode)
   CLIENT_ID=your-client-id
   CLIENT_SECRET=your-client-secret
   ```

### Usage

Import and initialize the client:

```python
from campus_python import Campus

# For server-to-server communication
client = Campus(timeout=30, mode="server")

# For device/public clients
client = Campus(timeout=30, mode="device")

# Discover the first-party integrations Campus offers (public, read-only)
for integration in client.integrations.list():
    print(integration.provider, integration.connectable)
```

## Project Structure

```
campus-api-python/
├── campus_python/          # Main package
│   ├── __init__.py         # Main Campus client class
│   ├── errors.py           # Error handling
│   ├── interface.py        # Core interfaces
│   ├── tracing.py          # Trace/journey/device propagation + injectable request-context provider
│   ├── api/
│   │   └── v1/             # API service clients
│   │       ├── assignments.py
│   │       ├── circles.py
│   │       ├── submissions.py
│   │       └── timetable.py
│   ├── audit/
│   │   ├── ratelimit.py    # Ingest circuit breaker (campus.audit)
│   │   └── v1/             # Audit service clients
│   │       ├── apikeys.py  # Audit API keys (mint, scope, rotate, revoke)
│   │       └── traces.py   # Traces (list, search, ingest)
│   ├── auth/
│   │   └── v1/             # Authentication clients (framework-free)
│   │       ├── __init__.py # AuthRoot + user-session token lane
│   │       ├── sessionstore.py  # Injected session-id resolution seam
│   │       ├── broker.py
│   │       ├── clients.py
│   │       ├── connections.py
│   │       ├── credentials.py
│   │       ├── grants.py
│   │       ├── logins.py
│   │       ├── oauth.py
│   │       ├── root.py
│   │       ├── sessions.py
│   │       ├── users.py
│   │       └── vaults.py
│   ├── integrations/       # Integrations registry (auth service, public)
│   └── json_client/        # JSON client implementation
│       ├── __init__.py
│       └── interface.py
├── tests/                  # Test suite
│   └── unit/               # Unit tests
├── pyproject.toml          # Poetry configuration
└── README.md               # This file
```

## Authentication Modes

### Server Mode

For server-to-server communication. Uses Basic authentication with OAuth client credentials.

**Required Environment Variables:**
- `CLIENT_ID` - OAuth client ID from Campus auth
- `CLIENT_SECRET` - OAuth client secret from Campus auth

**Example:**
```python
from campus_python import Campus

# Server mode (default) - requires CLIENT_ID and CLIENT_SECRET
client = Campus(timeout=30, mode="server")
```

### Device Mode

For public clients (e.g., CLI tools) that authenticate users via OAuth device flow. Does not require client credentials. Instead, you set Bearer token authentication after obtaining an access token.

**No Environment Variables Required**

**Example:**
```python
from campus_python import Campus

# Device mode - no credentials required
client = Campus(timeout=30, mode="device")

# After obtaining an OAuth access token (via device flow)
access_token = "your-access-token"
client.api.client.set_bearer_authorization(access_token)
client.auth.client.set_bearer_authorization(access_token)

# Now you can make authenticated requests
```

### 401 Auto-Refresh

`with_user_session()` installs a one-shot 401 auto-refresh hook on the auth and api clients by default (issue #89): when a request comes back 401 because the bearer expired mid-session, the session token is re-acquired once via `POST /auth/v1/logins/<session_id>/token` (campus#964) and the request retried with the new Authorization header. If the re-acquisition fails, the original 401 surfaces to the caller as before. Pass `refresh_on_401=False` for the old behaviour.

```python
with campus.with_user_session() as client:            # hook on (default)
    ...

with campus.with_user_session(refresh_on_401=False) as client:  # hook off
    ...
```

The retry cannot double-execute work: Campus services authenticate requests in a `before_request` hook before any handler runs, so a 401 response means no handler executed.

Raw `CampusRequest` users can install their own hook (e.g. public clients driving `auth.refresh(stored)`):

```python
client.set_unauthorized_hook(lambda: campus.auth.refresh(stored, client_id="campus-cli").access_token)
```

### Session & trace integration (the flask_campus boundary)

The SDK holds **no session state**. Flask-based Campus apps use the
`campus.flask_campus` middleware, which owns the browser login flow
and the client-side session storage; the SDK owns transport and
tokens. The two layers join through two injectable providers:

| Concern | Owner | How the SDK sees it |
|---|---|---|
| Login flow (authorize / code exchange / logout) | `campus.flask_campus.context` | orchestrates this SDK's pure API calls (`sessions.new`, `exchange_code_for_token`, `logins.new`, …) |
| Session-id storage (browser session keys) | `campus.flask_campus.context` | `set_session_id_provider` — ids resolve **explicit argument > provider**; with neither, resource methods raise `AuthenticationError` naming the seam |
| Request-context trace headers (span/journey/device) | `campus.flask_campus.propagation` (installed by `campus.audit.middleware.init_app`) | `tracing.set_request_context_provider` — provider output is attached verbatim to outbound calls; with no provider, calls carry only the process boot journey |
| User-session token lane (`with_user_session` / `get_token`) | this SDK | pure API orchestration (bearer setup, 401 auto-refresh); the session id arrives via the provider above |

Non-Flask hosts need none of this: the CLI authenticates via device
flow, stores tokens in its own keyring, and sets bearers directly
(`client.api.client.set_bearer_authorization(...)`). Out-of-request
SDK calls always carry the process boot journey (`X-Journey-ID` /
`X-Campus-Device`, #114) for audit attribution; see
`campus_python.tracing`.

> **History:** `AuthRoot.authorize/finalize/logout/push_context` and
> the flask.session-backed storage used to live here. They were
> deprecated in 0.4.0 and removed in 0.5.0 in favor of the
> flask_campus middleware (campus#1037).

## Service Base URLs

Each service client (`campus.auth`, `campus.api`, `campus.audit`)
resolves its base URL through the shared registry
(`campus.common.services.resolve_base_url`, campus-common 0.3.0+).
The environment is the source of truth — Campus ships no baked-in
deployment topology:

1. `CAMPUS_AUTH_URL` / `CAMPUS_API_URL` / `CAMPUS_AUDIT_URL` — the per-service variable. Use this for local testing deployments and custom endpoints (e.g. `CAMPUS_AUTH_URL=http://localhost:5000`).
2. `<SERVICE>_URL` — bare alias (`AUTH_URL`, `API_URL`, `AUDIT_URL`).
3. `CAMPUS_BASE_URL`, then `BASE_URL` — one origin fronting every service (gateway / single-server deployments).

An unconfigured service raises `ValueError` naming the variables to
set. (The former ENV-tier fallback table and the HOSTNAME-derived
URLs were removed in #127 — issue #52's migration is complete.)

## Environment Variables

| Variable | Required | Mode | Description |
|----------|----------|------|-------------|
| `CLIENT_ID` | Yes | Server | OAuth client ID from Campus auth |
| `CLIENT_SECRET` | Yes | Server | OAuth client secret from Campus auth |
| `CAMPUS_AUTH_URL` | No | All | Auth service base URL (overrides ENV default) |
| `CAMPUS_API_URL` | No | All | API service base URL (overrides ENV default) |
| `CAMPUS_AUDIT_URL` | No | All | Audit service base URL (overrides ENV default) |
| `AUDIT_API_KEY` | Yes (audit) | All | Audit service API key (`audit_v1_...`); sent as the audit root's Bearer token |
| `CAMPUS_CLIENT_TIMEOUT` | No | All | Request timeout in seconds for clients constructed without an explicit `timeout` (default 60). Invalid values are logged and ignored |
| `CAMPUS_BASE_URL` / `BASE_URL` | No | All | One origin fronting every service (gateway / single-server deployments); consulted last |

## Development

### Updating Dependencies

The SDK depends on the campus-common and campus-model **release wheels**
(pinned by URL in `pyproject.toml`), not on campus-suite — it imports no
campus-suite module. To pick up a new wheel release: edit the URL, run
`poetry lock`, then `poetry install` (or `poetry sync` to also remove
packages the old lock pulled in). Read the release's CHANGELOG first —
both dists use strict 0.x versioning (pre-1.0 minors may break).

### Testing

Run the test suite:

```bash
poetry run pytest
```

GitHub Actions runs the unit tests against both Python 3.11 and Python 3.12.

Unit tests are located in `tests/unit/`.

### Code Quality

The project uses Ruff for linting and formatting:

```bash
poetry run ruff check .
poetry run ruff format .
```

## Troubleshooting

### Import Errors

Ensure dependencies are installed:
```bash
poetry install
```

### Authentication Errors

For server mode, verify `CLIENT_ID` and `CLIENT_SECRET` are set correctly.

### Connection Issues

Check network connectivity and Campus service availability.

## Contributing

1. Follow the existing code style (enforced by Ruff)
2. Add unit tests for new features
3. Update documentation as needed
4. Commit with descriptive messages

## Related Projects

- [campus](https://github.com/nyjc-computing/campus) - Campus backend services; ships the `campus-suite` package, whose `campus.flask_campus` middleware is the supported way to build Flask apps on this SDK

## License

Internal use by NYJC Computing team.
