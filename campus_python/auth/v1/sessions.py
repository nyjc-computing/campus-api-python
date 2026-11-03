"""campus.python.auth.v1.sessions

Campus Auth sessions resource (v1).
"""

from datetime import datetime
from typing import cast

import flask

from campus.common import env, schema
import campus.model

from ...interface import JsonDict, Resource, ResourceCollection
from . import sessionstore

PROVIDER = "campus"

# flask.session key this resource historically reads/writes its id in.
# Hosts that own their own storage (flask_campus) use this key too, so
# both paths stay consistent during the provider-seam rollout.
SESSION_STORAGE_KEY = "campus_session_id"


class CampusSessions(ResourceCollection):
    """Campus Auth Sessions resource."""
    path = f"sessions/{PROVIDER}/"

    @property
    def _session_key(self) -> str:
        provider = self.path.rstrip("/").split("/")[-1]
        return f"{provider}_session_id"

    def __getitem__(self, session_id: str) -> "CampusSessions.Session":
        # Use the provided session_id parameter, not Flask session
        return CampusSessions.Session(session_id, parent=self)

    def from_code(self, code: str) -> campus.model.AuthSession:
        """Get a session using authorization code."""
        resp = self.client.post(
            self.make_path("authorization_code", end_slash=False),
            json={"code": code}
        )
        resp.raise_for_status()
        return campus.model.AuthSession.from_resource(resp.json())

    def from_session(self, session_id: str | None = None) -> campus.model.AuthSession:
        """Get a session from a client-side session id.

        Resolution order: explicit session_id > the installed
        session-id provider > the legacy flask.session read.
        """
        if session_id is None:
            session_id = sessionstore.resolve_session_id(
                sessionstore.LANE_SESSION
            )
        if session_id is None:
            session_id = cast(
                str, flask.session[self._session_key]
            )
        return CampusSessions.Session(session_id, parent=self).get()

    def has_session(self) -> bool:
        """Check if a session id is resolvable for the current context.

        True when the installed session-id provider supplies one, or
        (legacy lane) when the flask.session carries the storage key.
        """
        if sessionstore.resolve_session_id(sessionstore.LANE_SESSION):
            return True
        return self._session_key in flask.session

    def new(
            self,
            *,
            # expiry_seconds: int,
            user_id: str | None = None,
            redirect_uri: str,
            scopes: "list[str]",
            target: str | None = None,
    ) -> campus.model.AuthSession:
        client_id = env.CLIENT_ID
        json_data: JsonDict = {
            # "expiry_seconds": expiry_seconds,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scopes": scopes,
        }
        if target is not None:
            json_data["target"] = target
        if user_id is not None:
            json_data["user_id"] = str(user_id)
        resp = self.client.post(self.make_path(), json=json_data)
        resp.raise_for_status()
        # session_id is used as state parameter and stored in session
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
        resp = self.client.post(self.make_path("sweep", end_slash=False), json=json_data)
        resp.raise_for_status()
        return int(resp.json()["swept_count"])

    class Session(Resource):
        """A single provider session (/sessions/campus/{session_id})."""

        @property
        def session_id(self) -> str:
            return self.path.split("/")[-1]

        def finalize(self) -> "tuple[str, campus.model.User | None]":
            # DELETE /sessions/{provider}/{session_id} ->
            # {"target": <url>, "user": {...}|null}
            resp = self.client.delete(
                self.make_path(end_slash=True)
            )
            resp.raise_for_status()
            # Remove session ID from Flask session using correct key.
            # The key may be absent (expired cookie, new worker, lost
            # session) — clearing it must not fail the finalization (#59).
            flask.session.pop(
                cast(CampusSessions, self.parent)._session_key, None
            )
            body = resp.json()
            # The auth service embeds the session user for the owning
            # client (#879); None from pre-#879 services.
            user = campus.model.User.from_resource(body["user"]) \
                if body.get("user") else None
            return body["target"], user

        def get(self) -> campus.model.AuthSession:
            resp = self.client.get(
                self.make_path(end_slash=True)
            )
            resp.raise_for_status()
            return campus.model.AuthSession.from_resource(resp.json())

        def update(self, **updates) -> None:
            # Only user_id and authorization_code are expected by the API
            resp = self.client.patch(
                self.make_path(end_slash=True),
                json=updates
            )
            resp.raise_for_status()
            return None
