"""campus.python.errors

Common error types used across Campus API for Python.

Reference:
- campus/api/docs/api-error-spec.md
- campus/auth/docs/auth-error-spec.md
"""

from dataclasses import dataclass, field
from typing import Any, Self


@dataclass
class FieldError:
    """A single field validation error.

    Attributes:
        field: The field name that failed validation
        code: Machine-readable error code (e.g., "INVALID_FORMAT", "MISSING")
        message: Human-readable error message
    """
    field: str
    code: str
    message: str


class APIError(Exception):
    """Base exception for all campus client errors.

    Attributes:
        status_code: HTTP status code
        error: Error code (e.g., "NOT_FOUND", "VALIDATION_FAILED")
        error_description: Human-readable error message
        error_uri: Optional URI to error documentation
        request_id: Request identifier for tracing (from error envelope)
        details: Additional error details from server
        errors: Field-level validation errors (for ValidationError)
        notes: Client-side metadata (headers, body)
    """
    _registered_errors: dict[int, type["APIError"]] = {}
    status_code: int
    error: str
    error_description: str | None
    error_uri: str | None
    request_id: str | None
    details: dict[str, Any]
    errors: list[FieldError] | None
    notes: dict[str, Any] | None

    def __init__(
            self,
            status_code: int | None = None,
            error_description: str | None = None,
            *,
            error_uri: str | None = None,
            request_id: str | None = None,
            details: dict[str, Any] | None = None,
            errors: list[FieldError] | None = None,
            notes: dict[str, Any] | None = None
    ):
        if status_code is not None:
            self.status_code = status_code
        if error_description:
            super().__init__(error_description)
        else:
            super().__init__()
        self.error_description = error_description
        self.error_uri = error_uri
        self.request_id = request_id
        self.details = details or {}
        self.errors = errors
        self.notes = notes

    @property
    def oauth_error(self) -> str | None:
        """Get the OAuth protocol error string from details.

        Returns the OAuth error string (e.g., "invalid_client", "invalid_grant")
        if present in the error details. Used for auth endpoint errors.

        Reference: campus/auth/docs/auth-error-spec.md
        """
        return self.details.get("oauth_error") if self.details else None

    @property
    def oauth_error_description(self) -> str | None:
        """Get the OAuth error description from details.

        Returns the OAuth-specific error description if present.
        """
        return self.details.get("oauth_error_description") if self.details else None

    def __init_subclass__(cls) -> None:
        cls._registered_errors[cls.status_code] = cls

    @classmethod
    def with_status_code(
            cls: type["APIError"],
            status_code: int,
            response_data: dict[str, Any] | str | None = None,
            *,
            error: str | None = None,
            error_description: str | None = None,
            error_uri: str | None = None,
            request_id: str | None = None,
            details: dict[str, Any] | None = None,
            errors: list[FieldError] | None = None,
    ) -> "APIError | None":
        """Create an APIError instance based on status code.

        Handles both the new error envelope format and legacy format.

        Args:
            status_code: HTTP status code
            response_data: Full response data (dict or string) for parsing
            error: Explicit error code (overrides parsed value)
            error_description: Explicit error description (overrides parsed value)
            error_uri: Optional URI to error documentation
            request_id: Request identifier for tracing
            details: Additional error details
            errors: Field-level validation errors

        Returns:
            An APIError subclass instance or None if status_code < 400
        """
        if status_code < 400:
            return None

        # Determine error code and description from response data if not explicitly provided
        if isinstance(response_data, dict):
            # Try new error envelope format first
            if "error" in response_data and isinstance(response_data["error"], dict):
                error_obj = response_data["error"]
                error = error or error_obj.get("code")
                error_description = error_description or error_obj.get("message")
                request_id = request_id or error_obj.get("request_id")
                details = details or error_obj.get("details")

                # Parse field-level errors for validation errors
                if "errors" in error_obj and isinstance(error_obj["errors"], list):
                    errors = errors or [
                        FieldError(
                            field=e.get("field", ""),
                            code=e.get("code", ""),
                            message=e.get("message", "")
                        )
                        for e in error_obj["errors"]
                        if isinstance(e, dict)
                    ]
            # Fallback to legacy format (error_code at root level)
            elif "error_code" in response_data:
                error = error or response_data.get("error_code")
                error_description = error_description or response_data.get("message")
                details = details or response_data.get("details")

        # If response_data is a string, use it as error_description
        elif isinstance(response_data, str):
            error_description = error_description or response_data

        # Get the registered error class for this status code
        error_cls = cls._registered_errors.get(status_code, APIError)

        # For 422, use ValidationError if available
        if status_code == 422:
            error_cls = cls._registered_errors.get(422, ValidationError)

        # Create the error instance
        # All subclasses inherit from APIError and should accept its parameters
        # but if they override __init__ differently, we handle that
        try:
            instance = error_cls(
                status_code=status_code,
                error_description=error_description,
                error_uri=error_uri,
                request_id=request_id,
                details=details,
                errors=errors,
                notes=None
            )
        except TypeError:
            # Subclass has a different __init__ signature
            # Create with basic signature and set attributes manually
            instance = error_cls(error_description=error_description)
            # Manually set the new attributes if the subclass doesn't support them
            if not hasattr(instance, 'request_id'):
                instance.request_id = request_id
            if not hasattr(instance, 'details'):
                instance.details = details or {}
            if not hasattr(instance, 'errors'):
                instance.errors = errors
            if not hasattr(instance, 'notes'):
                instance.notes = None

        # Override the class-level error attribute if one was parsed
        if error is not None and hasattr(instance, 'error'):
            # Only override if the parsed value differs from the class default
            class_error = getattr(error_cls, 'error', None)
            if error != class_error:
                instance.error = error

        return instance


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


class ValidationError(APIError):
    """Raised when request validation fails with field-level details.

    This error is returned with status code 422 and includes structured
    field-level error information.

    Reference: campus/api/docs/api-error-spec.md Section 5
    """
    status_code = 422
    error = "VALIDATION_FAILED"

    @property
    def field_errors(self) -> list[FieldError]:
        """Return list of field errors, empty if none."""
        return self.errors or []

    def get_errors_for_field(self, field_name: str) -> list[FieldError]:
        """Get all errors for a specific field.

        Args:
            field_name: The field name to get errors for

        Returns:
            List of FieldError objects for the specified field
        """
        return [e for e in self.field_errors if e.field == field_name]
