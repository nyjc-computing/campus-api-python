"""campus.client.core

Unified Campus client interface providing consistent access to all services.
"""

__all__ = (
    "Campus",
    "errors",
)

import logging
from collections.abc import Iterator
from contextlib import contextmanager

import campus.model
from campus.common import env, services

from . import errors
from .api.v1 import ApiRoot
from .audit.v1 import AuditRoot
from .auth.v1 import AuthRoot
from .integrations.v1 import IntegrationsRoot
from .json_client import CampusRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default request timeout (seconds) for Campus clients whose host does
# not set one explicitly (tier-2 config: shared default = code constant
# next to the client, override = env, per-deployment = env/vault).
DEFAULT_CLIENT_TIMEOUT = 60


def _resolve_client_timeout(explicit: int | None) -> int:
    """Resolve the request timeout for a new Campus client.

    Precedence: explicit argument > CAMPUS_CLIENT_TIMEOUT env var >
    DEFAULT_CLIENT_TIMEOUT. An invalid env value fails open (default
    applied, WARN logged) rather than breaking construction.
    """
    if explicit is not None:
        return explicit
    raw = env.get("CAMPUS_CLIENT_TIMEOUT")
    if not raw:
        return DEFAULT_CLIENT_TIMEOUT
    try:
        timeout = int(raw)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid CAMPUS_CLIENT_TIMEOUT=%r; using default %d",
            raw, DEFAULT_CLIENT_TIMEOUT,
        )
        return DEFAULT_CLIENT_TIMEOUT
    if timeout < 1:
        logger.warning(
            "CAMPUS_CLIENT_TIMEOUT=%d < 1; using default %d",
            timeout, DEFAULT_CLIENT_TIMEOUT,
        )
        return DEFAULT_CLIENT_TIMEOUT
    return timeout


def _resolve_base_url(service: str) -> str:
    """Resolve the base URL for a Campus service via the shared registry.

    Delegates to campus.common.services.resolve_base_url (campus-common
    0.3.0+), whose precedence is:
        1. CAMPUS_<SERVICE>_URL (the `url_var` passed here)
        2. <SERVICE>_URL (bare alias)
        3. CAMPUS_BASE_URL, then BASE_URL — one origin fronting every
           service (gateway / single-server deployments)

    The environment is the source of truth: an unconfigured service
    raises ValueError naming the variables to set. Campus ships no
    baked-in deployment topology, so there is no ENV-tier fallback and
    no HOSTNAME-migration warning anymore (#52's migration is complete).
    """
    return services.resolve_base_url(f"campus.{service}")


