"""campus.python.auth.v1.users

Campus Auth users resource (v1).

This mirrors the style used in `clients.py` and `credentials.py` and
implements the minimal methods used by the Flask routes: list, new,
and per-user activate/delete/get.
"""

import campus.model

from ...interface import Resource, ResourceCollection


class Users(ResourceCollection):
    """Vault Users resource."""
    path = "users/"

    def __getitem__(self, user_id: str) -> "Users.User":
        """Get a specific user resource by ID."""
        return Users.User(user_id, parent=self)

    def list(self) -> list[campus.model.User]:
        resp = self.client.get(self.make_path())
        # Raise error if status code is not 2XX or 3XX
        resp.raise_for_status()
        return [
            campus.model.User.from_resource(item)
            for item in resp.json()["users"]
        ]

    def new(self, *, email: str, name: str) -> campus.model.User:
        resp = self.client.post(self.make_path(), json={
            "email": email,
            "name": name,
        })
        resp.raise_for_status()
        return campus.model.User.from_resource(resp.json())

    class User(Resource):
        """Single vault user resource."""

        def activate(self) -> campus.model.User:
            resp = self.client.post(self.make_path("activate"))
            resp.raise_for_status()
            return campus.model.User.from_resource(resp.json())

        def delete(self) -> None:
            resp = self.client.delete(self.make_path())
            resp.raise_for_status()

        def get(self) -> campus.model.User:
            resp = self.client.get(self.make_path())
            resp.raise_for_status()
            return campus.model.User.from_resource(resp.json())
