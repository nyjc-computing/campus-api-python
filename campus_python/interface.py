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

from .json_client import JsonClient, JsonDict

# Use char constant to avoid quoting-related syntax errors
SLASH = "/"


class Transport:
    """Shared HTTP verb helpers for classes backed by a JsonClient.

    ResourceRoot, ResourceCollection and Resource mix this in; `client`
    is provided by the host class. Each helper sends one verb via
    self.client, raises an APIError on a 4xx/5xx status (via
    JsonResponse.raise_for_status), and returns the response body
    parsed as JSON. Endpoint methods keep envelope keys and model
    hydration inline so each one reads start to finish; methods that
    must inspect the raw response first (e.g. to map a 404 to KeyError
    or observe rate-limit headers) call self.client directly instead.
    """

    @property
    def client(self) -> JsonClient:
        """The JsonClient used to send requests; provided by host classes."""
        raise AttributeError("No client defined for transport")

    def _get_json(self, path: str, query: JsonDict | None = None) -> Any:
        """GET path and return the parsed JSON body."""
        if query is None:
            response = self.client.get(path)
        else:
            response = self.client.get(path, query=query)
        response.raise_for_status()
        return response.json()

    def _post_json(self, path: str, json: JsonDict | None = None) -> Any:
        """POST the JSON body and return the parsed JSON response body."""
        if json is None:
            response = self.client.post(path)
        else:
            response = self.client.post(path, json=json)
        response.raise_for_status()
        return response.json()

    def _put_json(
            self,
            path: str,
            json: JsonDict,
            query: JsonDict | None = None
    ) -> Any:
        """PUT the JSON body (with optional query params) and return the
        parsed JSON response body."""
        if query is None:
            response = self.client.put(path, json=json)
        else:
            response = self.client.put(path, json=json, query=query)
        response.raise_for_status()
        return response.json()

    def _patch_json(
            self,
            path: str,
            json: Any,
            query: JsonDict | None = None
    ) -> Any:
        """PATCH the JSON body (with optional query params) and return
        the parsed JSON response body."""
        if query is None:
            response = self.client.patch(path, json=json)
        else:
            response = self.client.patch(path, json=json, query=query)
        response.raise_for_status()
        return response.json()

    def _delete_json(
            self,
            path: str,
            json: JsonDict | None = None,
            query: JsonDict | None = None
    ) -> Any:
        """DELETE (optionally with a JSON body and/or query params) and
        return the parsed JSON response body."""
        kwargs: JsonDict = {}
        if json is not None:
            kwargs["json"] = json
        if query is not None:
            kwargs["query"] = query
        response = self.client.delete(path, **kwargs)
        response.raise_for_status()
        return response.json()


class ResourceRoot(Transport):
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


class ResourceCollection(Transport):
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

    def make_path(self, part: str | None = None, end_slash: bool = True) -> str:
        """Create a full path for a resource collection.

        Args:
            part: Optional sub-resource or action path.
            end_slash: Whether to add a trailing slash (default: True for collections).

        Returns:
            Full path for the resource collection or sub-resource.
        """
        if part:
            base = f"/{self.root.make_path(self.path).strip(SLASH)}/{part.strip(SLASH)}"
            return f"{base}/" if end_slash else base
        else:
            return f"/{self.root.make_path(self.path).strip(SLASH)}/"

    def make_url(self, part: str | None = None) -> str:
        """Create a full URL for a sub-resource or action."""
        return f"{self.root.make_url()}{self.make_path(part)}"


class Resource(Transport):
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

    def make_path(self, part: str | None = None, end_slash=False) -> str:
        """Create a full path for a sub-resource or action."""
        if part:
            full_path = (
                f"/{self.path.strip(SLASH)}"
                f"/{part.strip(SLASH)}"
                f"{SLASH if end_slash else ''}"
            )
        else:
            full_path = f"/{self.path.lstrip(SLASH)}"
        if end_slash and not full_path.endswith(SLASH):
            full_path += SLASH
        return full_path

    def make_url(self, part: str | None = None) -> str:
        """Create a full URL for a sub-resource or action."""
        return f"{self.parent.make_url()}{self.make_path(part)}"
