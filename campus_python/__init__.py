"""campus.client.core

Unified Campus client interface providing consistent access to all services.
"""

__all__ = (
    "Campus",
    "errors",
)

import logging

from campus.common import env

from .api.v1 import ApiRoot
from .auth.v1 import AuthRoot
from .json_client import CampusClient
from . import errors

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Campus:
    """Unified Campus client interface.

    Provides consistent access patterns across all Campus services.
    Automatically loads credentials from CLIENT_ID and CLIENT_SECRET environment variables.

    See the API Reference for usage examples.
    """

    def __init__(self):
        """Initialize unified Campus client with all service clients.

        Credentials are automatically loaded from CLIENT_ID and CLIENT_SECRET
        environment variables. All service clients will be properly
        authenticated if these environment variables are set.

        Args:
            override: Optional mapping of app names to JSON clients.
            raw: If True, methods return JsonResponse objects.
                 If False (default), methods call raise_for_status() and return JSON data.
        """

    @property
    def auth(self) -> AuthRoot:
        """Get the auth service resource."""
        if not hasattr(self, "_auth"):
            # Use relative URL if in deployed auth service
            if env.get("DEPLOY") and env.DEPLOY.endswith(".auth"):
                base_url = ""
            else:
                match env.get("ENV", env.get("CAMPUS_ENV", "development")):
                    case "development":
                        base_url = "https://campusauth-development.up.railway.app"
                    case "staging":
                        base_url = "https://auth.campus.nyjc.dev"
                    case "production":
                        base_url = "https://auth.campus.nyjc.app"
                    case _:
                        raise ValueError("Invalid ENV value")
            self._auth = AuthRoot(
                json_client=CampusClient(base_url=base_url)
            )
        return self._auth

    @property
    def api(self) -> ApiRoot:
        """Get the api service resource."""
        if not hasattr(self, "_api"):
            if env.get("DEPLOY") and env.DEPLOY.endswith(".auth"):
                base_url = ""
            else:
                match env.get("ENV", env.get("CAMPUS_ENV", "development")):
                    case "development":
                        base_url = "https://campusapi-development.up.railway.app"
                    case "staging":
                        base_url = "https://api.campus.nyjc.dev"
                    case "production":
                        base_url = "https://api.campus.nyjc.app"
                    case _:
                        raise ValueError("Invalid ENV value")
            self._api = ApiRoot(
                json_client=CampusClient(base_url=base_url)
            )
        return self._api
