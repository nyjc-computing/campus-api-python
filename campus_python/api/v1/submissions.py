"""campus_python.api.v1.submissions

Campus API submissions resource (v1).
"""

from typing import Any

import campus.model

from ...interface import Resource, ResourceCollection


class Submissions(ResourceCollection):
    """Campus API Submissions resource."""
    path = "submissions"

    def __getitem__(self, submission_id: str) -> "Submissions.Submission":
        """Get a specific submission resource by ID."""
        return Submissions.Submission(submission_id, parent=self)

    def list(
            self,
            *,
            assignment_id: "str | None" = None,
            student_id: "str | None" = None,
            course_id: "str | None" = None,
    ) -> "list[campus.model.Submission]":
        """List all submissions matching filter requirements.

        Args:
            assignment_id: Filter by assignment
            student_id: Filter by student
            course_id: Filter by Google Classroom course

        Returns:
            List of Submission objects
        """
        query = {}
        if assignment_id:
            query["assignment_id"] = assignment_id
        if student_id:
            query["student_id"] = student_id
        if course_id:
            query["course_id"] = course_id

        body = self._get_json(self.make_path(), query=query)
        return [
            campus.model.Submission.from_resource(item)
            for item in body["data"]
        ]

    def by_assignment(self, assignment_id: str) -> "list[campus.model.Submission]":
        """List submissions for a specific assignment.

        Args:
            assignment_id: Assignment ID

        Returns:
            List of Submission objects
        """
        path = self.make_path(f"by-assignment/{assignment_id}")
        body = self._get_json(path)
        return [
            campus.model.Submission.from_resource(item)
            for item in body["data"]
        ]

    def by_student(self, student_id: str) -> "list[campus.model.Submission]":
        """List submissions from a specific student.

        Args:
            student_id: Student user ID

        Returns:
            List of Submission objects
        """
        path = self.make_path(f"by-student/{student_id}")
        body = self._get_json(path)
        return [
            campus.model.Submission.from_resource(item)
            for item in body["data"]
        ]

    def new(
            self,
            *,
            assignment_id: str,
            student_id: str,
            course_id: str,
            responses: "list[dict] | None" = None,
    ) -> campus.model.Submission:
        """Create a new submission.

        Args:
            assignment_id: Assignment ID
            student_id: Student user ID
            course_id: Google Classroom course ID
            responses: List of response dictionaries

        Returns:
            Created Submission object
        """
        payload: dict[str, Any] = {
            "assignment_id": assignment_id,
            "student_id": student_id,
            "course_id": course_id,
        }
        if responses is not None:
            payload["responses"] = responses

        return campus.model.Submission.from_resource(
            self._post_json(self.make_path(), json=payload)
        )

    class Submission(Resource):
        """Single campus API submission resource."""

        @property
        def responses(self) -> "Submissions.Submission.Responses":
            """Get the responses resource for this submission."""
            return Submissions.Submission.Responses("responses", parent=self)

        @property
        def feedback(self) -> "Submissions.Submission.Feedback":
            """Get the feedback resource for this submission."""
            return Submissions.Submission.Feedback("feedback", parent=self)

        def delete(self) -> None:
            """Delete this submission."""
            self._delete_json(self.make_path(end_slash=True))

        def get(self) -> campus.model.Submission:
            """Get this submission."""
            body = self._get_json(self.make_path(end_slash=True))
            return campus.model.Submission.from_resource(body)

        def update(
                self,
                *,
                responses: "list[dict] | None" = None,
                feedback: "list[dict] | None" = None,
                submitted_at: "str | None" = None,
        ) -> None:
            """Update this submission.

            All parameters are optional. Only provided fields will be updated.

            Args:
                responses: New list of responses
                feedback: New list of feedback
                submitted_at: New submitted_at timestamp
            """
            payload = {}
            if responses is not None:
                payload["responses"] = responses
            if feedback is not None:
                payload["feedback"] = feedback
            if submitted_at is not None:
                payload["submitted_at"] = submitted_at

            if not payload:
                raise ValueError("At least one field must be provided for update")

            self._patch_json(self.make_path(end_slash=True), json=payload)
            return None

        def submit(self) -> None:
            """Finalize/submit this submission (marks submitted_at timestamp)."""
            path = self.make_path("submit", end_slash=False)
            self._post_json(path)
            return None

        def unsubmit(self) -> None:
            """Clear this submission's submitted_at timestamp.

            The server only clears submitted_at for an explicit null in
            the PATCH body; update() cannot express that because None
            means "omit the field" there.
            """
            self._patch_json(
                self.make_path(end_slash=True), json={"submitted_at": None}
            )
            return None

        class Responses(Resource):
            """Campus API Submission Responses resource."""

            def add(
                    self,
                    *,
                    question_id: str,
                    response_text: str,
            ) -> None:
                """Add or update a response to a question.

                Args:
                    question_id: Question ID
                    response_text: Student's response text
                """
                payload = {
                    "question_id": question_id,
                    "response_text": response_text,
                }
                self._post_json(self.make_path(), json=payload)
                return None

        class Feedback(Resource):
            """Campus API Submission Feedback resource."""

            def add(
                    self,
                    *,
                    question_id: str,
                    feedback_text: str,
            ) -> None:
                """Add feedback on a response to a question.

                Args:
                    question_id: Question ID
                    feedback_text: Teacher's feedback text
                """
                payload = {
                    "question_id": question_id,
                    "feedback_text": feedback_text,
                }
                self._post_json(self.make_path(), json=payload)
                return None
