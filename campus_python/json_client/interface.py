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
        # Try to provide the same mapping as the interface's raise_for_status
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
            # Attach some helpful notes if the APIError implementation supports it
            try:
                error.add_note(f"Headers: {self.headers}")
                error.add_note(f"Body: {body}")
            except Exception:
                # add_note may not exist; ignore if it doesn't
                pass
            raise error from None


class JsonClient(ABC):
    """This class describes the public interface required from Client classes,
    which are used to send JSON requests.
    """
    base_url: str | None
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
    def get(self: Self, path: str, query: JsonDict | None = None) -> JsonResponse:
        """Sends a GET request."""

    @abstractmethod
    def post(self: Self, path: str, json: JsonDict | None = None) -> JsonResponse:
        """Sends a POST request."""

    @abstractmethod
    def put(self: Self, path: str, json: JsonDict | None = None) -> JsonResponse:
        """Sends a PUT request."""

    @abstractmethod
    def delete(self: Self, path: str, json: JsonDict | None = None) -> JsonResponse:
        """Sends a DELETE request."""

    @abstractmethod
    def patch(self: Self, path: str, json: Any = None) -> JsonResponse:
        """Sends a PATCH request."""
