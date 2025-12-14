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

# Use char constant to avoid quoting-related syntax errors
SLASH = "/"


class ResourceRoot:
    """Root of all resources.

    This class is used to group all top-level resources together.
    """
    _client: Optional[JsonClient] = None
    url_prefix: str

    def __init__(self, json_client: Optional[JsonClient] = None):
        self._client = json_client

    @property
    def base_url(self) -> str:
        """Get the base URL for this resource root."""
        if not self._client:
            raise AttributeError("No client defined")
        return self._client.base_url

    @property
    def client(self) -> JsonClient:
        """Get the JsonClient associated with this resource root."""
        if not self._client:
            raise AttributeError(
                f"No client defined for {self}"
            )
        return self._client

    def make_path(self, part: str | None = None) -> str:
        """Create a full path for the resource root or a sub-resource.

        Args:
            part (str | None): Optional sub-resource or action path.
        Returns:
            str: Full path for the resource root or sub-resource.
        """
        if part:
            return f"/{self.url_prefix.lstrip(SLASH)}/{part.lstrip(SLASH)}"
        else:
            return f"/{self.url_prefix.lstrip(SLASH)}"

    def make_url(self) -> str:
        """Create a full path for the resource root."""
        return f"{self.base_url}/{self.url_prefix.lstrip(SLASH)}"


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

    def make_path(self, part: str | None = None) -> str:
        """Create a full path for a sub-resource or action."""
        if part:
            return (
                f"/{self.root.make_path(self.path).lstrip(SLASH).rstrip(SLASH)}"
                f"/{part.lstrip(SLASH)}"
            )
        else:
            return f"/{self.root.make_path(self.path).lstrip(SLASH)}"

    def make_url(self, part: str | None = None) -> str:
        """Create a full URL for a sub-resource or action."""
        return f"{self.root.make_url()}{self.make_path(part)}"


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
        self.path = parent.make_path(SLASH.join(parts))

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

    def make_path(self, part: str | None = None, trailing_slash=False) -> str:
        """Create a full path for a sub-resource or action."""
        full_path = "/" + f"{self.path.strip(SLASH)}"
        if part:
            full_path = f"{full_path}/{part.strip(SLASH)}"
        if trailing_slash and not full_path.endswith(SLASH):
            full_path += SLASH
        return full_path

    def make_url(self, part: str | None = None) -> str:
        """Create a full URL for a sub-resource or action."""
        return f"{self.parent.make_url()}{self.make_path(part)}"
