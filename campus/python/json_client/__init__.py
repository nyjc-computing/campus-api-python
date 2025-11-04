"""campus.python.json_client

JSON client wrapper for Campus services.
"""

__all__ = [
    "JsonClient",
    "JsonResponse",
    "CampusClient",
    "get_client",
]

from typing import Any, Iterable, Mapping, MutableMapping, Self
import requests

from .interface import JsonClient, JsonDict, JsonResponse
from .. import errors


class CampusResponse(JsonResponse):
    """Wrapper around requests.Response to satisfy JsonResponse protocol.

    Implements the small subset of behaviour expected by the project's
    `JsonResponse` protocol (status_code, headers, text, json, ok, and
    raise_for_status mapping to project-specific errors).
    """

    def __init__(self, response: requests.Response):
        self._response = response

    @property
    def status_code(self) -> int:
        return self._response.status_code

    @property
    def headers(self) -> dict[str, str]:
        return dict(self._response.headers)

    @property
    def text(self) -> str:
        return self._response.text

    def json(self) -> Any:
        try:
            return self._response.json()
        except ValueError as exc:  # JSON decoding error
            raise errors.MalformedResponseError(
                error_description="Response is not valid JSON"
            ) from None

    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def is_client_error(self) -> bool:
        return 400 <= self.status_code < 500

    def is_server_error(self) -> bool:
        return 500 <= self.status_code < 600


class CampusClient(JsonClient):
    """Campus JSON client with default configuration.

    This client is pre-configured to handle JSON requests and responses.
    It provides convenience methods for common HTTP methods with JSON payloads.
    """

    def __init__(
            self,
            base_url: str | None,
            *,
            auth: Iterable[str] | str | None = None,
            headers: MutableMapping[str, str] | None = None,
            **kwargs: Any,
    ):
        self.base_url = base_url
        self._headers = dict(headers or {})
        # allow optional default timeout via kwargs
        self._timeout = kwargs.get("timeout", 10)

        match auth:
            case str():  # token
                self._headers["Authorization"] = "Bearer " + auth
            case (client_id, client_secret):
                # Keep the same behaviour as originally present; if encoding is
                # desired callers can pass a pre-built header instead.
                self._headers["Authorization"] = (
                    f"Basic {client_id}:{client_secret}"
                )
            case None:
                pass

        # Session to persist headers and connection pooling
        self._session = requests.Session()
        self._session.headers.update(self._headers)

    def _build_url(self, path: str) -> str:
        if not self.base_url:
            return path
        if self.base_url.endswith("/") and path.startswith("/"):
            return self.base_url[:-1] + path
        if not self.base_url.endswith("/") and not path.startswith("/"):
            return self.base_url + "/" + path
        return self.base_url + path

    def get(self: Self, path: str, query: JsonDict | None = None) -> JsonResponse:
        """Sends a GET request."""
        url = self._build_url(path)
        try:
            if query:
                resp = self._session.get(
                    url,
                    params=query,
                    timeout=self._timeout
                )
            else:
                resp = self._session.get(url, timeout=self._timeout)
        except requests.RequestException as exc:
            raise errors.NetworkError(error_description=str(exc)) from None
        return CampusResponse(resp)

    def post(self: Self, path: str, json: JsonDict | None = None) -> JsonResponse:
        """Sends a POST request."""
        url = self._build_url(path)
        try:
            resp = self._session.post(url, json=json, timeout=self._timeout)
        except requests.RequestException as exc:
            raise errors.NetworkError(error_description=str(exc)) from None
        return CampusResponse(resp)

    def put(self: Self, path: str, json: JsonDict | None = None) -> JsonResponse:
        """Sends a PUT request."""
        url = self._build_url(path)
        try:
            resp = self._session.put(url, json=json, timeout=self._timeout)
        except requests.RequestException as exc:
            raise errors.NetworkError(error_description=str(exc)) from None
        return CampusResponse(resp)

    def delete(self: Self, path: str, json: JsonDict | None = None) -> JsonResponse:
        """Sends a DELETE request."""
        url = self._build_url(path)
        try:
            resp = self._session.delete(url, json=json, timeout=self._timeout)
        except requests.RequestException as exc:
            raise errors.NetworkError(error_description=str(exc)) from None
        return CampusResponse(resp)

    def patch(self: Self, path: str, json: Any = None) -> JsonResponse:
        """Sends a PATCH request."""
        url = self._build_url(path)
        try:
            resp = self._session.patch(url, json=json, timeout=self._timeout)
        except requests.RequestException as exc:
            raise errors.NetworkError(error_description=str(exc)) from None
        return CampusResponse(resp)


def get_client(
        base_url: str | None = None,
        *,
        auth: Iterable[str] | str | None = None,
        headers: Mapping[str, str] | None = None,
        **kwargs: Any
) -> CampusClient:
    """Create a new CampusClient instance with default configuration.

    Returns:
        CampusClient: A new CampusClient instance.
    """
    # ensure headers is a mutable mapping (dict) to match CampusClient signature
    return CampusClient(base_url, auth=auth, headers=dict(headers) if headers is not None else None, **kwargs)
