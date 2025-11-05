"""campus.python.auth.sessions

Client-side interface for authentication session resources.

Implements the `Sessions` collection with provider-specific sessions
and per-session resources used by the Flask routes in `routes/sessions`.
"""

from datetime import datetime

from campus.common import env, schema
import campus.model

from ...interface import JsonDict, Resource, ResourceCollection


class Sessions(ResourceCollection):
    """Campus Auth Sessions resource."""
    path = "sessions"

    def __getitem__(self, provider: str) -> "Sessions.Provider":
        """Get provider-level resource (e.g. /sessions/{provider})."""
        return Sessions.Provider(provider, parent=self)

    def sweep(self, at_time: datetime | str | None = None) -> int:
        json_data: JsonDict = {}
        match at_time:
            case datetime():
                json_data["at_time"] = (
                    schema.DateTime.from_datetime(at_time)
                )
            case str():
                json_data["at_time"] = schema.DateTime(at_time)
            case None:
                json_data["at_time"] = schema.DateTime.utcnow()
        resp = self.client.post(
            self.make_path("sweep"),
            json=json_data
        )
        resp.raise_for_status()
        return int(resp.json()["swept_count"])

    class Provider(Resource):
        """Provider-level session resource (/sessions/{provider})."""

        def get(self, code: str) -> campus.model.AuthSession:
            """Get a session using authorization code."""
            resp = self.client.post(
                self.make_path(),
                json={"code": code}
            )
            resp.raise_for_status()
            return campus.model.AuthSession.from_resource(resp.json())

        def new(
                self,
                *,
                expiry_seconds: int,
                user_id: str | None = None,
                redirect_uri: str,
                scopes: list[str],
                state: str,
                target: str,
        ) -> campus.model.AuthSession:
            client_id = env.CLIENT_ID
            json_data: JsonDict = {
                "expiry_seconds": expiry_seconds,
                "client_id": str(client_id),
                "redirect_uri": redirect_uri,
                "scopes": scopes,
                "state": state,
                "target": target,
            }
            if user_id is not None:
                json_data["user_id"] = str(user_id)
            resp = self.client.post(self.make_path(), json=json_data)
            resp.raise_for_status()
            return campus.model.AuthSession.from_resource(resp.json())

        def __getitem__(self, session_id: str) -> "Sessions.Provider.Session":
            return Sessions.Provider.Session(session_id, parent=self)

        class Session(Resource):
            """A single provider session (/sessions/{provider}/{session_id})."""

            def finalize(self) -> str:
                # DELETE /sessions/{provider}/{session_id} -> {"redirect_uri": <url>}
                resp = self.client.delete(self.make_path())
                resp.raise_for_status()
                body = resp.json()
                return body["redirect_uri"]

            def get(self) -> campus.model.AuthSession:
                resp = self.client.get(self.make_path())
                resp.raise_for_status()
                return campus.model.AuthSession.from_resource(resp.json())

            def update(self, **updates) -> None:
                # Only user_id and authorization_code are expected by the API
                resp = self.client.patch(self.make_path(), json=updates)
                resp.raise_for_status()
                return None
