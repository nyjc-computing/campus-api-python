"""campus.python.auth.v1.sessions

Campus Auth sessions resource (v1).
"""

from datetime import datetime

import flask

from campus.common import env, schema
import campus.model

from ...interface import JsonDict, Resource, ResourceCollection

PROVIDER = "campus"


class CampusSessions(ResourceCollection):
    """Campus Auth Sessions resource."""
    path = f"sessions/{PROVIDER}"

    @property
    def _session_key(self) -> str:
        provider = self.path.split("/")[-1]
        return f"{provider}_session_id"

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
        authsession = campus.model.AuthSession.from_resource(resp.json())
        flask.session[self._session_key] = authsession.id
        return campus.model.AuthSession.from_resource(resp.json())

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
        resp = self.client.post(self.make_path("sweep"), json=json_data)
        resp.raise_for_status()
        return int(resp.json()["swept_count"])

    def __getitem__(self, session_id: str) -> "CampusSessions.Session":
        return CampusSessions.Session(session_id, parent=self)

    class Session(Resource):
        """A single provider session (/sessions/campus/{session_id})."""

        @property
        def session_id(self) -> str:
            return self.path.split("/")[-1]

        def finalize(self) -> str:
            # DELETE /sessions/{provider}/{session_id} -> {"target": <url>}
            resp = self.client.delete(self.make_path())
            resp.raise_for_status()
            del flask.session[self.session_id]
            body = resp.json()
            return body["target"]

        def get(self) -> campus.model.AuthSession:
            resp = self.client.get(self.make_path())
            resp.raise_for_status()
            return campus.model.AuthSession.from_resource(resp.json())

        def update(self, **updates) -> None:
            # Only user_id and authorization_code are expected by the API
            resp = self.client.patch(self.make_path(), json=updates)
            resp.raise_for_status()
            return None
