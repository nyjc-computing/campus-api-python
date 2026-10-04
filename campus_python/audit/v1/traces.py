"""campus.python.audit.v1.traces

Campus Audit traces resource (v1).

Span ingestion and trace queries. Traces are addressed by their 32-char
hex trace ID and spans by their 16-char hex span ID.
"""

from typing import Any

from ...interface import JsonDict, Resource, ResourceCollection


class Traces(ResourceCollection):
    """Campus Audit traces resource."""
    path = "traces/"

    def __getitem__(self, trace_id: str) -> "Traces.Trace":
        """Get a specific trace resource by ID."""
        return Traces.Trace(trace_id, parent=self)

    def ingest(self, spans: "list[dict[str, Any]]") -> JsonDict:
        """Ingest a batch of trace spans.

        Args:
            spans: Span dicts shaped like the server's TraceSpan
                resource (trace_id, span_id, method, path, ...)

        Returns:
            201 full success: {"created": [...]}; 207 partial failure
            adds {"failed": [...]} with per-span statuses.
        """
        resp = self.client.post(self.make_path(), json={"spans": spans})
        resp.raise_for_status()
        return resp.json()

    def list(
            self,
            *,
            since: "str | None" = None,
            until: "str | None" = None,
            limit: "int | None" = None,
            cursor: "str | None" = None,
    ) -> JsonDict:
        """List recent traces, newest first.

        Args:
            since: ISO 8601 lower bound
            until: ISO 8601 upper bound
            limit: Page size (server clamps to its max)
            cursor: Opaque token from a previous page's cursor.next

        Returns:
            {"traces": [...], "cursor": {"next": ..., "has_more": bool}}
        """
        query: JsonDict = {}
        if since is not None:
            query["since"] = since
        if until is not None:
            query["until"] = until
        if limit is not None:
            query["limit"] = limit
        if cursor is not None:
            query["cursor"] = cursor
        resp = self.client.get(
            self.make_path(), query=query or None
        )
        resp.raise_for_status()
        return resp.json()

    def search(
            self,
            *,
            path: "str | None" = None,
            status: "int | str | None" = None,
            api_key_id: "str | None" = None,
            client_id: "str | None" = None,
            user_id: "str | None" = None,
            since: "str | None" = None,
            until: "str | None" = None,
            limit: "int | None" = None,
            cursor: "str | None" = None,
    ) -> JsonDict:
        """Filter and search traces.

        Args:
            path: Filter by endpoint path
            status: Filter by HTTP status code
            api_key_id: Filter by audit API key
            client_id: Filter by OAuth client
            user_id: Filter by user
            since, until, limit, cursor: As in list()

        Returns:
            {"traces": [...], "cursor": {"next": ..., "has_more": bool}}
        """
        query: JsonDict = {}
        if path is not None:
            query["path"] = path
        if status is not None:
            query["status"] = status
        if api_key_id is not None:
            query["api_key_id"] = api_key_id
        if client_id is not None:
            query["client_id"] = client_id
        if user_id is not None:
            query["user_id"] = user_id
        if since is not None:
            query["since"] = since
        if until is not None:
            query["until"] = until
        if limit is not None:
            query["limit"] = limit
        if cursor is not None:
            query["cursor"] = cursor
        resp = self.client.get(
            self.make_path("search", end_slash=False), query=query or None
        )
        resp.raise_for_status()
        return resp.json()

    class Trace(Resource):
        """Single campus audit trace resource."""

        @property
        def spans(self) -> "Traces.Trace.Spans":
            """Get the spans resource for this trace."""
            return Traces.Trace.Spans("spans", parent=self)

        def get(self) -> JsonDict:
            """Get the full trace tree.

            Returns:
                {"trace_id": ..., "root_span": <nested span tree>}
            """
            resp = self.client.get(self.make_path(end_slash=True))
            resp.raise_for_status()
            return resp.json()

        class Spans(Resource):
            """Spans of a single trace."""

            def __getitem__(self, span_id: str) -> "Traces.Trace.Span":
                """Get a specific span resource by ID."""
                return Traces.Trace.Span(span_id, parent=self)

            def list(self) -> "list[JsonDict]":
                """List all spans in this trace (flat)."""
                resp = self.client.get(self.make_path(end_slash=True))
                resp.raise_for_status()
                return resp.json()["spans"]

        class Span(Resource):
            """Single span of a trace, with full request/response detail."""

            def get(self) -> JsonDict:
                resp = self.client.get(self.make_path(end_slash=True))
                resp.raise_for_status()
                return resp.json()
