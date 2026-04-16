"""campus_python.api.v1.timetable

Campus API timetable resource (v1).
"""

import campus.model

from ...interface import Resource, ResourceCollection

TIMESLOTS = [
    "0730",
    "0800",
    "0830",
    "0900",
    "0930",
    "1000",
    "1030",
    "1100",
    "1130",
    "1200",
    "1230",
    "1300",
    "1330",
    "1400",
    "1430",
    "1500",
    "1530",
    "1600",
    "1630",
    "1700",
    "1730",
    "1800",
    "1830",
    "1900",
]
WEEKDAYS = [
    "Mon A",
    "Tue A",
    "Wed A",
    "Thu A",
    "Fri A",
    "Mon B",
    "Tue B",
    "Wed B",
    "Thu B",
    "Fri B",
]


class Timetables(ResourceCollection):
    """Campus API Timetable resource."""
    path = "timetable"
    # hardcoded enums
    timeslots = TIMESLOTS
    weekdays = WEEKDAYS

    def __getitem__(self, timtable_id: str) -> "Timetables.Timetable":
        """Get a specific timetable resource by ID."""
        return Timetables.Timetable(timtable_id, parent=self)

    def get_current(self) -> str:
        """Get the timetable ID of current timetable."""
        resp = self.client.get(self.make_path("current"))
        resp.raise_for_status()
        return resp.json()["value"]

    def get_next(self) -> str:
        """Get the timetable ID of next timetable."""
        resp = self.client.get(self.make_path("next"))
        resp.raise_for_status()
        return resp.json()["value"]

    def set_current(self, timetable_id: str) -> None:
        """Set the current timetable.

        Args:
            timetable_id: ID of the timetable to set as current
        """
        resp = self.client.put(
            self.make_path("current"),
            json={"value": timetable_id}
        )
        resp.raise_for_status()

    def set_next(self, timetable_id: str) -> None:
        """Set the next timetable.

        Args:
            timetable_id: ID of the timetable to set as next
        """
        resp = self.client.put(
            self.make_path("next"),
            json={"value": timetable_id}
        )
        resp.raise_for_status()

    def new(self, metadata: dict, data: dict) -> dict:
        """Create a new timetable.

        Args:
            metadata: Metadata for the timetable (e.g., start_date, end_date)
            data: Timetable data (e.g., entries)

        Returns:
            The created timetable resource

        Raises:
            NotImplementedError: Not yet implemented
        """
        raise NotImplementedError("TODO: Student to implement")

    class Timetable(Resource):
        """A single timetable with start date."""

        @property
        def entries(self) -> "Timetables.Timetable.Entries":
            """Get the entries resource for this timetable."""
            return Timetables.Timetable.Entries(parent=self)

        @property
        def metadata(self) -> "Timetables.Timetable.Metadata":
            """Get the metadata resource for this timetable."""
            return Timetables.Timetable.Metadata(parent=self)

        def get(self) -> campus.model.Timetable:
            """Get the metadata for this timetable."""
            timetable = self.metadata.get()
            # entries = self.entries.list()
            # timetable.entries = entries
            # venues = self.venues.list()
            # timetable.venues = venues
            return timetable

        class Entries(Resource):
            """Entries for a single timetable."""
            path = "entries"

            def list(self) -> "list[campus.model.TimetableEntry]":
                """List all entries for this timetable."""
                resp = self.client.get(self.make_path(end_slash=True))
                resp.raise_for_status()
                return [
                    campus.model.TimetableEntry.from_resource(item)
                    for item in resp.json()["entries"]
                ]

        class Metadata(Resource):
            """Metadata for a single timetable."""
            path = "metadata"

            def get(self) -> campus.model.Timetable:
                """Get the metadata for this timetable."""
                resp = self.client.get(self.make_path(end_slash=True))
                resp.raise_for_status()
                return campus.model.Timetable.from_resource(resp.json())

            def update(self, **kwargs) -> None:
                """Update the metadata for this timetable.

                Args:
                    **kwargs: Fields to update (e.g., start_date, end_date)

                Raises:
                    NotImplementedError: Not yet implemented
                """
                raise NotImplementedError("TODO: Student to implement")


