"""campus.python.auth.v1.sessionstore

Client-side session-id storage seam for the auth session/login lanes.

The SDK's session and login resources historically resolved their
current session ids directly from the host's flask.session (and wrote
new ids back into it). Hosts that own their own request state — e.g.
flask_campus — can instead install a provider that resolves the
current id per lane, keeping the SDK free of any particular web
framework:

    from campus_python.auth import v1
    v1.set_session_id_provider(my_resolver)

The provider takes a lane name — "session" for auth sessions
(sessions.SESSION_STORAGE_KEY) or "login" for login sessions
(logins.LOGIN_STORAGE_KEY) — and returns the current session id or
None. Every read resolves in the same order: explicit argument >
provider > the legacy flask.session read. Writes still go to the
legacy flask.session keys while the provider seam rolls out; a host
that owns storage writes the same keys itself, so both paths stay
consistent (identical values, idempotent).
"""

__all__ = [
    "set_session_id_provider",
]

import typing
import warnings

# Lane names, shared with AuthRoot's user cache namespacing.
LANE_SESSION = "session"
LANE_LOGIN = "login"

# Provider contract: lane name -> current session id or None.
_session_id_provider: typing.Callable[[str], str | None] | None = None


def warn_legacy_lane_read(site: str) -> None:
    """Announce a legacy flask.session id read (no provider installed).

    Fires only on the legacy read lane — hosts that installed a
    session-id provider (flask_campus) never hit it, and the compat
    writes stay silent. Removed with the flask lane in 0.5.0.
    """
    warnings.warn(
        f"{site} read the login id from flask.session (legacy lane); "
        "install campus_python.auth.v1.set_session_id_provider or "
        "migrate to the flask_campus middleware — the legacy lane is "
        "deprecated and will be removed in campus_api_python 0.5.0. "
        "Ref: campus#1037, classroom#72.",
        DeprecationWarning,
        stacklevel=3,
    )


def set_session_id_provider(
        provider: typing.Callable[[str], str | None] | None,
) -> None:
    """Install (or clear) the session-id resolver for both lanes.

    The provider is consulted whenever a resource method needs the
    current session id and none was passed explicitly. Pass None to
    revert to the legacy flask.session-only behavior (tests).
    """
    global _session_id_provider
    _session_id_provider = provider


def resolve_session_id(kind: str) -> str | None:
    """The installed provider's id for the lane, or None."""
    if _session_id_provider is None:
        return None
    return _session_id_provider(kind)
