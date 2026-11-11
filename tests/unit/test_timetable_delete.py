"""Unit tests for Timetable.delete (#1088).

DELETE /timetable/<id>/ returns an empty object on success; the SDK
just needs to hit the right path with the right verb.
"""

import unittest
from unittest.mock import Mock

from tests.support import make_api


class TestTimetableDelete(unittest.TestCase):
    def setUp(self):
        self.api, self.client = make_api()
        self.client.delete.return_value = Mock(status_code=200)

    def test_delete_hits_version_path(self):
        self.api.timetable["tt-1"].delete()

        self.client.delete.assert_called_once_with("/api/v1/timetable/tt-1/")


if __name__ == "__main__":
    unittest.main()
