"""campus.python.json_client.interface

Interface descriptions for the Campus client interface.

This interface is designed to:
- wrap `flask.testing.FlaskClient`
- wrap most common client interfaces e.g. `requests`
- provide a common Response interface that wraps `werkzeug.test.TestResponse,
  `requests.Response`, etc
- so aa to enable WSGI hooks or unit testing with a local WSGI app.
"""

__all__ = [
    "JsonClient",
    "JsonResponse",
]

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, Iterable, Protocol, Self, runtime_checkable

from .. import errors

Header = Mapping[str, str]
JsonDict = dict[str, Any]


class JsonResponse(ABC):
    """This class describes the public interface required from Response
    wrappers for JSON responses.
    """
    # pylint: disable=unnecessary-ellipsis

    @abstractmethod
    def __init__(self): ...

    @property
    @abstractmethod
    def status_code(self) -> int:
        """HTTP status code of the response."""
        ...

    @property
    @abstractmethod
    def headers(self) -> dict[str, str]:
        """Returns headers of the response as a dict."""
        ...

    @property
    @abstractmethod
    def text(self) -> str:
        """Returns the response body as a string."""
        ...

    @property
    @abstractmethod
    def content(self) -> bytes:
        """Returns the response body as bytes, undecoded.

        File content (campus.api /files) is binary: callers decode,
        never this property.
        """
        ...

    @abstractmethod
    def json(self) -> Any:
        """Returns the response body as JSON."""
        ...

    def ok(self) -> bool:
        """Returns True if the response status code is 2xx, False otherwise."""
        return 200 <= self.status_code < 300

    def is_client_error(self) -> bool:
        """Returns True if the response status code is 4xx, False otherwise."""
        return 400 <= self.status_code < 500

    def is_server_error(self) -> bool:
        """Returns True if the response status code is 5xx, False otherwise."""
        return 500 <= self.status_code < 600

    def raise_for_status(self) -> None:
        """Raise the mapped APIError subclass on a 4xx/5xx status.

        Parses the Campus error envelope (and the legacy error_code
        form) into the registered error class for the status code;
        OAuth errors are recovered from AUTH_* codes when the server
        strips envelope details. Response headers and body ride along
        as error notes.
        """
        if not (self.is_client_error() or self.is_server_error()):
            return

        status_code = self.status_code

        # Try to extract a useful message/body
        try:
            response_data = self.json()
        except Exception:
            response_data = None

        try:
            body = response_data if response_data is not None else self.text
        except Exception:
            body = f"HTTP {status_code}"

        error = errors.APIError.with_status_code(status_code, response_data)
        if error:
            # Attach notes for debugging (headers, body)
            # Try the notes attribute first (new APIError)
            try:
                error.notes = {"headers": dict(self.headers), "body": body}
            except AttributeError:
                # Fall back to add_note for older implementations
                try:
                    error.add_note(f"Headers: {self.headers}")
                    error.add_note(f"Body: {body}")
                except Exception:
                    # add_note may not exist; ignore if it doesn't
                    pass
            raise error from None


class JsonClient(ABC):
    """This class describes the public interface required from Client
    classes, which are used to send JSON requests.

    Optional capability, not part of this abstract interface: concrete
    clients may support a 401 auto-refresh hook
    (CampusRequest.set_unauthorized_hook, issue #89) that refreshes the
    bearer token and retries a request once when it comes back 401.
    Callers must feature-detect (hasattr) rather than assume it.
    """
    base_url: str
    # pylint: disable=unnecessary-ellipsis

    @abstractmethod
    def __init__(
            self,
            base_url: str | None = None,
            *,
            auth: Iterable[str] | str | None = None,
            headers: Mapping[str, str] | None = None,
            **kwargs: Any
    ): ...

    @abstractmethod
    def reset_authorization(self) -> None:
        """Reset authorization back to client credentials from env."""

    @property
    @abstractmethod
    def authorization(self) -> str | None:
        """The current Authorization header value, or None when unset."""

    @abstractmethod
    def set_basic_authorization(self, client_id: str, secret: str) -> None:
        """Set Basic Authorization header using a pre-encoded token.

        Args:
            client_id (str): Client ID.
            secret (str): Client Secret.
        """

    @abstractmethod
    def set_bearer_authorization(self, token: str) -> None:
        """Set Bearer Authorization header.

        Args:
            token (str): Bearer token.
        """

    def set_default_header(self, name: str, value: str) -> None:
        """Set a default header sent with every request (#837).

        Optional capability: the ABC default refuses, so callers can
        detect a client that cannot carry default headers instead of
        silently dropping them. Implementations should set the header
        on their underlying transport (e.g. the requests session).
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support default headers"
        )

    @abstractmethod
    def get(self: Self, path: str, query: JsonDict | None = None) -> JsonResponse:
        """Sends a GET request."""

    @abstractmethod
    def post(self: Self, path: str, json: JsonDict | None = None) -> JsonResponse:
        """Sends a POST request."""

    @abstractmethod
    def put(
            self: Self,
            path: str,
            json: JsonDict | None = None,
            query: JsonDict | None = None
    ) -> JsonResponse:
        """Sends a PUT request."""

    @abstractmethod
    def put_data(
            self: Self,
            path: str,
            data: bytes | str,
            content_type: str | None = None,
            query: JsonDict | None = None
    ) -> JsonResponse:
        """Sends a PUT request with a raw (non-JSON) body.

        The body is sent verbatim, with no JSON encoding; the
        Content-Type header is caller-controlled. Used by file
        uploads (campus.api /files by-slug), which carry raw bytes
        with an explicit Content-Type. `query` carries URL query
        parameters (e.g. the files upsert's optional display name).
        """

    @abstractmethod
    def delete(
            self: Self,
            path: str,
            json: JsonDict | None = None,
            query: JsonDict | None = None
    ) -> JsonResponse:
        """Sends a DELETE request."""

    @abstractmethod
    def patch(
            self: Self,
            path: str,
            json: Any = None,
            query: JsonDict | None = None
    ) -> JsonResponse:
        """Sends a PATCH request."""
