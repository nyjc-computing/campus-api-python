"""campus.client.interface

Interface descriptions for the Campus client interface.

This interface is designed to:
- wrap `flask.testing.FlaskClient`
- wrap most common client interfaces e.g. `requests`
- provide a common Response interface that wraps `werkzeug.test.TestResponse,
  `requests.Response`, etc
- so aa to enable WSGI hooks or unit testing with a local WSGI app.
"""

from typing import Any, Optional

from .json_client import JsonClient, JsonDict, JsonResponse


class ResourceRoot:
    """Root of all resources.

    This class is used to group all top-level resources together.
    """
    _client: Optional[JsonClient] = None
    base_url: str
    url_prefix: str

    def __init__(self, json_client: Optional[JsonClient] = None):
        self._client = json_client
    
    @property
    def client(self) -> JsonClient:
        """Get the JsonClient associated with this resource root."""
        if not self._client:
            raise AttributeError(
                f"No client defined for {self}"
            )
        return self._client

    def make_url(self) -> str:
        """Create a full path for the resource root."""
        return f"{self.base_url}/{self.url_prefix.lstrip('/')}"


class ResourceCollection:
    """Collection of resources.

    This class is used to group related resources together.
    """
    _client: Optional[JsonClient] = None
    path: str
    root: ResourceRoot

    def __init__(
            self,
            client: Optional[JsonClient] = None,
            *,
            root: ResourceRoot
    ):
        self._client = client
        self.root = root

    @property
    def client(self) -> JsonClient:
        """Get the JsonClient associated with this resource."""
        if self._client:
            return self._client
        if self.root.client:
            return self.root.client
        raise AttributeError(f"No client defined for {self}")

    def make_path(self, path: str | None = None) -> str:
        """Create a full path for a sub-resource or action."""
        if path:
            return f"{self.root.make_url()}/{self.path}/{path.lstrip('/')}"
        return f"{self.root.make_url()}/{self.path}"


class Resource:
    """Resource class that represents API resources

    The resource class uses a JsonClient instance to handle all API requests.
    It only tracks the path of the current resource.
    """
    _client: Optional[JsonClient] = None
    parent: "Resource | ResourceCollection"
    path: str

    def __init__(
            self,
            *parts: str,
            parent: "Resource | ResourceCollection",
            client: Optional[JsonClient] = None,
    ):
        self._client = client
        self.parent = parent
        self.path = f"{parent.path if parent else ''}/{'/'.join(parts)}"

    def __repr__(self) -> str:
        return f"Resource(client={self.client}, path={self.path})"

    def __str__(self) -> str:
        return self.path

    @property
    def client(self) -> JsonClient:
        """Get the JsonClient associated with this resource."""
        if self._client:
            return self._client
        if self.parent and self.parent.client:
            return self.parent.client
        raise AttributeError(f"No client defined for {self}")

    def _process_response(self, response: JsonResponse) -> JsonResponse | Any:
        """Process response based on raw setting.

        If raw=True, returns JsonResponse directly.
        If raw=False, calls raise_for_status() then returns response.json().
        """
        response.raise_for_status()
        return response.json()

    def make_path(self, path: str| None = None) -> str:
        """Create a full path for a sub-resource or action."""
        if path:
            return f"{self.path}/{path.lstrip('/')}"
        return self.path
