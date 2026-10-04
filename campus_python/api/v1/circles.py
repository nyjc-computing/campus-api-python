"""campus.python.api.v1.circles

Campus API circles resource (v1).
"""

from typing import Any

import campus.model

from ...interface import Resource, ResourceCollection


class Circles(ResourceCollection):
    """Campus API Circles resource."""
    path = "circles/"

    def __getitem__(self, circle_id: str) -> "Circles.Circle":
        """Get a specific circle resource by ID."""
        return Circles.Circle(circle_id, parent=self)

    def list(self) -> "list[campus.model.Circle]":
        resp = self.client.get(self.make_path())
        # Raise error if status code is not 2XX or 3XX
        resp.raise_for_status()
        return [
            campus.model.Circle.from_resource(item)
            for item in resp.json()["data"]
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
        resp = self.client.post(self.make_path(), json=payload)
        resp.raise_for_status()
        return campus.model.Circle.from_resource(resp.json())

    class Circle(Resource):
        """Single campus API circle resource."""

        @property
        def members(self) -> "Circles.Circle.CircleMembers":
            """Get the members resource for this circle."""
            return Circles.Circle.CircleMembers("members", parent=self)

        def delete(self) -> None:
            resp = self.client.delete(self.make_path())
            resp.raise_for_status()
            return None

        def get(self) -> campus.model.Circle:
            resp = self.client.get(self.make_path())
            resp.raise_for_status()
            return campus.model.Circle.from_resource(resp.json())

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
            resp = self.client.patch(self.make_path(), json=payload)
            resp.raise_for_status()
            return None

        class CircleMembers(Resource):
            """Campus API Circle Members resource."""
            path = "members"

            def list(self) -> dict[str, int]:
                """Return the circle's {member_id: access_value} mapping."""
                resp = self.client.get(self.make_path(end_slash=True))
                resp.raise_for_status()
                return resp.json()

            def add(self, member_id: str, access_value: int) -> None:
                resp = self.client.post(
                    self.make_path("add"),
                    json={"member_id": member_id, "access_value": access_value}
                )
                resp.raise_for_status()
                return None

            def remove(self, member_id: str) -> None:
                resp = self.client.delete(
                    self.make_path("remove"),
                    json={"member_id": member_id}
                )
                resp.raise_for_status()
                return None

            def set(self, member_id: str, access_value: int) -> None:
                """Create or update a member's access value (upsert).

                Unlike add()/remove(), which target the /members/add and
                /members/remove action routes, this PATCHes the members
                collection directly — the server's set semantics apply
                (no error when the access value is unchanged).
                """
                resp = self.client.patch(
                    self.make_path(end_slash=True),
                    json={"member_id": member_id, "access_value": access_value}
                )
                resp.raise_for_status()
                return None
