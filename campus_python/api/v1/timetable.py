"""campus_python.api.v1.timetable

Campus API timetable resource (v1).
"""

import typing

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

    def __getitem__(self, timetable_id: str) -> "Timetables.Timetable":
        """Get a specific timetable resource by ID."""
        return Timetables.Timetable(timetable_id, parent=self)

    def get_current(self) -> str:
        """Get the timetable ID of current timetable."""
        return self._get_json(self.make_path("current", end_slash=False))["value"]

    def get_next(self) -> str:
        """Get the timetable ID of next timetable."""
        return self._get_json(self.make_path("next", end_slash=False))["value"]

    def set_current(self, timetable_id: str) -> None:
        """Set the current timetable.

        Args:
            timetable_id: ID of the timetable to set as current
        """
        self._put_json(
            self.make_path("current", end_slash=False),
            json={"value": timetable_id}
        )

    def set_next(self, timetable_id: str) -> None:
        """Set the next timetable.

        Args:
            timetable_id: ID of the timetable to set as next
        """
        self._put_json(
            self.make_path("next", end_slash=False),
            json={"value": timetable_id}
        )

    def new(self, metadata: dict, data: dict) -> dict:
        """Create a new timetable.

        Args:
            metadata: Metadata for the timetable (e.g., start_date, end_date)
            data: Timetable data; must contain the key `lessongroups`
                (not `lesson_groups` — the server rejects the request
                with 400 otherwise)

        Returns:
            The created timetable resource
        """
        if "lessongroups" not in data:
            raise ValueError(
                "data must contain the key 'lessongroups'"
                + (
                    " ('lesson_groups' found instead — rename it)"
                    if "lesson_groups" in data else ""
                )
            )
        body = self._post_json(
            self.make_path(),
            json={
                "metadata": metadata,
                "data": data
            }
        )
        # POST /timetable/ wraps the created resource in a data envelope
        return body["data"]

    def list(self, **filters: typing.Any) -> "list[campus.model.TimetableMetadata]":
        """List timetables matching the provided filters.

        Args:
            **filters: Arbitrary filter parameters applied to the query.

        Returns:
            list[campus.model.TimetableMetadata]: Matching timetable metadata objects.
        """
        body = self._get_json(self.make_path(), query=filters if filters else None)
        return [
            campus.model.TimetableMetadata.from_resource(item)
            for item in body["data"]
        ]

    class Timetable(Resource):
        """A single timetable with start date."""

        @property
        def entries(self) -> "Timetables.Timetable.Entries":
            """Get the entries resource for this timetable."""
            return Timetables.Timetable.Entries("entries", parent=self)

        @property
        def metadata(self) -> "Timetables.Timetable.Metadata":
            """Get the metadata resource for this timetable."""
            return Timetables.Timetable.Metadata("metadata", parent=self)

        def get(self) -> campus.model.Timetable:
            """Get this timetable (metadata and labeled entries).

            GET /timetable/<id>/ wraps the resource in a
            ``{"timetable": ...}`` envelope.
            """
            body = self._get_json(self.make_path(end_slash=True))
            return campus.model.Timetable.from_resource(body["timetable"])

        class Entries(Resource):
            """Entries for a single timetable."""
            path = "entries"

            def list(self) -> "list[campus.model.TimetableEntry]":
                """Return a list of all entries for this timetable."""
                body = self._get_json(self.make_path())
                return [
                    campus.model.TimetableEntry.from_resource(item)
                    for item in body["entries"]
                ]

        class Metadata(Resource):
            """Metadata for a single timetable."""
            path = "metadata"

            def get(self) -> campus.model.TimetableMetadata:
                """Get the metadata for this timetable.

                This does not include timetable entries.
                """
                body = self._get_json(self.make_path())
                return campus.model.TimetableMetadata.from_resource(body)

            def update(self, *, start_date: str, end_date: str) -> None:
                """Update the metadata for this timetable.

                The API replaces both dates together: each is required.

                Args:
                    start_date: New start date (schema.DateTime-compatible)
                    end_date: New end date (schema.DateTime-compatible)
                """
                self._patch_json(self.make_path(), json={
                    "start_date": start_date,
                    "end_date": end_date,
                })
                return None
