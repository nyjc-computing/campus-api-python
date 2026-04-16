"""campus.python.api

Campus API resource.
"""

from ...interface import ResourceRoot
from ...json_client.interface import JsonClient
from . import (
    assignments,
    circles,
    submissions,
    timetable,
)

class ApiRoot(ResourceRoot):
    """Campus API resource."""
    url_prefix = "/api/v1"

    def __init__(self, json_client: JsonClient):
        self._json_client = json_client
        self._clients = None
        self._assignments = None
        self._circles = None
        self._submissions = None
        self._timetables = None

    @property
    def assignments(self) -> assignments.Assignments:
        """Get the assignments resource."""
        if not self._assignments:
            self._assignments = assignments.Assignments(
                self._json_client,
                root=self
            )
        return self._assignments

    @property
    def circles(self) -> circles.Circles:
        """Get the circles resource."""
        if not self._circles:
            self._circles = circles.Circles(
                self._json_client,
                root=self
            )
        return self._circles

    @property
    def submissions(self) -> submissions.Submissions:
        """Get the submissions resource."""
        if not self._submissions:
            self._submissions = submissions.Submissions(
                self._json_client,
                root=self
            )
        return self._submissions

    @property
    def timetable(self) -> timetable.Timetables:
        """Get the timetable resource."""
        if not self._timetables:
            self._timetables = timetable.Timetables(
                self._json_client,
                root=self
            )
        return self._timetables
