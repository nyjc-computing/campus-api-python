"""Regression tests for nested resource paths (issue #38).

Nested resources must be constructed with their path part so that their
paths extend the parent resource's path instead of collapsing onto it.

The expected request paths mirror the Campus API routes defined in the
campus-suite repository (branch: weekly):
- POST /api/v1/submissions/<id>/responses
- POST /api/v1/submissions/<id>/feedback
- POST /api/v1/submissions/<id>/submit
- POST /api/v1/assignments/<id>/links
- GET  /api/v1/timetable/<id>/entries
- GET  /api/v1/timetable/<id>/metadata
- GET  /api/v1/circles/<id>/members
"""

import unittest
from unittest.mock import Mock, patch

import campus.model

from campus_python.api.v1 import ApiRoot


def make_api() -> tuple[ApiRoot, Mock]:
    """Create an ApiRoot backed by a mock JSON client."""
    client = Mock()
    return ApiRoot(json_client=client), client


class TestNestedResourcePaths(unittest.TestCase):
    """Nested resource paths must include their own path part."""

    def setUp(self):
        self.api, _ = make_api()

    def test_submission_responses_path(self):
        responses = self.api.submissions["sub-1"].responses
        self.assertEqual(
            responses.make_path(), "/api/v1/submissions/sub-1/responses"
        )

    def test_submission_feedback_path(self):
        feedback = self.api.submissions["sub-1"].feedback
        self.assertEqual(
            feedback.make_path(), "/api/v1/submissions/sub-1/feedback"
        )

    def test_assignment_links_path(self):
        links = self.api.assignments["asg-1"].links
        self.assertEqual(links.make_path(), "/api/v1/assignments/asg-1/links")

    def test_timetable_entries_path(self):
        entries = self.api.timetable["tt-1"].entries
        self.assertEqual(entries.make_path(), "/api/v1/timetable/tt-1/entries")

    def test_timetable_metadata_path(self):
        metadata = self.api.timetable["tt-1"].metadata
        self.assertEqual(metadata.make_path(), "/api/v1/timetable/tt-1/metadata")

    def test_circle_members_path(self):
        members = self.api.circles["cir-1"].members
        self.assertEqual(members.make_path(), "/api/v1/circles/cir-1/members")

    def test_nested_paths_extend_parent_path(self):
        """A nested resource path must not collapse onto its parent's path."""
        submission = self.api.submissions["sub-1"]
        for child in (submission.responses, submission.feedback):
            self.assertTrue(child.make_path().startswith(submission.make_path()))
            self.assertNotEqual(child.make_path(), submission.make_path())

        assignment = self.api.assignments["asg-1"]
        self.assertTrue(assignment.links.make_path().startswith(assignment.make_path()))
        self.assertNotEqual(assignment.links.make_path(), assignment.make_path())

        timetable = self.api.timetable["tt-1"]
        for child in (timetable.entries, timetable.metadata):
            self.assertTrue(child.make_path().startswith(timetable.make_path()))
            self.assertNotEqual(child.make_path(), timetable.make_path())

        circle = self.api.circles["cir-1"]
        self.assertTrue(circle.members.make_path().startswith(circle.make_path()))
        self.assertNotEqual(circle.members.make_path(), circle.make_path())


class TestNestedResourceRequests(unittest.TestCase):
    """Nested resource methods must request their own API endpoints."""

    def setUp(self):
        self.api, self.client = make_api()

    def test_responses_add_posts_to_responses_endpoint(self):
        self.api.submissions["sub-1"].responses.add(
            question_id="q-1", response_text="answer"
        )
        self.client.post.assert_called_once_with(
            "/api/v1/submissions/sub-1/responses",
            json={"question_id": "q-1", "response_text": "answer"},
        )

    def test_feedback_add_posts_to_feedback_endpoint(self):
        self.api.submissions["sub-1"].feedback.add(
            question_id="q-1", feedback_text="good"
        )
        self.client.post.assert_called_once_with(
            "/api/v1/submissions/sub-1/feedback",
            json={"question_id": "q-1", "feedback_text": "good"},
        )

    def test_submit_posts_to_submit_endpoint(self):
        self.api.submissions["sub-1"].submit()
        self.client.post.assert_called_once_with(
            "/api/v1/submissions/sub-1/submit"
        )

    def test_links_add_posts_to_links_endpoint(self):
        self.api.assignments["asg-1"].links.add(
            course_id="course-1", coursework_id="cw-1"
        )
        self.client.post.assert_called_once_with(
            "/api/v1/assignments/asg-1/links",
            json={"course_id": "course-1", "coursework_id": "cw-1"},
        )

    def test_entries_list_gets_entries_endpoint(self):
        self.client.get.return_value.json.return_value = {"entries": []}
        self.api.timetable["tt-1"].entries.list()
        self.client.get.assert_called_once_with(
            "/api/v1/timetable/tt-1/entries"
        )

    def test_metadata_get_gets_metadata_endpoint(self):
        with patch.object(
            campus.model.Timetable, "from_resource", return_value=Mock()
        ):
            self.api.timetable["tt-1"].metadata.get()
        self.client.get.assert_called_once_with(
            "/api/v1/timetable/tt-1/metadata"
        )

    def test_members_list_gets_members_endpoint(self):
        self.client.get.return_value.json.return_value = {"members": {}}
        self.api.circles["cir-1"].members.list()
        self.client.get.assert_called_once_with(
            "/api/v1/circles/cir-1/members"
        )

    def test_assignments_list_passes_query_argument(self):
        """Assignments.list must pass filters via the client's query argument."""
        self.client.get.return_value.json.return_value = {"data": []}
        self.api.assignments.list(created_by="teacher-1")
        self.client.get.assert_called_once_with(
            "/api/v1/assignments/", query={"created_by": "teacher-1"}
        )


if __name__ == "__main__":
    unittest.main()
