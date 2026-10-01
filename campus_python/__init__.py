"""campus.client.core

Unified Campus client interface providing consistent access to all services.
"""

__all__ = (
    "Campus",
    "errors",
)

import logging
import warnings
from collections.abc import Iterator
from contextlib import contextmanager

import campus.model
from campus.common import env

from . import errors
from .api.v1 import ApiRoot
from .auth.v1 import AuthRoot
from .json_client import CampusRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Development Railway deployments, used when no explicit URL is configured
AUTH_DEVELOPMENT_URL = "https://campusauth-development.up.railway.app"
API_DEVELOPMENT_URL = "https://campusapi-development.up.railway.app"


def _resolve_base_url(service: str, url_var: str, development_url: str) -> str:
    """Resolve the base URL for a Campus service.

    Precedence:
        1. Explicit URL config: the `url_var` environment variable
           (CAMPUS_AUTH_URL / CAMPUS_API_URL).
        2. ENV-based defaults: development Railway deployments,
           staging and production domains.

    Emits a DeprecationWarning if the environment would previously have
    produced a HOSTNAME-derived URL (a DEPLOY service suffix or
    ENV/CAMPUS_ENV=testing); those deployments must set `url_var`
    explicitly or accept the ENV-based default (issue #52).
    """
    explicit_url = env.get(url_var)
    if explicit_url:
        return explicit_url

    campus_env = env.get("ENV", env.get("CAMPUS_ENV", "development"))
    if env.get("DEPLOY", "").endswith(f".{service}") or campus_env == "testing":
        warnings.warn(
            f"HOSTNAME-derived {service} base URLs are deprecated and no "
            f"longer used; set {url_var} to configure the {service} base "
            "URL explicitly.",
            DeprecationWarning,
            stacklevel=3,
        )

    match campus_env:
        case "development" | "testing":
            return development_url
        case "staging":
            return f"https://{service}.campus.nyjc.dev"
        case "production":
            return f"https://{service}.campus.nyjc.app"
        case _:
            raise ValueError("Invalid ENV value")


class Campus:
    """Unified Campus client interface.

    Provides consistent access patterns across all Campus services.

    Modes:
    - mode="server" (default): For server-to-server communication (e.g., campus.api).
      Requires CLIENT_ID and CLIENT_SECRET environment variables.
    - mode="device": For public clients (e.g., CLI) that don't have secrets.
      No credentials required; only public OAuth endpoints are accessible.

    Service base URLs are resolved per service (auth, api) in this order:
    1. Explicit URL config: CAMPUS_AUTH_URL / CAMPUS_API_URL env vars.
    2. ENV/CAMPUS_ENV defaults: development (Railway), staging, production.

    See the API Reference for usage examples.
    """

    def __init__(self, timeout: int, mode: str = "server"):
        """Initialize unified Campus client with all service clients.

        Args:
            timeout: Request timeout in seconds.
            mode: Client mode - "server" (default) or "device".

        Raises:
            OSError: If mode="server" and CLIENT_ID or CLIENT_SECRET
                environment variables are not set.
        """
        self.timeout = timeout
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
            base_url = _resolve_base_url(
                "auth", "CAMPUS_AUTH_URL", AUTH_DEVELOPMENT_URL
            )
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
            base_url = _resolve_base_url(
                "api", "CAMPUS_API_URL", API_DEVELOPMENT_URL
            )
            self._api = ApiRoot(
                json_client=CampusRequest(
                    base_url=base_url,
                    timeout=self.timeout,
                    mode=self._mode,
                )
            )
        return self._api

    def _get_token_from_session(
            self,
            force_refresh=False,
            refresh_if_expired=True
    ) -> campus.model.OAuthToken:
        """Get the token from flask session."""
        # flask session stores a session id
        login_session = self.auth.logins.from_session()
        creds_resource = self.auth.credentials["campus"][login_session.user_id]
        user_creds = creds_resource.get()
        if (
                force_refresh
                or refresh_if_expired and user_creds.token.is_expired()
        ):
            token = self.auth.token(
                grant_type="refresh_token",
                refresh_token=user_creds.token.refresh_token
            )
            self.auth.credentials["campus"][login_session.user_id].update(
                token=token
            )
        return user_creds.token

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
    def with_user_session(self) -> Iterator["Campus"]:
        """Context manager yielding CampusRequest with user credentials.

        Usage:
            with campus.with_user_session() as client:
                # use client for requests

        Yields:
            CampusRequest: JSON client with user credentials set.
        """
        try:
            token = self._get_token_from_session()
            self.use_token(token)
            yield self
        except Exception:
            raise
        finally:
            self.revoke_session()
