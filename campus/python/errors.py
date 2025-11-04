"""campus.python.errors

Common error types used across Campus API for Python.
"""


from typing import Self


class APIError(Exception):
    """Base exception for all campus client errors."""
    _registered_errors: dict[int, type["APIError"]] = {}
    status_code: int
    error: str
    error_description: str | None
    error_uri: str | None

    def __init__(
            self,
            status_code: int | None = None,
            error_description: str | None = None,
            *,
            error_uri: str | None = None
    ):
        if status_code is not None:
            self.status_code = status_code
        if error_description:
            super().__init__(error_description)
        else:
            super().__init__()
        self.error_description = error_description

    def __init_subclass__(cls) -> None:
        cls._registered_errors[cls.status_code] = cls

    @classmethod
    def with_status_code(
            cls: type["APIError"],
            status_code: int,
            error_description: str | None = None,
    ) -> "APIError | None":
        """Create an APIError instance based on status code."""
        if status_code < 400:
            return None
        error_cls = cls._registered_errors.get(status_code, APIError)
        if error_cls is APIError:
            return error_cls(status_code, error_description)
        return error_cls(error_description=error_description)


class AuthenticationError(APIError):
    """Raised when client is unauthenticated or authentication fails."""
    status_code = 401
    error = "authentication_error"


class AccessDeniedError(APIError):
    """Raised when an authenticated client lacks required permissions."""
    status_code = 403
    error = "access_denied"


class ConflictError(APIError):
    """Raised when a conflict occurs."""
    status_code = 409
    error = "conflict_error"


class NotFoundError(APIError):
    """Raised when a requested resource is not found."""
    status_code = 404
    error = "not_found"


class BadRequestError(APIError):
    """Raised when request validation fails."""
    status_code = 400
    error = "invalid_request"


class MalformedResponseError(APIError):
    """Raised when the API response is malformed."""
    status_code = 502
    error = "malformed_response"


class NetworkError(APIError):
    """Raised when network communication fails."""
    status_code = 500
    error = "network_error"


class NotImplementedError(APIError):
    """Raised when the endpoint is not yet implemented."""
    status_code = 501
    error = "not_implemented"


class RateLimitExceededError(APIError):
    """Raised when rate limits are exceeded."""
    status_code = 429
    error = "too_many_requests"


class ServerError(APIError):
    """Raised when the server encounters an error."""
    status_code = 500
    error = "server_error"


class UnavailableError(APIError):
    """Raised when the service is unavailable."""
    status_code = 503
    error = "service_unavailable"
