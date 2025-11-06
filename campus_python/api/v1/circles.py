"""campus.python.api.v1.circles

Campus API circles resource (v1).
"""

from campus.common import env
import campus.model

from ...interface import JsonDict, Resource, ResourceCollection


class Circles(ResourceCollection):
    """Campus API Circles resource."""
    path = "circles"

    def __getitem__(self, circle_id: str) -> "Circles.Circle":
        """Get a specific circle resource by ID."""
        return Circles.Circle(circle_id, parent=self)

    def list(self) -> list[campus.model.Circle]:
        resp = self.client.get(self.make_path())
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
            tag: str
    ) -> campus.model.Circle:
        resp = self.client.post(self.make_path(), json={
            "name": name,
            "description": description,
        })
        resp.raise_for_status()
        return campus.model.Circle.from_resource(resp.json())

    class Circle(Resource):
        """Single campus API circle resource."""

        def get(self) -> campus.model.Circle:
            resp = self.client.get(self.make_path())
            resp.raise_for_status()
            return campus.model.Circle.from_resource(resp.json())

        def update(self, **updates) -> None:
            resp = self.client.patch(self.make_path(), json=updates)
            resp.raise_for_status()
            return None

        def delete(self) -> None:
            resp = self.client.delete(self.make_path())
            resp.raise_for_status()
            return None
