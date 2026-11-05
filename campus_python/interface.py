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


def join_path(*parts: str) -> str:
    """Join path parts into a single absolute path.

    Leading/trailing slashes are stripped from each part (inner
    slashes survive — by-slug path tails rely on them), the parts are
    joined with single slashes, and the result gets one leading slash.
    """
    cleaned = [part.strip(SLASH) for part in parts]
    return SLASH + SLASH.join(part for part in cleaned if part)


def payload(**fields: Any) -> dict[str, Any]:
    """Build a JSON request body from keyword fields.

    Fields set to None are omitted — the "not provided" convention
    across Campus write routes (an omitted field is left unchanged
    upstream). Fields that ARE provided are sent verbatim, including
    falsy ones (0, "", False).

    Not for bodies that must carry an explicit null: build those by
    hand (e.g. submissions.unsubmit's {"submitted_at": null}).
    """
    return {key: value for key, value in fields.items() if value is not None}


def updates(**fields: Any) -> dict[str, Any]:
    """Build a PATCH body from keyword fields, dropping None fields.

    Raises ValueError when every field is None — Campus PATCH routes
    reject an empty body outright.

    The same explicit-null caveat as payload applies: a PATCH that
    must set a field to null cannot go through here.
    """
    body = payload(**fields)
    if not body:
        raise ValueError("At least one field must be provided for update")
    return body


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

        Only leading slashes are trimmed here: a url_prefix that
        intentionally ends with a slash (e.g. /integrations/v1/) keeps
        it, and a part with an inner path tail (e.g. broker's
        "google/classroom") is preserved verbatim.

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

        Collection routes carry a trailing slash by default (the
        upstream API schema); item ids, sub-resources and action parts
        append after the collection segment.

        Args:
            part: Optional sub-resource or action path.
            end_slash: Whether to add a trailing slash.

        Returns:
            Full path for the resource collection or sub-resource.
        """
        if part:
            path = join_path(self.root.make_path(self.path), part)
        else:
            path = join_path(self.root.make_path(self.path))
        if end_slash and not path.endswith(SLASH):
            path += SLASH
        return path

    def make_url(self, part: str | None = None) -> str:
        """Create a full URL for the collection or a sub-resource."""
        return f"{self.client.base_url}{self.make_path(part)}"


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
        """Create a full path for a sub-resource or action.

        Item paths built from a parent collection carry the
        collection's trailing slash; dead-end sub-resource and action
        parts append after the item segment without one by default.
        With no part, the instance path is returned as constructed —
        only a leading slash is trimmed, so an item's trailing slash
        survives.
        """
        if part:
            path = join_path(self.path, part)
        else:
            path = SLASH + self.path.lstrip(SLASH)
        if end_slash and not path.endswith(SLASH):
            path += SLASH
        return path

    def make_url(self, part: str | None = None) -> str:
        """Create a full URL for this resource or a sub-resource."""
        return f"{self.client.base_url}{self.make_path(part)}"
