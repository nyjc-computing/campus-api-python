"""campus.python.json_client

JSON client wrapper for Campus services.
"""

__all__ = [
    "JsonClient",
    "JsonResponse",
    "CampusRequest",
]

import base64
from typing import Any, Mapping, Self, cast

import campus.model
import requests
from campus.common import env

from .. import errors
from .interface import JsonClient, JsonDict, JsonResponse


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


class CampusRequest(JsonClient):
    """Campus JSON client

    This client is pre-configured to handle JSON requests and responses.
    It provides convenience methods for common HTTP methods with JSON
    payloads.

    Note that the client requires authorization before it can make
    requests. Use CampusRequest.set_basic_authorization(),
    CampusRequest.set_bearer_authorization(), or
    CampusRequest.for_user() to authorize the client, and
    CampusRequest.reset_authorization() to reset to client credentials
    """

    def __init__(
            self,
            base_url: str | None,
            *,
            mode: str = "server",
            headers: Mapping[str, str] | None = None,
            **kwargs: Any,
    ):
        self.base_url = base_url or ""
        self._headers = dict(headers or {})
        # allow optional default timeout via kwargs
        self._timeout = kwargs.get("timeout", 10)
        # Session to persist headers and connection pooling
        self._session = requests.Session()
        self._session.headers.update(self._headers)
        # Only set client credentials in server mode
        # Device mode starts without auth (Bearer token will be set later)
        if mode == "server":
            self.reset_authorization()

    @property
    def headers(self) -> campus.model.HttpHeader:
        """Get the currently configured headers."""
        headers = cast(Mapping[str, str], self._session.headers)
        return campus.model.HttpHeader.from_header(headers)

    def _build_url(self, path: str) -> str:
        if not self.base_url:  # relative URL
            return f"http://localhost:{env.get('PORT', '8080')}" + path
        if self.base_url.endswith("/") and path.startswith("/"):
            return self.base_url[:-1] + path
        if not self.base_url.endswith("/") and not path.startswith("/"):
            return self.base_url + "/" + path
        return self.base_url + path

    def reset_authorization(self) -> None:
        """Reset authorization back to client credentials from env."""
        env.require("CLIENT_ID", "CLIENT_SECRET")
        self.set_basic_authorization(
            client_id=env.CLIENT_ID,
            secret=env.CLIENT_SECRET
        )

    def set_basic_authorization(self, client_id: str, secret: str) -> None:
        """Set Basic Authorization header using a pre-encoded token.

        Args:
            client_id (str): Client ID.
            secret (str): Client Secret.
        """
        credentials = f"{client_id}:{secret}"
        # Encode credentials in base64 following RFC 7617
        encoded_credentials = base64.b64encode(
            credentials.encode('utf-8')
        ).decode('ascii')
        self._session.headers["Authorization"] = "Basic " + encoded_credentials

    def set_bearer_authorization(self, token: str) -> None:
        """Set Bearer Authorization header.

        Args:
            token (str): Bearer token.
        """
        self._session.headers["Authorization"] = "Bearer " + token

    def get(
            self: Self,
            path: str,
            query: JsonDict | None = None
    ) -> JsonResponse:
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
            raise errors.ServerError(error_description=str(exc)) from None
        return CampusResponse(resp)

    def post(self: Self, path: str, json: JsonDict | None = None) -> JsonResponse:
        """Sends a POST request."""
        url = self._build_url(path)
        try:
            resp = self._session.post(url, json=json, timeout=self._timeout)
        except requests.RequestException as exc:
            raise errors.ServerError(error_description=str(exc)) from None
        return CampusResponse(resp)

    def put(self: Self, path: str, json: JsonDict | None = None) -> JsonResponse:
        """Sends a PUT request."""
        url = self._build_url(path)
        try:
            resp = self._session.put(url, json=json, timeout=self._timeout)
        except requests.RequestException as exc:
            raise errors.ServerError(error_description=str(exc)) from None
        return CampusResponse(resp)

    def delete(self: Self, path: str, json: JsonDict | None = None) -> JsonResponse:
        """Sends a DELETE request."""
        url = self._build_url(path)
        try:
            resp = self._session.delete(url, json=json, timeout=self._timeout)
        except requests.RequestException as exc:
            raise errors.ServerError(error_description=str(exc)) from None
        return CampusResponse(resp)

    def patch(self: Self, path: str, json: Any = None) -> JsonResponse:
        """Sends a PATCH request."""
        url = self._build_url(path)
        try:
            resp = self._session.patch(url, json=json, timeout=self._timeout)
        except requests.RequestException as exc:
            raise errors.ServerError(error_description=str(exc)) from None
        return CampusResponse(resp)
