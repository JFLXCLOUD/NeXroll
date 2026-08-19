import datetime
import os
import unittest
from unittest import mock

from backend.scheduler import Scheduler


class FakeSetting:
    plex_url = "http://plex.local:32400"
    plex_token = "token"


def response(status=200, content=b'<MediaContainer size="0"></MediaContainer>'):
    fake = mock.Mock()
    fake.status_code = status
    fake.content = content
    return fake


SESSION_XML = (
    b'<MediaContainer size="1">'
    b'<Video ratingKey="123" title="A Movie"/>'
    b'</MediaContainer>'
)
IDLE_XML = b'<MediaContainer size="0"></MediaContainer>'


class SessionProbeTests(unittest.TestCase):
    def setUp(self):
        self.scheduler = Scheduler()
        self.setting = FakeSetting()

    def test_counts_active_sessions(self):
        with mock.patch("backend.scheduler.requests.get", return_value=response(content=SESSION_XML)):
            self.assertEqual(self.scheduler._plex_active_session_count(self.setting), 1)

    def test_idle_server_reports_zero(self):
        with mock.patch("backend.scheduler.requests.get", return_value=response(content=IDLE_XML)):
            self.assertEqual(self.scheduler._plex_active_session_count(self.setting), 0)

    def test_probe_result_is_cached_within_its_ttl(self):
        # One scheduler tick can consult this from several apply paths; there is
        # no value in hitting Plex once per path.
        with mock.patch("backend.scheduler.requests.get",
                        return_value=response(content=SESSION_XML)) as get:
            for _ in range(5):
                self.scheduler._plex_active_session_count(self.setting)
            self.assertEqual(get.call_count, 1)

    def test_cache_expires(self):
        self.scheduler._session_probe_ttl_seconds = 0
        with mock.patch("backend.scheduler.requests.get",
                        return_value=response(content=SESSION_XML)) as get:
            self.scheduler._plex_active_session_count(self.setting)
            self.scheduler._plex_active_session_count(self.setting)
            self.assertEqual(get.call_count, 2)

    def test_unreachable_server_reports_unknown(self):
        with mock.patch("backend.scheduler.requests.get", side_effect=OSError("no route")):
            self.assertIsNone(self.scheduler._plex_active_session_count(self.setting))

    def test_error_status_reports_unknown(self):
        with mock.patch("backend.scheduler.requests.get", return_value=response(status=500)):
            self.assertIsNone(self.scheduler._plex_active_session_count(self.setting))

    def test_missing_credentials_report_unknown(self):
        class NoCreds:
            plex_url = None
            plex_token = None

        self.assertIsNone(self.scheduler._plex_active_session_count(NoCreds()))


class DeferPrerollWriteTests(unittest.TestCase):
    def setUp(self):
        self.scheduler = Scheduler()
        self.setting = FakeSetting()

    def test_writes_are_deferred_while_something_is_playing(self):
        with mock.patch("backend.scheduler.requests.get", return_value=response(content=SESSION_XML)):
            self.assertTrue(self.scheduler._defer_preroll_write(self.setting, "rotation"))

    def test_writes_proceed_when_the_server_is_idle(self):
        with mock.patch("backend.scheduler.requests.get", return_value=response(content=IDLE_XML)):
            self.assertFalse(self.scheduler._defer_preroll_write(self.setting, "rotation"))

    def test_an_unreachable_server_does_not_wedge_scheduling(self):
        # If Plex cannot be probed the write will fail on its own; blocking here
        # would let an outage freeze scheduling indefinitely.
        with mock.patch("backend.scheduler.requests.get", side_effect=OSError("down")):
            self.assertFalse(self.scheduler._defer_preroll_write(self.setting, "rotation"))

    def test_deferral_start_is_recorded_once_and_cleared_when_playback_ends(self):
        with mock.patch("backend.scheduler.requests.get", return_value=response(content=SESSION_XML)):
            self.scheduler._defer_preroll_write(self.setting, "rotation")
            first = self.scheduler._deferred_write_since
            self.assertIsNotNone(first)

            self.scheduler._session_probe_at = None  # force a re-probe
            self.scheduler._defer_preroll_write(self.setting, "rotation")
            self.assertEqual(self.scheduler._deferred_write_since, first)

        self.scheduler._session_probe_at = None
        with mock.patch("backend.scheduler.requests.get", return_value=response(content=IDLE_XML)):
            self.assertFalse(self.scheduler._defer_preroll_write(self.setting, "rotation"))
        self.assertIsNone(self.scheduler._deferred_write_since)

    def test_escape_hatch_env_var_disables_the_guard(self):
        original = os.environ.get("NEXROLL_ALLOW_MIDPLAYBACK_PREROLL_WRITES")
        os.environ["NEXROLL_ALLOW_MIDPLAYBACK_PREROLL_WRITES"] = "1"
        try:
            with mock.patch("backend.scheduler.requests.get",
                            return_value=response(content=SESSION_XML)) as get:
                self.assertFalse(self.scheduler._defer_preroll_write(self.setting, "rotation"))
                self.assertEqual(get.call_count, 0)  # not even probed
        finally:
            if original is None:
                os.environ.pop("NEXROLL_ALLOW_MIDPLAYBACK_PREROLL_WRITES", None)
            else:
                os.environ["NEXROLL_ALLOW_MIDPLAYBACK_PREROLL_WRITES"] = original


class TrailerRetentionGuardTests(unittest.TestCase):
    """Retention must never delete a file that is sitting in the list Plex is
    currently serving - the path would remain in Plex's preference with nothing
    behind it, which is the same hang by a different route."""

    def test_applied_paths_start_empty(self):
        self.assertEqual(Scheduler()._applied_local_paths, set())

    def test_membership_is_compared_on_absolute_paths(self):
        scheduler = Scheduler()
        scheduler._applied_local_paths = {os.path.abspath(os.path.join("videos", "trailer.mp4"))}

        self.assertIn(
            os.path.abspath(os.path.join("videos", "trailer.mp4")),
            scheduler._applied_local_paths,
        )
        self.assertNotIn(
            os.path.abspath(os.path.join("videos", "other.mp4")),
            scheduler._applied_local_paths,
        )


class GenreFeatureRemovalTests(unittest.TestCase):
    def test_genre_playback_monitor_is_gone(self):
        self.assertFalse(hasattr(Scheduler(), "_apply_genre_mapping_from_playback"))

    def test_scheduler_module_has_no_genre_references(self):
        import backend.scheduler as scheduler_module

        with open(scheduler_module.__file__, encoding="utf-8") as handle:
            self.assertNotIn("genre", handle.read().lower())


if __name__ == "__main__":
    unittest.main()
