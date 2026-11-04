"""campus.python.auth.v1.sessions

Campus Auth sessions resource (v1).
"""

from datetime import datetime

from campus.common import env, schema
import campus.model

from ... import errors
from ...interface import JsonDict, Resource, ResourceCollection
from . import sessionstore

PROVIDER = "campus"

# Client-side storage key for this resource's session id. The SDK does
# not touch any web-framework session store; hosts that keep the id in
# their own request state (flask_campus) use this key, and install a
# session-id provider (set_session_id_provider) so the resources below
# resolve ids without an explicit argument.
SESSION_STORAGE_KEY = "campus_session_id"


class CampusSessions(ResourceCollection):
    """Campus Auth Sessions resource."""
    path = f"sessions/{PROVIDER}/"

    def __getitem__(self, session_id: str) -> "CampusSessions.Session":
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
        """Get a session by its client-side session id.

        Resolution order: explicit session_id > the installed
        session-id provider. There is no framework fallback: hosts
        without a provider must pass the id explicitly.
        """
        if session_id is None:
            session_id = sessionstore.resolve_session_id(
                sessionstore.LANE_SESSION
            )
        if not session_id:
            raise errors.AuthenticationError(
                error_description=(
                    "No session id available: pass session_id or "
                    "install a session-id provider "
                    "(campus_python.auth.v1.set_session_id_provider)."
                )
            )
        return CampusSessions.Session(session_id, parent=self).get()

    def has_session(self) -> bool:
        """True when the installed session-id provider supplies a
        session id for this lane."""
        return bool(sessionstore.resolve_session_id(sessionstore.LANE_SESSION))

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
        # The returned session id doubles as the OAuth state parameter;
        # storing it client-side is the host's business (flask_campus
        # context owns its flask.session storage).
        return campus.model.AuthSession.from_resource(resp.json())

    def list(
            self,
            *,
            provider: str | None = PROVIDER,
            client_id: str | None = None,
            user_id: str | None = None,
            limit: int | None = None,
            offset: int | None = None,
    ) -> "list[campus.model.AuthSession]":
        """List live sessions (admin view, campus#1055).

        GET /sessions/ with optional provider/client_id/user_id
        filters and limit/offset pagination. Requires the operator
        principal or a designated admin user (sessions:read); client
        principals are denied. Records carry metadata only — no
        authorization_code, no user embeds — and finalized sessions
        are absent (finalize deletes the record).
        """
        query: JsonDict = {}
        if provider is not None:
            query["provider"] = provider
        if client_id is not None:
            query["client_id"] = client_id
        if user_id is not None:
            query["user_id"] = str(user_id)
        if limit is not None:
            query["limit"] = limit
        if offset is not None:
            query["offset"] = offset
        # The list route is provider-agnostic (/sessions/), unlike the
        # campus-provider path this collection wraps.
        collection_path = f"/{self.root.make_path('sessions').strip('/')}/"
        resp = self.client.get(collection_path, query=query)
        resp.raise_for_status()
        return [
            campus.model.AuthSession.from_resource(item)
            for item in resp.json().get("sessions", [])
        ]

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
            return self.path.rstrip("/").split("/")[-1]

        def finalize(self) -> "tuple[str, campus.model.User | None]":
            # DELETE /sessions/{provider}/{session_id} ->
            # {"target": <url>, "user": {...}|null}
            resp = self.client.delete(
                self.make_path(end_slash=True)
            )
            resp.raise_for_status()
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
