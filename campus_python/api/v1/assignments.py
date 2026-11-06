"""campus_python.api.v1.assignments

Campus API assignments resource (v1).
"""

import campus.model

from ...interface import Resource, ResourceCollection, payload, updates


class Assignments(ResourceCollection):
    """Campus API Assignments resource."""
    path = "assignments"

    def __getitem__(self, assignment_id: str) -> "Assignments.Assignment":
        """Get a specific assignment resource by ID."""
        return Assignments.Assignment(assignment_id, parent=self)

    def list(self, *, created_by: "str | None" = None) -> "list[campus.model.Assignment]":
        """List all assignments matching filter requirements.

        Args:
            created_by: Filter by teacher who created the assignment

        Returns:
            List of Assignment objects
        """
        params = {}
        if created_by:
            params["created_by"] = created_by

        body = self._get_json(self.make_path(), query=params)
        return [
            campus.model.Assignment.from_resource(item)
            for item in body["data"]
        ]

    def new(
            self,
            *,
            title: str,
            description: "str | None" = None,
            questions: "list[dict] | None" = None,
            classroom_links: "list[dict] | None" = None,
    ) -> campus.model.Assignment:
        """Create a new assignment.

        Args:
            title: Assignment title (required by the server).
            description: Assignment description.
            questions: Question definitions.
            classroom_links: Google Classroom course/coursework links.

        Returns:
            The created Assignment.
        """
        return campus.model.Assignment.from_resource(self._post_json(
            self.make_path(),
            json=payload(
                title=title,
                description=description,
                questions=questions,
                classroom_links=classroom_links,
            )
        ))

    class Assignment(Resource):
        """Single campus API assignment resource."""

        @property
        def links(self) -> "Assignments.Assignment.Links":
            """Get the links resource for this assignment."""
            return Assignments.Assignment.Links("links", parent=self)

        def delete(self) -> None:
            """Delete this assignment."""
            self._delete_json(self.make_path(end_slash=True))

        def get(self) -> campus.model.Assignment:
            """Get this assignment.

            Returns:
                The Assignment.
            """
            body = self._get_json(self.make_path(end_slash=True))
            return campus.model.Assignment.from_resource(body)

        def update(self, **fields) -> None:
            """Update this assignment with the given fields.

            The server rejects an empty PATCH body, so at least one
            field must be provided.
            """
            self._patch_json(self.make_path(end_slash=True), json=updates(**fields))
            return None

        class Links(Resource):
            """Campus API Assignment Links resource."""

            def add(
                    self,
                    *,
                    course_id: str,
                    coursework_id: str,
                    attachment_id: str | None = None,
            ) -> None:
                """Attach a Google Classroom course/coursework link.

                Args:
                    course_id: Classroom course ID.
                    coursework_id: Classroom coursework ID.
                    attachment_id: Optional Drive attachment ID.
                """
                self._post_json(self.make_path(), json=payload(
                    course_id=course_id,
                    coursework_id=coursework_id,
                    attachment_id=attachment_id,
                ))
                return None