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

- **Server Mode:** For server-to-server communication. Requires `CLIENT_ID` and `CLIENT_SECRET` environment variables.
- **Device Mode:** For public clients (e.g., CLI tools). No credentials required; limited to public endpoints.

## Environment Variables

| Variable | Required | Mode | Description |
|----------|----------|------|-------------|
| `CLIENT_ID` | Yes | Server | OAuth client ID from Campus auth |
| `CLIENT_SECRET` | Yes | Server | OAuth client secret from Campus auth |

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
