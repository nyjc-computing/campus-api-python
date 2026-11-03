"""campus.python.auth.v1.sessionstore

Client-side session-id resolution seam for the auth session/login
lanes.

The SDK never touches a web-framework session store: hosts that keep
their session ids in their own request state — e.g. flask_campus,
which stores them under sessions.SESSION_STORAGE_KEY /
logins.LOGIN_STORAGE_KEY — install a provider that resolves the
current id per lane:

    from campus_python.auth import v1
    v1.set_session_id_provider(my_resolver)

The provider takes a lane name — "session" for auth sessions or
"login" for login sessions — and returns the current session id or
None. Every read resolves explicit argument first, then the provider;
with neither, the resource methods raise AuthenticationError naming
the seam to install.
"""

__all__ = [
    "set_session_id_provider",
]

import typing

# Lane names, shared with AuthRoot's user cache namespacing.
LANE_SESSION = "session"
LANE_LOGIN = "login"

# Provider contract: lane name -> current session id or None.
_session_id_provider: typing.Callable[[str], str | None] | None = None


def set_session_id_provider(
        provider: typing.Callable[[str], str | None] | None,
) -> None:
    """Install (or clear) the session-id resolver for both lanes.

    The provider is consulted whenever a resource method needs the
    current session id and none was passed explicitly. Pass None to
    clear it (tests).
    """
    global _session_id_provider
    _session_id_provider = provider


def resolve_session_id(kind: str) -> str | None:
    """The installed provider's id for the lane, or None."""
    if _session_id_provider is None:
        return None
    return _session_id_provider(kind)
