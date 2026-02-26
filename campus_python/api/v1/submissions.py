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

        resp = self.client.get(self.make_path(), query=query)
        resp.raise_for_status()
        return [
            campus.model.Submission.from_resource(item)
            for item in resp.json()["data"]
        ]

    def by_assignment(self, assignment_id: str) -> "list[campus.model.Submission]":
        """List submissions for a specific assignment.

        Args:
            assignment_id: Assignment ID

        Returns:
            List of Submission objects
        """
        path = f"{self.make_path()}/by-assignment/{assignment_id}"
        resp = self.client.get(path)
        resp.raise_for_status()
        return [
            campus.model.Submission.from_resource(item)
            for item in resp.json()["data"]
        ]

    def by_student(self, student_id: str) -> "list[campus.model.Submission]":
        """List submissions from a specific student.

        Args:
            student_id: Student user ID

        Returns:
            List of Submission objects
        """
        path = f"{self.make_path()}/by-student/{student_id}"
        resp = self.client.get(path)
        resp.raise_for_status()
        return [
            campus.model.Submission.from_resource(item)
            for item in resp.json()["data"]
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

        resp = self.client.post(self.make_path(), json=payload)
        resp.raise_for_status()
        return campus.model.Submission.from_resource(resp.json())

    class Submission(Resource):
        """Single campus API submission resource."""

        @property
        def responses(self) -> "Submissions.Submission.Responses":
            """Get the responses resource for this submission."""
            return Submissions.Submission.Responses(parent=self)

        @property
        def feedback(self) -> "Submissions.Submission.Feedback":
            """Get the feedback resource for this submission."""
            return Submissions.Submission.Feedback(parent=self)

        def delete(self) -> None:
            """Delete this submission."""
            resp = self.client.delete(self.make_path())
            resp.raise_for_status()
            return None

        def get(self) -> campus.model.Submission:
            """Get this submission."""
            resp = self.client.get(self.make_path())
            resp.raise_for_status()
            return campus.model.Submission.from_resource(resp.json())

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

            resp = self.client.patch(self.make_path(), json=payload)
            resp.raise_for_status()
            return None

        def submit(self) -> None:
            """Finalize/submit this submission (marks submitted_at timestamp)."""
            path = f"{self.make_path()}/submit"
            resp = self.client.post(path)
            resp.raise_for_status()
            return None

        class Responses(Resource):
            """Campus API Submission Responses resource."""
            path = "responses"

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
                resp = self.client.post(self.make_path(), json=payload)
                resp.raise_for_status()
                return None

        class Feedback(Resource):
            """Campus API Submission Feedback resource."""
            path = "feedback"

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
                resp = self.client.post(self.make_path(), json=payload)
                resp.raise_for_status()
                return None
