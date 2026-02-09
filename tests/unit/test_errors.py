"""Tests for error response handling.

Tests new error envelope format parsing with backward compatibility
for the legacy format.

Reference: campus/api/docs/api-error-spec.md
"""

import sys
from pathlib import Path

# Add campus_python to path to import without triggering campus_python/__init__.py
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "campus_python"))

import unittest

from errors import (
    APIError,
    BadRequestError,
    FieldError,
    NotFoundError,
    ValidationError,
)


class TestFieldError(unittest.TestCase):
    """Test FieldError dataclass."""

    def test_field_error_creation(self):
        """FieldError can be created with required attributes."""
        error = FieldError(
            field="email",
            code="INVALID_FORMAT",
            message="Invalid email format"
        )
        self.assertEqual(error.field, "email")
        self.assertEqual(error.code, "INVALID_FORMAT")
        self.assertEqual(error.message, "Invalid email format")


class TestAPIErrorNewFields(unittest.TestCase):
    """Test APIError with new fields from error envelope spec."""

    def test_api_error_with_new_fields(self):
        """APIError accepts new fields: request_id, details, errors, notes."""
        error = APIError(
            status_code=500,
            error_description="Server error",
            request_id="req-123",
            details={"traceback": "..."},
            errors=None,
            notes={"headers": {}, "body": "..."}
        )
        self.assertEqual(error.status_code, 500)
        self.assertEqual(error.request_id, "req-123")
        self.assertEqual(error.details, {"traceback": "..."})
        self.assertIsNone(error.errors)
        self.assertEqual(error.notes, {"headers": {}, "body": "..."})

    def test_api_error_defaults(self):
        """APIError new fields have sensible defaults."""
        error = APIError(status_code=404, error_description="Not found")
        self.assertIsNone(error.request_id)
        self.assertEqual(error.details, {})
        self.assertIsNone(error.errors)
        self.assertIsNone(error.notes)


class TestErrorEnvelopeParsing(unittest.TestCase):
    """Test parsing new error envelope format."""

    def test_parse_new_error_envelope(self):
        """with_status_code parses new error envelope format."""
        response_data = {
            "error": {
                "code": "NOT_FOUND",
                "message": "Resource not found",
                "request_id": "req-456",
                "details": {"resource_id": "123"}
            }
        }

        error = APIError.with_status_code(404, response_data)

        self.assertIsInstance(error, NotFoundError)
        self.assertEqual(error.error_description, "Resource not found")
        self.assertEqual(error.request_id, "req-456")
        self.assertEqual(error.details, {"resource_id": "123"})

    def test_parse_new_error_envelope_without_optional_fields(self):
        """Error envelope works without optional fields."""
        response_data = {
            "error": {
                "code": "NOT_FOUND",
                "message": "Not found",
                "request_id": None
            }
        }

        error = APIError.with_status_code(404, response_data)

        self.assertIsInstance(error, NotFoundError)
        self.assertEqual(error.error_description, "Not found")
        self.assertIsNone(error.request_id)
        self.assertEqual(error.details, {})

    def test_parse_legacy_format(self):
        """Legacy error format is still supported for backward compatibility."""
        response_data = {
            "error_code": "NOT_FOUND",
            "message": "Resource not found",
            "details": {"resource_id": "123"}
        }

        error = APIError.with_status_code(404, response_data)

        self.assertIsInstance(error, NotFoundError)
        self.assertEqual(error.error_description, "Resource not found")
        self.assertEqual(error.details, {"resource_id": "123"})

    def test_string_response_data(self):
        """String response data is used as error_description."""
        error = APIError.with_status_code(500, "Internal server error")

        self.assertIsInstance(error, APIError)
        self.assertEqual(error.error_description, "Internal server error")

    def test_none_response_data(self):
        """None response_data creates error with default message."""
        error = APIError.with_status_code(500, None)

        self.assertIsInstance(error, APIError)
        # The error will have a None description since we didn't provide one
        self.assertIsNone(error.error_description)

    def test_success_status_returns_none(self):
        """Status codes < 400 return None."""
        self.assertIsNone(APIError.with_status_code(200, {}))
        self.assertIsNone(APIError.with_status_code(201, {}))
        self.assertIsNone(APIError.with_status_code(204, {}))
        self.assertIsNone(APIError.with_status_code(304, {}))


