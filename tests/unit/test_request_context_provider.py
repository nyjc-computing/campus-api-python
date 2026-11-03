"""Unit tests for the injectable request-context provider (tracing).

Hosts that own their own request state (flask_campus) install a
provider that supplies the request-context half of propagation
themselves. Contract: the provider returns the in-request headers
(dict, possibly empty) or None when there is no active request
context — only then does the SDK apply the process boot journey.
The SDK itself is framework-free: these tests drive the provider
seam directly, with no flask involved.
"""

import os
import unittest

from campus_python import tracing
from campus_python.tracing import (
    DEVICE_ID_HEADER,
    JOURNEY_ID_HEADER,
    JOURNEY_NAME_HEADER,
    PARENT_SPAN_ID_HEADER,
    TRACE_ID_HEADER,
    propagation_headers,
    set_request_context_provider,
)

TRACE_ID = "a" * 32
SPAN_ID = "b" * 16


class TestRequestContextProvider(unittest.TestCase):
    """set_request_context_provider owns the request-context half."""

    def setUp(self):
        tracing._reset_process_journey()

    def tearDown(self):
        set_request_context_provider(None)
        tracing._reset_process_journey()

    def test_provider_output_used_verbatim(self):
        """The provider's headers are taken verbatim — the SDK adds
        nothing."""
        set_request_context_provider(
            lambda: {
                TRACE_ID_HEADER: TRACE_ID,
                PARENT_SPAN_ID_HEADER: SPAN_ID,
                JOURNEY_ID_HEADER: "uid-journey-provider",
            }
        )
        self.assertEqual(
            propagation_headers(),
            {
                TRACE_ID_HEADER: TRACE_ID,
                PARENT_SPAN_ID_HEADER: SPAN_ID,
                JOURNEY_ID_HEADER: "uid-journey-provider",
            },
        )

    def test_provider_none_applies_boot_journey(self):
        """None = no active request context: the SDK fills in the boot
        journey (#114) and nothing else."""
        tracing.set_process_journey("uid-journey-boot", name="boot")
        set_request_context_provider(lambda: None)
        headers = propagation_headers()
        self.assertEqual(headers[JOURNEY_ID_HEADER], "uid-journey-boot")
        self.assertEqual(headers[JOURNEY_NAME_HEADER], "boot")
        self.assertNotIn(TRACE_ID_HEADER, headers)

    def test_provider_empty_dict_stays_unjourneyed(self):
        """An empty dict = in-request but journey-less: strict MVP keeps
        it unjourneyed — no boot-journey leakage."""
        tracing.set_process_journey("uid-journey-boot")
        set_request_context_provider(lambda: {})
        self.assertEqual(propagation_headers(), {})

    def test_uninstall_reverts_to_boot_journey_only(self):
        """No provider = no request-context half: headers are
        boot-journey-only (the former built-in flask reader is gone;
        flask_campus installs the provider)."""
        set_request_context_provider(None)
        headers = propagation_headers()
        self.assertNotIn(TRACE_ID_HEADER, headers)
        self.assertNotIn(PARENT_SPAN_ID_HEADER, headers)

    def test_no_provider_no_trace_headers_without_context(self):
        """Without a provider there are no trace headers, period."""
        headers = propagation_headers()
        self.assertNotIn(TRACE_ID_HEADER, headers)
        self.assertNotIn(PARENT_SPAN_ID_HEADER, headers)


class TestProcessDeviceAccessor(unittest.TestCase):
    """tracing.process_device() exposes the gap-fill device publicly."""

    def setUp(self):
        self.saved = os.environ.get("RAILWAY_DEPLOYMENT_ID")
        tracing._reset_process_journey()

    def tearDown(self):
        if self.saved is None:
            os.environ.pop("RAILWAY_DEPLOYMENT_ID", None)
        else:
            os.environ["RAILWAY_DEPLOYMENT_ID"] = self.saved
        tracing._reset_process_journey()

    def test_process_device_reads_env(self):
        os.environ["RAILWAY_DEPLOYMENT_ID"] = "deploy-abc"
        self.assertEqual(tracing.process_device(), "deploy-abc")

    def test_process_device_unset_is_none(self):
        os.environ.pop("RAILWAY_DEPLOYMENT_ID", None)
        self.assertIsNone(tracing.process_device())

    def test_process_device_never_mints_journey(self):
        """Reading the device must not mint the boot journey (#114:
        hosts that only read the device never mint)."""
        tracing.process_device()
        self.assertIsNone(tracing._process_state["journey_id"])


if __name__ == "__main__":
    unittest.main()
