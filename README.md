# Campus API Python

Python client library for NYJC Campus API, providing unified access to campus services including authentication, assignments, circles, submissions, and timetable management.

## Overview

The Campus API Python library is a comprehensive client for interacting with the NYJC Campus backend services. It provides a unified interface for server-to-server and device-based authentication, enabling secure access to various campus resources through a consistent API.

## Features

- Unified client interface for all Campus services
- Support for server-to-server and device authentication modes
- OAuth2 integration with Google Workspace (nyjc.edu.sg domain)
- Comprehensive API coverage for assignments, circles, submissions, and timetable
- Session management and secure request handling
- Error handling and logging support

## Tech Stack

- **Language:** Python 3.11 and 3.12
- **Package Management:** Poetry
- **Dependencies:**
  - `flask` - Web framework (for integration)
  - `campus-suite` - Campus backend services
  - Additional dependencies managed via Poetry

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
│   ├── api/
│   │   └── v1/             # API service clients
│   │       ├── assignments.py
│   │       ├── circles.py
│   │       ├── submissions.py
│   │       └── timetable.py
│   ├── auth/
│   │   └── v1/             # Authentication clients
│   │       ├── clients.py
│   │       ├── credentials.py
│   │       ├── logins.py
│   │       ├── oauth.py
│   │       ├── root.py
│   │       ├── sessions.py
│   │       ├── users.py
│   │       └── vaults.py
│   ├── integrations/
│   │   └── v1/             # Integrations registry (auth service, public)
│   └── json_client/        # JSON client implementation
│       ├── __init__.py
│       └── interface.py
├── scripts/                # Utility scripts
│   └── refresh-dependencies.sh
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

`with_user_session()` installs a one-shot 401 auto-refresh hook on the auth and api clients by default (issue #89): when a request comes back 401 because the bearer expired mid-session, the session token is force-refreshed once and the request retried with the new Authorization header. If the refresh fails, the original 401 surfaces to the caller as before. Pass `refresh_on_401=False` for the old behaviour.

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

## Service Base URLs

Each service client (`campus.auth`, `campus.api`, `campus.audit`) resolves its base URL in this order:

1. **Explicit URL config** — the `CAMPUS_AUTH_URL` / `CAMPUS_API_URL` / `CAMPUS_AUDIT_URL` environment variable, if set. Use this for local testing deployments and custom endpoints (e.g. `CAMPUS_AUTH_URL=http://localhost:5000`).
2. **ENV-based defaults** — selected by `ENV` (or `CAMPUS_ENV`):

| ENV value | auth | api | audit |
|-----------|------|-----|-------|
| `development` (default) | `https://campusauth-development.up.railway.app` | `https://campusapi-development.up.railway.app` | `https://campusaudit-development.up.railway.app` |
| `staging` | `https://auth.campus.nyjc.dev` | `https://api.campus.nyjc.dev` | `https://audit.campus.nyjc.dev` |
| `production` | `https://auth.campus.nyjc.app` | `https://api.campus.nyjc.app` | `https://audit.campus.nyjc.app` |

> **Deprecated (issue #52):** base URLs are no longer derived from the `HOSTNAME` environment variable. Deployments that relied on the `DEPLOY` service suffix (e.g. `campus.auth`) or `ENV=testing` to produce `https://{HOSTNAME}` URLs now get a `DeprecationWarning` and the ENV-based default instead — set `CAMPUS_AUTH_URL` / `CAMPUS_API_URL` explicitly to point the client at those deployments.

## Environment Variables

| Variable | Required | Mode | Description |
|----------|----------|------|-------------|
| `CLIENT_ID` | Yes | Server | OAuth client ID from Campus auth |
| `CLIENT_SECRET` | Yes | Server | OAuth client secret from Campus auth |
| `CAMPUS_AUTH_URL` | No | All | Auth service base URL (overrides ENV default) |
| `CAMPUS_API_URL` | No | All | API service base URL (overrides ENV default) |
| `CAMPUS_AUDIT_URL` | No | All | Audit service base URL (overrides ENV default) |
| `AUDIT_API_KEY` | Yes (audit) | All | Audit service API key (`audit_v1_...`); sent as the audit root's Bearer token |
| `ENV` / `CAMPUS_ENV` | No | All | Deployment environment selecting default URLs: `development` (default), `staging`, `production` |

## Development

### Refreshing Dependencies

If you make changes to the local `campus-suite` package:

```bash
./scripts/refresh-dependencies.sh
```

This will update `poetry.lock` and reinstall dependencies from the latest commits.

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

- [campus](https://github.com/nyjc-computing/campus) - Campus backend services
- [campus-suite](https://github.com/nyjc-computing/campus-suite) - Campus suite components

## License

Internal use by NYJC Computing team.