class TestValidationErrorParsing(unittest.TestCase):
    """Test ValidationError with field-level errors."""

    def test_parse_validation_error_with_field_errors(self):
        """ValidationError parses field-level errors array."""
        response_data = {
            "error": {
                "code": "VALIDATION_FAILED",
                "message": "One or more fields are invalid",
                "request_id": "req-789",
                "errors": [
                    {
                        "field": "email",
                        "code": "INVALID_FORMAT",
                        "message": "Invalid email format"
                    },
                    {
                        "field": "password",
                        "code": "TOO_SHORT",
                        "message": "Password must be at least 8 characters"
                    }
                ]
            }
        }

        error = APIError.with_status_code(422, response_data)

        self.assertIsInstance(error, ValidationError)
        self.assertEqual(error.error, "VALIDATION_FAILED")
        self.assertEqual(error.error_description, "One or more fields are invalid")
        self.assertEqual(error.request_id, "req-789")

        # Check field errors
        self.assertIsNotNone(error.errors)
        self.assertEqual(len(error.errors), 2)

        # First error
        self.assertEqual(error.errors[0].field, "email")
        self.assertEqual(error.errors[0].code, "INVALID_FORMAT")
        self.assertEqual(error.errors[0].message, "Invalid email format")

        # Second error
        self.assertEqual(error.errors[1].field, "password")
        self.assertEqual(error.errors[1].code, "TOO_SHORT")
        self.assertEqual(error.errors[1].message, "Password must be at least 8 characters")

    def test_validation_error_field_errors_property(self):
        """ValidationError.field_errors returns list of FieldErrors."""
        response_data = {
            "error": {
                "code": "VALIDATION_FAILED",
                "message": "Validation failed",
                "errors": [
                    {"field": "name", "code": "MISSING", "message": "Name is required"}
                ]
            }
        }

        error = APIError.with_status_code(422, response_data)

        self.assertEqual(len(error.field_errors), 1)
        self.assertEqual(error.field_errors[0].field, "name")

    def test_validation_error_get_errors_for_field(self):
        """get_errors_for_field filters errors by field name."""
        response_data = {
            "error": {
                "code": "VALIDATION_FAILED",
                "message": "Validation failed",
                "errors": [
                    {"field": "email", "code": "INVALID_FORMAT", "message": "Bad format"},
                    {"field": "email", "code": "REQUIRED", "message": "Is required"},
                    {"field": "password", "code": "TOO_SHORT", "message": "Too short"}
                ]
            }
        }

        error = APIError.with_status_code(422, response_data)

        email_errors = error.get_errors_for_field("email")
        self.assertEqual(len(email_errors), 2)

        password_errors = error.get_errors_for_field("password")
        self.assertEqual(len(password_errors), 1)

        name_errors = error.get_errors_for_field("name")
        self.assertEqual(len(name_errors), 0)

    def test_validation_error_without_field_errors(self):
        """ValidationError works without errors array."""
        response_data = {
            "error": {
                "code": "VALIDATION_FAILED",
                "message": "Validation failed"
            }
        }

        error = APIError.with_status_code(422, response_data)

        self.assertIsInstance(error, ValidationError)
        self.assertIsNone(error.errors)
        self.assertEqual(error.field_errors, [])


class TestExplicitParametersOverride(unittest.TestCase):
    """Test that explicit parameters override parsed values."""

    def test_explicit_error_overrides_parsed(self):
        """Explicit error parameter overrides parsed value."""
        response_data = {
            "error": {
                "code": "NOT_FOUND",
                "message": "Parsed message"
            }
        }

        error = APIError.with_status_code(
            404,
            response_data,
            error="CUSTOM_CODE",
            error_description="Override message"
        )

        self.assertEqual(error.error_description, "Override message")

    def test_explicit_request_id_overrides_parsed(self):
        """Explicit request_id overrides parsed value."""
        response_data = {
            "error": {
                "code": "NOT_FOUND",
                "message": "Not found",
                "request_id": "parsed-123"
            }
        }

        error = APIError.with_status_code(
            404,
            response_data,
            request_id="override-456"
        )

        self.assertEqual(error.request_id, "override-456")


class TestOtherErrorCodes(unittest.TestCase):
    """Test that other error status codes still work correctly."""

    def test_400_bad_request(self):
        """400 status code returns BadRequestError."""
        response_data = {
            "error": {
                "code": "INVALID_REQUEST",
                "message": "Bad request"
            }
        }

        error = APIError.with_status_code(400, response_data)

        self.assertIsInstance(error, BadRequestError)
        self.assertEqual(error.error_description, "Bad request")

    def test_unknown_status_code_returns_base_api_error(self):
        """Unregistered status codes return base APIError."""
        response_data = {
            "error": {
                "code": "UNKNOWN",
                "message": "Unknown error"
            }
        }

        error = APIError.with_status_code(418, response_data)

        self.assertIsInstance(error, APIError)
        self.assertNotIsInstance(error, BadRequestError)
        self.assertNotIsInstance(error, NotFoundError)


if __name__ == "__main__":
    unittest.main()
