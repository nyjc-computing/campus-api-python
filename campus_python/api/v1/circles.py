"""campus.python.api.v1.circles

Campus API circles resource (v1).
"""

import campus.model

from ...interface import Resource, ResourceCollection


class Circles(ResourceCollection):
    """Campus API Circles resource."""
    path = "circles"

    def __getitem__(self, circle_id: str) -> "Circles.Circle":
        """Get a specific circle resource by ID."""
        return Circles.Circle(circle_id, parent=self)

    def list(self) -> list[campus.model.Circle]:
        resp = self.client.get(self.make_url())
        # Raise error if status code is not 2XX or 3XX
        resp.raise_for_status()
        return [
            campus.model.Circle.from_resource(item)
            for item in resp.json()["circles"]
        ]

    def new(
            self,
            *,
            name: str,
            description: str,
            tag: str,
            parents: dict[str, int] | None = None,
    ) -> campus.model.Circle:
        resp = self.client.post(self.make_url(), json={
            "name": name,
            "description": description,
        })
        resp.raise_for_status()
        return campus.model.Circle.from_resource(resp.json())

    class Circle(Resource):
        """Single campus API circle resource."""

        @property
        def members(self) -> "Circles.Circle.CircleMembers":
            """Get the members resource for this circle."""
            return Circles.Circle.CircleMembers(parent=self)

        def delete(self) -> None:
            resp = self.client.delete(self.make_url())
            resp.raise_for_status()
            return None

        def get(self) -> campus.model.Circle:
            resp = self.client.get(self.make_url())
            resp.raise_for_status()
            return campus.model.Circle.from_resource(resp.json())

        def update(self, **updates) -> None:
            resp = self.client.patch(self.make_url(), json=updates)
            resp.raise_for_status()
            return None

        class CircleMembers(Resource):
            """Campus API Circle Members resource."""
            path = "members"

            def list(self) -> list[dict[str, int]]:
                resp = self.client.get(self.make_url())
                resp.raise_for_status()
                return resp.json()["members"]

            def add(self, member_id: str, access_value: int) -> None:
                resp = self.client.post(
                    self.make_url(),
                    json={"member_id": member_id, "access": access_value}
                )
                resp.raise_for_status()
                return None

            def remove(self, member_id: str) -> None:
                resp = self.client.delete(
                    self.make_url(),
                    json={"member_id": member_id}
                )
                resp.raise_for_status()
                return None
