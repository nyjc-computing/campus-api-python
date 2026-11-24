"""campus.python.api

Campus API resource.
"""

from ...interface import ResourceRoot
from ...json_client.interface import JsonClient
from . import (
    assignments,
    circles,
    files,
    hostedapps,
    subjcombi,
    submissions,
    timetable,
    users,
    venues,
)

class ApiRoot(ResourceRoot):
    """Campus API resource."""
    url_prefix = "/api/v1"

    def __init__(self, json_client: JsonClient):
        super().__init__(json_client=json_client)
        self._clients = None
        self._assignments = None
        self._circles = None
        self._files = None
        self._hostedapps = None
        self._submissions = None
        self._subjcombi = None
        self._timetables = None
        self._users = None
        self._venues = None

    @property
    def assignments(self) -> assignments.Assignments:
        """Get the assignments resource."""
        if not self._assignments:
            self._assignments = assignments.Assignments(root=self)
        return self._assignments

    @property
    def circles(self) -> circles.Circles:
        """Get the circles resource."""
        if not self._circles:
            self._circles = circles.Circles(root=self)
        return self._circles

    @property
    def files(self) -> files.Files:
        """Get the files resource (by-slug + id-based management)."""
        if not self._files:
            self._files = files.Files(root=self)
        return self._files

    @property
    def hostedapps(self) -> hostedapps.HostedApps:
        """Get the hosted-apps resource (by-slug consumer surface)."""
        if not self._hostedapps:
            self._hostedapps = hostedapps.HostedApps(root=self)
        return self._hostedapps

    @property
    def subjcombi(self) -> subjcombi.Subjcombi:
        """Get the subjcombi resource (user→lessongroup mappings)."""
        if not self._subjcombi:
            self._subjcombi = subjcombi.Subjcombi(root=self)
        return self._subjcombi

    @property
    def submissions(self) -> submissions.Submissions:
        """Get the submissions resource."""
        if not self._submissions:
            self._submissions = submissions.Submissions(root=self)
        return self._submissions

    @property
    def timetable(self) -> timetable.Timetables:
        """Get the timetable resource."""
        if not self._timetables:
            self._timetables = timetable.Timetables(root=self)
        return self._timetables

    @property
    def users(self) -> users.Users:
        """Get the users resource (directory facade + roles query)."""
        if not self._users:
            self._users = users.Users(root=self)
        return self._users

    @property
    def venues(self) -> venues.Venues:
        """Get the venues resource (documents-backed venue CRUD)."""
        if not self._venues:
            self._venues = venues.Venues(root=self)
        return self._venues
