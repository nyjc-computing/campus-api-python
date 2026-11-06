"""campus.python.auth.v1.users

Campus Auth users resource (v1).

This mirrors the style used in `clients.py` and `credentials.py` and
implements the minimal methods used by the Flask routes: list, new,
and per-user activate/delete/get/update.
"""

import campus.model

from ...interface import Resource, ResourceCollection


class Users(ResourceCollection):
    """Vault Users resource."""
    path = "users"

    def __getitem__(self, user_id: str) -> "Users.User":
        """Get a specific user resource by ID."""
        return Users.User(user_id, parent=self)

    def list(self) -> "list[campus.model.User]":
        """List all users.

        Returns:
            List of User objects.
        """
        body = self._get_json(self.make_path())
        return [
            campus.model.User.from_resource(item)
            for item in body["users"]
        ]

    def new(self, *, email: str, name: str) -> campus.model.User:
        """Create a user.

        A user's id IS its email.

        Args:
            email: The user's email (also their id).
            name: Display name.

        Returns:
            The created User.
        """
        return campus.model.User.from_resource(self._post_json(self.make_path(), json={
            "email": email,
            "name": name,
        }))

    class User(Resource):
        """Single vault user resource."""

        def activate(self) -> campus.model.User:
            """Activate this user (allows login).

            Returns:
                The activated User.
            """
            return campus.model.User.from_resource(
                self._post_json(self.make_path("activate", end_slash=False))
            )

        def delete(self) -> None:
            """Delete this user."""
            self._delete_json(self.make_path(end_slash=True))

        def get(self) -> campus.model.User:
            """Get this user.

            Returns:
                The User.
            """
            body = self._get_json(self.make_path(end_slash=True))
            return campus.model.User.from_resource(body)

        def update(self, *, name: str) -> campus.model.User:
            """Update the user's display name (campus-cli#42).

            The server PATCH accepts name only: a user's id IS its
            email (identity), and activation runs through the
            /activate endpoint, so no other field is patchable.

            Args:
                name: New display name

            Returns:
                The updated User
            """
            body = self._patch_json(
                self.make_path(end_slash=True), json={"name": name}
            )
            return campus.model.User.from_resource(body)
