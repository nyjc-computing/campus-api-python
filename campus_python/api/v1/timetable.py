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

    def view(self) -> dict:
        """Get the deployment's timetable pointer state.

        Returns:
            {"current": timetable_id | None, "next": timetable_id |
            None, "effective_from": datetime | None} — the pending
            switch applies at its effective_from without any client
            action (#1075).
        """
        return self._get_json(self.make_path())

    def patch(
        self,
        *,
        current: str | None = None,
        next: str | None = None,  # noqa: A002 - API field name
        effective_from: str | None = None,
    ) -> dict:
        """Patch exactly one timetable pointer (#1075).

        Pass keyword arguments, exactly one of `current` or `next`.

        Args:
            current: Timetable ID to make current, effective now.
            next: Timetable ID to schedule as the pending switch
                (reschedules any previous pending switch).
            effective_from: When the pending switch applies (ISO
                datetime, or YYYY-MM-DD for 07:00 school time). Only
                valid with `next`; absent stages an undated switch
                that flips only when pointed at manually.

        Returns:
            The resulting pointer state (same shape as view()).
        """
        present = {
            key: value
            for key, value in (("current", current), ("next", next))
            if value is not None
        }
        if len(present) != 1:
            raise ValueError(
                "Patch exactly one pointer: pass current=<id> or "
                "next=<id> (use cancel_next() to cancel a pending "
                "switch)"
            )
        body: dict = dict(present)
        if "next" in body and effective_from is not None:
            body["effective_from"] = effective_from
        return self._patch_json(self.make_path(), json=body)

    def cancel_next(self) -> dict:
        """Cancel the pending scheduled switch (API: {next: null}).

        Returns:
            The resulting pointer state.
        """
        return self._patch_json(self.make_path(), json={"next": None})

    def me(self, at: str | None = None) -> dict:
        """Resolve the signed-in user's effective timetable view (#592).

        Returns:
            {"current": {timetable_id, lessongroup_id, source},
            "next": null | {..., effective_from, change_type}}; entries
            render via timetable[id].entries filtered by
            lessongroup_id.
        """
        query = {"at": at} if at else None
        return self._get_json(
            self.make_path("me", end_slash=False), query=query
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

    def list_metadata(
        self, **filters: typing.Any
    ) -> "list[campus.model.TimetableMetadata]":
        """List timetable metadata records.

        Args:
            **filters: Arbitrary filter parameters applied to the query.

        Returns:
            list[campus.model.TimetableMetadata]: Matching
            timetable metadata objects. (GET /timetable/ itself now
            serves the pointer state; the list lives at
            /timetable/metadata/.)
        """
        body = self._get_json(
            self.make_path("metadata"), query=filters if filters else None
        )
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

        def delete(self) -> None:
            """Delete this timetable version and all of its rows (#1088).

            DELETE /timetable/<id>/ cascades the version's entries, group
            members and lessongroup rows, then the version row itself.
            The API refuses the version the current or next pointer
            names with a 409 — move/cancel the pointer first. This is
            the cleanup surface for the label-drift create 409.
            """
            self._delete_json(self.make_path(end_slash=True))
            return None

        def get(self) -> campus.model.Timetable:
            """Get this timetable (metadata and labeled entries).

            GET /timetable/<id>/ wraps the resource in a
            ``{"timetable": ...}`` envelope.
            """
            body = self._get_json(self.make_path(end_slash=True))
            return campus.model.Timetable.from_resource(body["timetable"])

        class Entries(Resource):
            """Entries for a single timetable."""

            def list(self) -> "list[campus.model.TimetableEntry]":
                """Return a list of all entries for this timetable."""
                body = self._get_json(self.make_path())
                return [
                    campus.model.TimetableEntry.from_resource(item)
                    for item in body["entries"]
                ]

        class Metadata(Resource):
            """Metadata for a single timetable."""

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
