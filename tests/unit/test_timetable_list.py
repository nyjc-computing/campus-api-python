import unittest
from unittest.mock import Mock, MagicMock

from campus_python.api.v1.timetable import Timetables
from campus_python.interface import ResourceRoot
import campus.model


class TestTimetablesList(unittest.TestCase):
    """Test Timetables.list() method."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock client
        self.mock_client = Mock()
        self.mock_client.base_url = "https://api.example.com"

        # Create resource root
        self.root = ResourceRoot(self.mock_client)
        self.root.url_prefix = "api/v1"

        # Create Timetables instance
        self.timetables = Timetables(self.mock_client, root=self.root)

    def test_list_without_filters(self):
        """Test list() returns timetables without filters."""
        # Mock the response - backend returns direct list
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "id": "tt-123",
                "filename": "schedule.xlsx",
                "start_date": "2026-01-01T00:00:00Z",
                "end_date": "2026-06-30T00:00:00Z",
                "created_at": "2026-01-01T00:00:00Z"
            },
            {
                "id": "tt-456",
                "filename": "other.xlsx",
                "start_date": "2026-07-01T00:00:00Z",
                "end_date": "2026-12-31T00:00:00Z",
                "created_at": "2026-07-01T00:00:00Z"
            }
        ]
        mock_response.raise_for_status = Mock()

        self.mock_client.get.return_value = mock_response

        # Call list()
        result = self.timetables.list()

        # Verify the client was called correctly
        self.mock_client.get.assert_called_once_with(
            "/api/v1/timetable/",
            query=None
        )

        # Verify results
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].id, "tt-123")
        self.assertEqual(result[0].filename, "schedule.xlsx")
        self.assertEqual(result[1].id, "tt-456")
        self.assertEqual(result[1].filename, "other.xlsx")

    def test_list_with_filters(self):
        """Test list() with filter parameters."""
        # Mock the response - backend returns direct list
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "id": "tt-123",
                "filename": "schedule.xlsx",
                "start_date": "2026-01-01T00:00:00Z",
                "end_date": "2026-06-30T00:00:00Z",
                "created_at": "2026-01-01T00:00:00Z"
            }
        ]
        mock_response.raise_for_status = Mock()

        self.mock_client.get.return_value = mock_response

        # Call list() with filters
        result = self.timetables.list(filename="schedule.xlsx")

        # Verify the client was called with correct filters
        self.mock_client.get.assert_called_once_with(
            "/api/v1/timetable/",
            query={"filename": "schedule.xlsx"}
        )

        # Verify results
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].filename, "schedule.xlsx")

    def test_list_empty_result(self):
        """Test list() returns empty list when no timetables found."""
        # Mock the response - backend returns direct list
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = Mock()

        self.mock_client.get.return_value = mock_response

        # Call list()
        result = self.timetables.list()

        # Verify results
        self.assertEqual(len(result), 0)

    def test_list_with_multiple_filters(self):
        """Test list() with multiple filter parameters."""
        # Mock the response - backend returns direct list
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "id": "tt-789",
                "filename": "test.xlsx",
                "start_date": "2026-01-01T00:00:00Z",
                "end_date": "2026-06-30T00:00:00Z",
                "created_at": "2026-01-01T00:00:00Z"
            }
        ]
        mock_response.raise_for_status = Mock()

        self.mock_client.get.return_value = mock_response

        # Call list() with multiple filters
        result = self.timetables.list(
            filename="test.xlsx",
            start_date="2026-01-01T00:00:00Z"
        )

        # Verify the client was called with correct filters
        self.mock_client.get.assert_called_once_with(
            "/api/v1/timetable/",
            query={
                "filename": "test.xlsx",
                "start_date": "2026-01-01T00:00:00Z"
            }
        )

        # Verify results
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].filename, "test.xlsx")

    def test_list_propagates_client_errors(self):
        """Test list() propagates client errors."""
        # Mock response with raise_for_status that raises exception
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("Client error")

        self.mock_client.get.return_value = mock_response

        # Call list() should raise exception
        with self.assertRaises(Exception) as context:
            self.timetables.list()

        self.assertEqual(str(context.exception), "Client error")


if __name__ == "__main__":
    unittest.main()