"""Tests for CampusRequest class, specifically around authentication modes."""

import os
import unittest

from campus_python.json_client import CampusRequest


class TestCampusRequestModes(unittest.TestCase):
    """Test CampusRequest initialization with different authentication modes."""

    def setUp(self):
        """Save and clear environment variables before each test."""
        self.saved_client_id = os.environ.get('CLIENT_ID')
        self.saved_client_secret = os.environ.get('CLIENT_SECRET')

        # Clear env vars to ensure clean state
        if 'CLIENT_ID' in os.environ:
            del os.environ['CLIENT_ID']
        if 'CLIENT_SECRET' in os.environ:
            del os.environ['CLIENT_SECRET']

    def tearDown(self):
        """Restore original environment variables after each test."""
        # Restore original values
        if self.saved_client_id is not None:
            os.environ['CLIENT_ID'] = self.saved_client_id
        elif 'CLIENT_ID' in os.environ:
            del os.environ['CLIENT_ID']

        if self.saved_client_secret is not None:
            os.environ['CLIENT_SECRET'] = self.saved_client_secret
        elif 'CLIENT_SECRET' in os.environ:
            del os.environ['CLIENT_SECRET']

    def test_server_mode_requires_credentials(self):
        """Test that server mode (default) requires CLIENT_ID and CLIENT_SECRET."""
        with self.assertRaises(OSError) as context:
            CampusRequest(base_url="http://localhost", mode="server")

        # Verify error message mentions both variables
        self.assertIn('CLIENT_ID', str(context.exception))
        self.assertIn('CLIENT_SECRET', str(context.exception))

    def test_device_mode_no_credentials_required(self):
        """Test that device mode does NOT require CLIENT_ID or CLIENT_SECRET."""
        # Should not raise any exception
        client = CampusRequest(base_url="http://localhost", mode="device")

        # Verify the client was created successfully
        self.assertIsNotNone(client)
        self.assertEqual(client.base_url, "http://localhost")

    def test_server_mode_with_credentials(self):
        """Test that server mode works when credentials are provided."""
        os.environ['CLIENT_ID'] = 'test-client-id'
        os.environ['CLIENT_SECRET'] = 'test-client-secret'

        # Should not raise
        client = CampusRequest(base_url="http://localhost", mode="server")

        # Verify the client was created successfully
        self.assertIsNotNone(client)

        # Verify Basic auth header was set
        auth_header = client._session.headers.get('Authorization')
        self.assertIsNotNone(auth_header)
        self.assertTrue(auth_header.startswith('Basic '))

    def test_default_mode_is_server(self):
        """Test that the default mode is 'server' which requires credentials."""
        # Without specifying mode, it should default to "server"
        with self.assertRaises(OSError):
            CampusRequest(base_url="http://localhost")

    def test_bearer_authorization_in_device_mode(self):
        """Test that Bearer authorization can be set in device mode."""
        # Create client in device mode (no credentials required)
        client = CampusRequest(base_url="http://localhost", mode="device")

        # Verify no Authorization header initially
        auth_header = client._session.headers.get('Authorization')
        self.assertIsNone(auth_header)

        # Set Bearer authorization
        test_token = "test-bearer-token-12345"
        client.set_bearer_authorization(test_token)

        # Verify Bearer auth header was set
        auth_header = client._session.headers.get('Authorization')
        self.assertIsNotNone(auth_header)
        self.assertEqual(auth_header, f'Bearer {test_token}')

    def test_bearer_authorization_overrides_basic(self):
        """Test that set_bearer_authorization overrides Basic auth."""
        os.environ['CLIENT_ID'] = 'test-client-id'
        os.environ['CLIENT_SECRET'] = 'test-client-secret'

        # Create client in server mode (sets Basic auth)
        client = CampusRequest(base_url="http://localhost", mode="server")

        # Verify Basic auth was set initially
        auth_header = client._session.headers.get('Authorization')
        self.assertTrue(auth_header.startswith('Basic '))

        # Set Bearer authorization (should override)
        test_token = "test-bearer-token-67890"
        client.set_bearer_authorization(test_token)

        # Verify Bearer auth header replaced Basic auth
        auth_header = client._session.headers.get('Authorization')
        self.assertEqual(auth_header, f'Bearer {test_token}')


if __name__ == "__main__":
    unittest.main()
