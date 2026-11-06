"""Unit tests for the subjcombi resource (campus#592, SDK slice 4).

Path/method contracts against the mock JSON client: PUT per-user set,
current view (+at), history, pending, and pending-record cancel.
"""

import unittest

from tests.support import make_api


class TestSubjcombiSet(unittest.TestCase):
    def setUp(self):
        self.api, self.client = make_api()

    def test_set_put_user_path_with_payload(self):
        self.client.put.return_value.json.return_value = {"id": "uid-subjcombi-1"}
        record = self.api.subjcombi.set(
            "student@campus.test",
            "uid-lessongroup-1",
            effective_from="2027-06-01",
            reason="transfer",
        )
        self.client.put.assert_called_once_with(
            "/api/v1/subjcombi/student@campus.test",
            json={
                "lessongroup_id": "uid-lessongroup-1",
                "effective_from": "2027-06-01",
                "reason": "transfer",
            },
        )
        self.assertEqual(record["id"], "uid-subjcombi-1")

    def test_set_immediate_omits_optional_fields(self):
        self.client.put.return_value.json.return_value = {"id": "uid-subjcombi-2"}
        self.api.subjcombi.set("student@campus.test", "uid-lessongroup-1")
        self.client.put.assert_called_once_with(
            "/api/v1/subjcombi/student@campus.test",
            json={"lessongroup_id": "uid-lessongroup-1"},
        )


class TestSubjcombiViews(unittest.TestCase):
    def setUp(self):
        self.api, self.client = make_api()

    def test_get_current_with_at_query(self):
        self.client.get.return_value.json.return_value = {
            "user_id": "student@campus.test",
            "lessongroup_id": "uid-lessongroup-1",
            "source": "mapping",
        }
        view = self.api.subjcombi["student@campus.test"].get(at="2027-06-02T00:00:00Z")
        self.client.get.assert_called_once_with(
            "/api/v1/subjcombi/student@campus.test",
            query={"at": "2027-06-02T00:00:00Z"},
        )
        self.assertEqual(view["source"], "mapping")

    def test_get_current_without_at_omits_query(self):
        self.client.get.return_value.json.return_value = {
            "user_id": "student@campus.test",
            "lessongroup_id": None,
            "source": "unmapped",
        }
        self.api.subjcombi["student@campus.test"].get()
        self.client.get.assert_called_once_with(
            "/api/v1/subjcombi/student@campus.test"
        )

    def test_history_unwraps_data_envelope(self):
        self.client.get.return_value.json.return_value = {"data": [{"id": "r1"}]}
        history = self.api.subjcombi["student@campus.test"].history()
        self.client.get.assert_called_once_with(
            "/api/v1/subjcombi/student@campus.test/history"
        )
        self.assertEqual(history, [{"id": "r1"}])

    def test_pending_unwraps_data_envelope(self):
        self.client.get.return_value.json.return_value = {"data": [{"id": "r2"}]}
        pending = self.api.subjcombi.pending()
        self.client.get.assert_called_once_with("/api/v1/subjcombi/pending")
        self.assertEqual(pending, [{"id": "r2"}])

    def test_cancel_deletes_pending_record(self):
        self.client.delete.return_value.json.return_value = {
            "id": "uid-subjcombi-3",
            "cancelled_at": "2026-11-06T00:00:00+00:00",
        }
        cancelled = self.api.subjcombi.cancel("uid-subjcombi-3")
        self.client.delete.assert_called_once_with(
            "/api/v1/subjcombi/pending/uid-subjcombi-3"
        )
        self.assertIsNotNone(cancelled["cancelled_at"])


class TestTimetablePointerRework(unittest.TestCase):
    """view/patch/cancel_next/me replace the retired current/next verbs."""

    def setUp(self):
        self.api, self.client = make_api()

    def test_view_gets_pointer_state(self):
        self.client.get.return_value.json.return_value = {
            "current": "uid-timetable-1",
            "next": None,
            "effective_from": None,
        }
        state = self.api.timetable.view()
        self.client.get.assert_called_once_with("/api/v1/timetable/")
        self.assertEqual(state["current"], "uid-timetable-1")

    def test_patch_current(self):
        self.client.patch.return_value.json.return_value = {
            "current": "uid-timetable-2", "next": None, "effective_from": None,
        }
        self.api.timetable.patch(current="uid-timetable-2")
        self.client.patch.assert_called_once_with(
            "/api/v1/timetable/", json={"current": "uid-timetable-2"}
        )

    def test_patch_next_with_effective_from(self):
        self.api.timetable.patch(next="uid-timetable-2", effective_from="2027-06-01")
        self.client.patch.assert_called_once_with(
            "/api/v1/timetable/",
            json={"next": "uid-timetable-2", "effective_from": "2027-06-01"},
        )

    def test_patch_rejects_both_pointers(self):
        with self.assertRaises(ValueError):
            self.api.timetable.patch(
                current="uid-timetable-1", next="uid-timetable-2"
            )

    def test_cancel_next_patches_null(self):
        self.api.timetable.cancel_next()
        self.client.patch.assert_called_once_with(
            "/api/v1/timetable/", json={"next": None}
        )

    def test_me_gets_resolved_view(self):
        self.client.get.return_value.json.return_value = {
            "current": {"timetable_id": "t1", "lessongroup_id": "l1",
                        "source": "roster"},
            "next": None,
        }
        view = self.api.timetable.me()
        self.client.get.assert_called_once_with("/api/v1/timetable/me")
        self.assertEqual(view["current"]["source"], "roster")
