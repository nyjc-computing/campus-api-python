"""Shared test doubles for resource unit tests.

The make_* factories return (root, client) pairs backed by one mock
JSON client — the shape resource unit tests assert against: configure
the client's verb return values, then assert on the recorded calls.
json_response() builds a JsonResponse-like stub whose raise_for_status
behaves like the real one, so error-path tests get realistic raising
responses instead of hand-wired side effects.

Specialized setups (CampusRequest-based fakes, providers with extra
stubbing) keep their own local fixtures.
"""

from typing import Any
from unittest.mock import Mock

from campus_python import errors
from campus_python.api.v1 import ApiRoot
from campus_python.audit.v1 import AuditRoot
from campus_python.auth.v1 import AuthRoot
from campus_python.integrations.v1 import IntegrationsRoot


def make_client() -> Mock:
    """A bare Mock standing in for the JsonClient; calls record on it."""
    return Mock()


def make_api() -> "tuple[ApiRoot, Mock]":
    """Create an ApiRoot backed by a mock JSON client."""
    client = make_client()
    return ApiRoot(json_client=client), client


def make_auth() -> "tuple[AuthRoot, Mock]":
    """Create an AuthRoot backed by a mock JSON client."""
    client = make_client()
    return AuthRoot(json_client=client), client


def make_audit() -> "tuple[AuditRoot, Mock]":
    """Create an AuditRoot backed by a mock JSON client."""
    client = make_client()
    return AuditRoot(json_client=client), client


def make_integrations() -> "tuple[IntegrationsRoot, Mock]":
    """Create an IntegrationsRoot backed by a mock JSON client."""
    client = make_client()
    return IntegrationsRoot(json_client=client), client


def json_response(body: Any = None, status_code: int = 200) -> Mock:
    """A response stub carrying `body`.

    raise_for_status mirrors JsonResponse: a no-op on 2xx/3xx, the
    mapped APIError on 4xx/5xx. Headers stay a plain Mock attribute
    for tests that inspect them.
    """
    response = Mock()
    response.status_code = status_code
    response.json.return_value = body
    if status_code >= 400:
        response.raise_for_status.side_effect = errors.APIError.with_status_code(
            status_code, body
        )
    return response