class Campus:
    """Unified Campus client interface.

    Provides consistent access patterns across all Campus services.

    Modes:
    - mode="server" (default): For server-to-server communication (e.g., campus.api).
      Requires CLIENT_ID and CLIENT_SECRET environment variables.
    - mode="device": For public clients (e.g., CLI) that don't have secrets.
      No credentials required; only public OAuth endpoints are accessible.

    Service base URLs are resolved per service (auth, api, audit)
    via the campus.common.services registry, in this order:
    1. CAMPUS_AUTH_URL / CAMPUS_API_URL / CAMPUS_AUDIT_URL.
    2. Bare aliases: AUTH_URL / API_URL / AUDIT_URL.
    3. CAMPUS_BASE_URL, then BASE_URL — one origin fronting every
       service (gateway / single-server deployments).

    The environment is the source of truth: Campus ships no baked-in
    deployment topology, so an unconfigured service raises ValueError.

    See the API Reference for usage examples.
    """

    def __init__(self, timeout: int | None = None, mode: str = "server"):
        """Initialize unified Campus client with all service clients.

        Args:
            timeout: Request timeout in seconds. Resolution order:
                explicit argument > CAMPUS_CLIENT_TIMEOUT env var >
                DEFAULT_CLIENT_TIMEOUT (60). Invalid env values fail
                open (default applied, WARN logged).
            mode: Client mode - "server" (default) or "device".

        Raises:
            OSError: If mode="server" and CLIENT_ID or CLIENT_SECRET
                environment variables are not set.
        """
        self.timeout = _resolve_client_timeout(timeout)
        self._mode = mode

        # Server mode requires credentials
        if mode == "server":
            env.require("CLIENT_ID", "CLIENT_SECRET")
        elif mode != "device":
            raise ValueError(f"Invalid mode: {mode}. Must be 'server' or 'device'")

    @property
    def auth(self) -> AuthRoot:
        """Get the auth service resource."""
        if not hasattr(self, "_auth"):
            base_url = _resolve_base_url("auth")
            self._auth = AuthRoot(
                json_client=CampusRequest(
                    base_url=base_url,
                    timeout=self.timeout,
                    mode=self._mode,
                )
            )
        return self._auth

    @property
    def api(self) -> ApiRoot:
        """Get the api service resource."""
        if not hasattr(self, "_api"):
            base_url = _resolve_base_url("api")
            self._api = ApiRoot(
                json_client=CampusRequest(
                    base_url=base_url,
                    timeout=self.timeout,
                    mode=self._mode,
                )
            )
        return self._api

    @property
    def audit(self) -> AuditRoot:
        """Get the audit service resource.

        The audit service authenticates with one of its own API keys
        (AUDIT_API_KEY env var, an `audit_v1_...` value) sent as a
        Bearer token — CLIENT_ID/CLIENT_SECRET are not accepted — so
        this root carries its own JsonClient, created in device mode
        to avoid requiring app credentials.
        """
        if not hasattr(self, "_audit"):
            base_url = _resolve_base_url("audit")
            client = CampusRequest(
                base_url=base_url,
                timeout=self.timeout,
                mode="device",
            )
            env.require("AUDIT_API_KEY")
            client.set_bearer_authorization(env.get("AUDIT_API_KEY") or "")
            self._audit = AuditRoot(json_client=client)
        return self._audit

    @property
    def integrations(self) -> IntegrationsRoot:
        """Get the integrations registry resource (auth service).

        Public, read-only catalog of first-party integrations (#56),
        served by the auth service at /integrations/v1 (outside
        /auth/v1); shares the auth client so it works in device mode
        too.
        """
        if not hasattr(self, "_integrations"):
            self._integrations = IntegrationsRoot(
                json_client=self.auth.client
            )
        return self._integrations

    def _get_token_from_session(self) -> campus.model.OAuthToken:
        """Re-acquire the login session user's campus bearer.

        The login-session id resolves via the injected session-id
        provider (flask_campus installs one reading its request-state
        storage) or an explicit id — the SDK holds no request state.

        One endpoint call (campus#963/#964, invariant A10):
        POST /logins/<session_id>/token re-acquires the session user's
        campus bearer with the client's Basic credentials. The
        operator-gated credentials GET → refresh grant → credentials
        PATCH legs (#854) are gone, with no fallback to them; the
        server rotates an expired grant token itself, so there is no
        proactive is_expired() check or write-back here — re-calling
        this method (as the 401 hook does) is the refresh.
        """
        return self.auth.get_token()

    def revoke_session(self) -> None:
        """Revoke the current authorization token."""
        self.api.client.reset_authorization()
        self.auth.client.reset_authorization()

    def use_token(self, token: campus.model.OAuthToken) -> None:
        """Set Bearer Authorization header using the given token.

        Args:
            token (campus.model.Token): Token to use for authorization.
        """
        self.api.client.set_bearer_authorization(token.access_token)
        self.auth.client.set_bearer_authorization(token.access_token)

    @contextmanager
    def with_app_session(self) -> Iterator["Campus"]:
        """Context manager yielding CampusRequest with app credentials.

        Usage:
            with campus.with_app_session() as client:
                # use client for requests

        Yields:
            CampusRequest: JSON client with app credentials set.
        """
        try:
            token = self.auth.token(grant_type="client_credentials")
            self.use_token(token)
            yield self
        except Exception:
            raise
        finally:
            self.revoke_session()

    @contextmanager
    def with_user_session(
            self,
            *,
            refresh_on_401: bool = True,
    ) -> Iterator["Campus"]:
        """Context manager yielding CampusRequest with user credentials.

        Usage:
            with campus.with_user_session() as client:
                # use client for requests

        By default a 401 auto-refresh hook is installed on the auth and
        api clients for the duration of the session (issue #89): when a
        request comes back 401 because the bearer expired after the
        re-acquisition below, the token is re-acquired once via the
        login-session token route (campus#964) and the request retried
        with the new Authorization header. The retry cannot
        double-execute work — Campus services reject unauthenticated
        requests in a before_request authenticator before any handler
        runs. If the re-acquisition itself fails, the original 401
        response surfaces to the caller as before. Pass
        refresh_on_401=False for the old behaviour.

        Yields:
            Campus: JSON client with user credentials set.
        """
        token = self._get_token_from_session()
        self.use_token(token)

        hooked_clients = []
        if refresh_on_401:
            refreshing = False

            def refresh_bearer() -> str | None:
                """Re-acquire the session token once.

                Returns the new bearer token for the client to retry
                with, or None on failure (the original 401 then
                surfaces). Re-entrant calls (the re-acquisition
                round-trip itself hitting a 401) bail out immediately.

                The round-trip authenticates as the client (Basic):
                the login-session token route denies user principals
                outright (campus#964/A10), so the session's stale
                bearer must not be presented mid-rotation.
                """
                nonlocal refreshing
                if refreshing:
                    return None
                refreshing = True
                try:
                    self.revoke_session()
                    refreshed = self._get_token_from_session()
                except errors.APIError:
                    self.use_token(token)
                    return None
                finally:
                    refreshing = False
                self.use_token(refreshed)
                return refreshed.access_token

            for client in (self.api.client, self.auth.client):
                # The 401 hook is an optional JsonClient capability
                # (see json_client.interface) — feature-detect it.
                if isinstance(client, CampusRequest):
                    client.set_unauthorized_hook(refresh_bearer)
                    hooked_clients.append(client)

        try:
            yield self
        except Exception:
            raise
        finally:
            for client in hooked_clients:
                client.set_unauthorized_hook(None)
            self.revoke_session()
