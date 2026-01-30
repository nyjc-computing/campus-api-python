"""campus_python.api.v1.assignments

Campus API assignments resource (v1).
"""

import campus.model

from ...interface import Resource, ResourceCollection


class Assignments(ResourceCollection):
    """Campus API Assignments resource."""
    path = "assignments"

    def __getitem__(self, assignment_id: str) -> "Assignments.Assignment":
        """Get a specific assignment resource by ID."""
        return Assignments.Assignment(assignment_id, parent=self)

    def list(self, *, created_by: str | None = None) -> list[campus.model.Assignment]:
        """List all assignments matching filter requirements.

        Args:
            created_by: Filter by teacher who created the assignment

        Returns:
            List of Assignment objects
        """
        params = {}
        if created_by:
            params["created_by"] = created_by

        resp = self.client.get(self.make_path(), params=params)
        # Raise error if status code is not 2XX or 3XX
        resp.raise_for_status()
        return [
            campus.model.Assignment.from_resource(item)
            for item in resp.json()["data"]
        ]

    def new(
            self,
            *,
            title: str,
            description: "str | None" = None,
            questions: "list[dict] | None" = None,
            classroom_links: "list[dict] | None" = None,
    ) -> campus.model.Assignment:
        payload = {"title": title}
        if description is not None:
            payload["description"] = description
        if questions is not None:
            payload["questions"] = questions
        if classroom_links is not None:
            payload["classroom_links"] = classroom_links

        resp = self.client.post(self.make_path(), json=payload)
        resp.raise_for_status()
        return campus.model.Assignment.from_resource(resp.json())

    class Assignment(Resource):
        """Single campus API assignment resource."""

        @property
        def links(self) -> "Assignments.Assignment.Links":
            """Get the links resource for this assignment."""
            return Assignments.Assignment.Links(parent=self)

        def delete(self) -> None:
            resp = self.client.delete(self.make_path())
            resp.raise_for_status()
            return None

        def get(self) -> campus.model.Assignment:
            resp = self.client.get(self.make_path())
            resp.raise_for_status()
            return campus.model.Assignment.from_resource(resp.json())

        def update(self, **updates) -> None:
            resp = self.client.patch(self.make_path(), json=updates)
            resp.raise_for_status()
            return None

        class Links(Resource):
            """Campus API Assignment Links resource."""
            path = "links"

            def add(
                    self,
                    *,
                    course_id: str,
                    coursework_id: str,
                    attachment_id: str | None = None,
            ) -> None:
                payload = {
                    "course_id": course_id,
                    "coursework_id": coursework_id,
                }
                if attachment_id is not None:
                    payload["attachment_id"] = attachment_id

                resp = self.client.post(self.make_path(), json=payload)
                resp.raise_for_status()
                return None