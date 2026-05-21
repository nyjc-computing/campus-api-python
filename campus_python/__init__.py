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
from campus.common import env

from . import errors
from .api.v1 import ApiRoot
from .auth.v1 import AuthRoot
from .json_client import CampusRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Campus:
    """Unified Campus client interface.

    Provides consistent access patterns across all Campus services.

    Modes:
    - mode="server" (default): For server-to-server communication (e.g., campus.api).
      Requires CLIENT_ID and CLIENT_SECRET environment variables.
    - mode="device": For public clients (e.g., CLI) that don't have secrets.
      No credentials required; only public OAuth endpoints are accessible.

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
            # Use relative URL if in deployed auth service
            if env.get("DEPLOY") and env.DEPLOY.endswith(".auth"):
                base_url = f"https://{env.HOSTNAME}"
            else:
                match env.get("ENV", env.get("CAMPUS_ENV", "development")):
                    case "development":
                        base_url = "https://campusauth-development.up.railway.app"
                    case "testing":
                        base_url = f"https://{env.HOSTNAME}"
                    case "staging":
                        base_url = "https://auth.campus.nyjc.dev"
                    case "production":
                        base_url = "https://auth.campus.nyjc.app"
                    case _:
                        raise ValueError("Invalid ENV value")
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
            if env.get("DEPLOY") and env.DEPLOY.endswith(".api"):
                base_url = f"https://{env.HOSTNAME}"
            else:
                match env.get("ENV", env.get("CAMPUS_ENV", "development")):
                    case "development":
                        base_url = "https://campusapi-development.up.railway.app"
                    case "testing":
                        base_url = f"https://{env.HOSTNAME}"
                    case "staging":
                        base_url = "https://api.campus.nyjc.dev"
                    case "production":
                        base_url = "https://api.campus.nyjc.app"
                    case _:
                        raise ValueError("Invalid ENV value")
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
