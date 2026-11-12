"""campus_python.api.v1.subjcombi

Campus API subjcombi resource (v1): the maintained mapping of a user
to a timetable lessongroup (#592). Changes append effective-dated
records server-side — the records are the mutation trail — and
scheduled changes take effect at their effective_from as a read-time
fact (date-only values apply at 07:00 school time).
"""

from ...interface import Resource, ResourceCollection


class Subjcombi(ResourceCollection):
    """Campus API subjcombi resource."""

    path = "subjcombi"

    def __getitem__(self, user_id: str) -> "Subjcombi.UserMapping":
        """Address one user's mapping by their campus account email."""
        return Subjcombi.UserMapping(user_id, parent=self)

    def set(
        self,
        user_id: str,
        lessongroup_id: str,
        effective_from: str | None = None,
        reason: str | None = None,
    ) -> dict:
        """Set the user's mapping; returns the created trail record.

        Args:
            user_id: The user's campus account email.
            lessongroup_id: The lessongroup label to map the user to
                (the v1 ttcode, e.g. "2601-H1/P" or a bare class code).
                Stored verbatim; it need not exist in any timetable yet.
            effective_from: When it applies (ISO datetime, or
                YYYY-MM-DD for 07:00 school time). Absent = immediate.
            reason: Optional change note, preserved on the trail.
        """
        body: dict = {"lessongroup_id": lessongroup_id}
        if effective_from is not None:
            body["effective_from"] = effective_from
        if reason is not None:
            body["reason"] = reason
        return self._put_json(
            self.make_path(user_id, end_slash=False), json=body
        )

    def list(self) -> "list[dict]":
        """Every user's current effective mapping, one record per user.

        The bulk read for version-switch checking: scheduled (pending)
        switches are not included (pending()); mutation trails stay on
        the per-user history. Sorted by user_id.
        """
        body = self._get_json(self.make_path())
        return body["data"]

    def pending(self) -> "list[dict]":
        """Scheduled mappings not yet effective (soonest first)."""
        body = self._get_json(self.make_path("pending", end_slash=False))
        return body["data"]

    def cancel(self, record_id: str) -> dict:
        """Cancel a pending record (409 once it is effective)."""
        pending_path = self.make_path("pending", end_slash=False)
        return self._delete_json(f"{pending_path}/{record_id}")

    class UserMapping(Resource):
        """One user's mapping view and trail."""

        def get(self, at: str | None = None) -> dict:
            """The user's effective mapping.

            Returns:
                {"user_id": ..., "lessongroup_id": ... | null,
                "source": "mapping" | "roster" | "unmapped"}.
            """
            query = {"at": at} if at else None
            # Collection item paths carry the collection's trailing
            # slash; the API route does not.
            return self._get_json(
                self.make_path(end_slash=False).rstrip("/"), query=query
            )

        def history(self) -> "list[dict]":
            """The user's full mutation trail, newest effective first."""
            body = self._get_json(self.make_path("history"))
            return body["data"]
