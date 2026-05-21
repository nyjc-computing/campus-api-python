import os
import unittest

import campus_python


class TestCampusInitialization(unittest.TestCase):
    """Test Campus client initialization and credential validation."""

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

    def test_campus_init_missing_both_credentials(self):
        """Test that Campus.__init__() raises OSError when both credentials are missing."""
        with self.assertRaises(OSError) as context:
            campus_python.Campus(timeout=60)

        # Verify error message mentions both variables
        self.assertIn('CLIENT_ID', str(context.exception))
        self.assertIn('CLIENT_SECRET', str(context.exception))

    def test_campus_init_missing_client_id(self):
        """Test that Campus.__init__() raises OSError when CLIENT_ID is missing."""
        os.environ['CLIENT_SECRET'] = 'test-secret'

        with self.assertRaises(OSError) as context:
            campus_python.Campus(timeout=60)

        self.assertIn('CLIENT_ID', str(context.exception))

    def test_campus_init_missing_client_secret(self):
        """Test that Campus.__init__() raises OSError when CLIENT_SECRET is missing."""
        os.environ['CLIENT_ID'] = 'test-client'

        with self.assertRaises(OSError) as context:
            campus_python.Campus(timeout=60)

        self.assertIn('CLIENT_SECRET', str(context.exception))

    def test_campus_init_with_credentials(self):
        """Test that Campus.__init__() succeeds when both credentials are present."""
        os.environ['CLIENT_ID'] = 'test-client-id'
        os.environ['CLIENT_SECRET'] = 'test-client-secret'

        # Should not raise
        campus = campus_python.Campus(timeout=60)

        # Verify timeout is set correctly
        self.assertEqual(campus.timeout, 60)

    def test_campus_init_fail_fast(self):
        """Test that Campus.__init__() fails immediately, not on first use.

        This is a regression test for the bug where missing credentials were
        only detected when first accessing campus.auth or campus.api (lazy
        loading), rather than during Campus object construction.
        """
        # The Campus object should raise OSError immediately in __init__
        # NOT when accessing campus.auth for the first time
        with self.assertRaises(OSError):
            campus_python.Campus(timeout=60)

        # If we got here without an exception, the fail-fast check is broken

    def test_campus_init_device_mode_no_credentials(self):
        """Test that Campus.__init__() succeeds in device mode without credentials."""
        # Device mode should NOT require CLIENT_ID or CLIENT_SECRET
        campus = campus_python.Campus(timeout=60, mode="device")

        # Verify mode is set correctly
        self.assertEqual(campus._mode, "device")

    def test_campus_init_device_mode_with_credentials_ignored(self):
        """Test that credentials are ignored in device mode."""
        # Set credentials (they should be ignored in device mode)
        os.environ['CLIENT_ID'] = 'test-client-id'
        os.environ['CLIENT_SECRET'] = 'test-client-secret'

        # Should succeed without using credentials
        campus = campus_python.Campus(timeout=60, mode="device")

        # Verify mode is set correctly
        self.assertEqual(campus._mode, "device")


if __name__ == "__main__":
    unittest.main()
