"""campus.python.api.v1.circles

Campus API circles resource (v1).
"""

from typing import Any

import campus.model

from ...interface import Resource, ResourceCollection


class Circles(ResourceCollection):
    """Campus API Circles resource."""
    path = "circles"

    def __getitem__(self, circle_id: str) -> "Circles.Circle":
        """Get a specific circle resource by ID."""
        return Circles.Circle(circle_id, parent=self)

    def list(self) -> "list[campus.model.Circle]":
        body = self._get_json(self.make_path())
        return [
            campus.model.Circle.from_resource(item)
            for item in body["data"]
        ]

    def new(
            self,
            *,
            name: str,
            tag: str,
            description: str = "",
            parents: dict[str, int] | None = None,
    ) -> campus.model.Circle:
        payload: dict[str, Any] = {
            "name": name,
            "tag": tag,
            "description": description,
        }
        if parents is not None:
            payload["parents"] = parents
        return campus.model.Circle.from_resource(
            self._post_json(self.make_path(), json=payload)
        )

    class Circle(Resource):
        """Single campus API circle resource."""

        @property
        def members(self) -> "Circles.Circle.CircleMembers":
            """Get the members resource for this circle."""
            return Circles.Circle.CircleMembers("members", parent=self)

        def delete(self) -> None:
            self._delete_json(self.make_path(end_slash=True))

        def get(self) -> campus.model.Circle:
            body = self._get_json(self.make_path(end_slash=True))
            return campus.model.Circle.from_resource(body)

        def update(
                self,
                *,
                name: str,
                description: "str | None" = None,
        ) -> None:
            """Update this circle.

            The server requires name on every circle PATCH and returns
            422 without it, so it is a required parameter here.
            Description is unchanged when omitted.

            Args:
                name: New circle name (must not collide with an
                    existing circle's name)
                description: New description; omitted leaves it unchanged
            """
            payload: dict[str, Any] = {"name": name}
            if description is not None:
                payload["description"] = description
            self._patch_json(self.make_path(end_slash=True), json=payload)
            return None

        class CircleMembers(Resource):
            """Campus API Circle Members resource."""

            def list(self) -> dict[str, int]:
                """Return the circle's {member_id: access_value} mapping."""
                return self._get_json(self.make_path(end_slash=True))

            def add(self, member_id: str, access_value: int) -> None:
                self._post_json(
                    self.make_path("add"),
                    json={"member_id": member_id, "access_value": access_value}
                )

            def remove(self, member_id: str) -> None:
                self._delete_json(
                    self.make_path("remove"),
                    json={"member_id": member_id}
                )

            def set(self, member_id: str, access_value: int) -> None:
                """Create or update a member's access value (upsert).

                Unlike add()/remove(), which target the /members/add and
                /members/remove action routes, this PATCHes the members
                collection directly — the server's set semantics apply
                (no error when the access value is unchanged).
                """
                self._patch_json(
                    self.make_path(end_slash=True),
                    json={"member_id": member_id, "access_value": access_value}
                )
                return None
