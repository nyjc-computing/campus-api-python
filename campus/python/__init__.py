"""campus.client.core

Unified Campus client interface providing consistent access to all services.
"""

import logging

from campus.common import env
from .api.v1 import ApiRoot
from .auth.v1 import AuthRoot

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
            self._auth = AuthRoot()
        return self._auth

    @property
    def api(self) -> ApiRoot:
        """Get the api service resource."""
        if not hasattr(self, "_api"):
            self._api = ApiRoot()
        return self._api
