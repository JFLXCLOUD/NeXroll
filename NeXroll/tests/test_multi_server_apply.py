"""Applying prerolls when more than one media server is configured.

NeXroll reaches media servers two opposite ways. Plex is a *push* - NeXroll
writes paths into Plex's own preroll setting, and that call can fail. Jellyfin
and Emby *pull* - their plugin asks /plugin/intros at playback time and reads
state out of the database, so there is nothing to fail at apply time.

Collapsing both into one boolean made the pull channel a hostage to the push
one: callers wrote `if applied_ok:` before recording the active category, so an
unreachable Plex meant Jellyfin and Emby were never told what to play either.
These tests pin the behaviour that fixes.
"""
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import models
from backend import scheduler as scheduler_module

ApplyResult = scheduler_module.ApplyResult


class ApplyResultTests(unittest.TestCase):
    """The contract every caller relies on."""

    def test_truthy_when_either_channel_took_it(self):
        self.assertTrue(ApplyResult(plex=True))
        self.assertTrue(ApplyResult(plugin=True))
        self.assertTrue(ApplyResult(plex=True, plugin=True))

    def test_plugin_alone_is_enough_when_plex_failed(self):
        # The whole point: Plex being unreachable must not stop the caller
        # recording the active category that Jellyfin and Emby read.
        self.assertTrue(ApplyResult(plex=False, plugin=True))

    def test_falsy_when_nothing_took_it(self):
        self.assertFalse(ApplyResult())
        self.assertFalse(ApplyResult(plex=False))
        self.assertFalse(ApplyResult(plex=False, plugin=None))

    def test_none_means_not_configured_not_failure(self):
        self.assertFalse(ApplyResult().configured)
        self.assertTrue(ApplyResult(plex=False).configured)
        self.assertTrue(ApplyResult(plugin=True).configured)

    def test_describe_names_each_channel(self):
        self.assertEqual(
            ApplyResult(plex=False, plugin=True).describe(),
            "Plex: failed, Jellyfin/Emby: ok",
        )
        self.assertEqual(ApplyResult().describe(), "no media server configured")


class PluginChannelTests(unittest.TestCase):
    def test_true_for_either_plugin_server(self):
        for field in ("jellyfin_url", "emby_url"):
            setting = models.Setting(**{field: "http://server:8096"})
            self.assertTrue(scheduler_module._plugin_channel(setting), field)

    def test_none_when_no_plugin_server(self):
        self.assertIsNone(scheduler_module._plugin_channel(models.Setting()))
        self.assertIsNone(scheduler_module._plugin_channel(None))

    def test_never_false(self):
        """A pull channel has no delivery to fail, so it is True or None."""
        self.assertIsNot(scheduler_module._plugin_channel(models.Setting()), False)


class MultiServerFixture(unittest.TestCase):
    """Shared fixture. Holds no tests of its own."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        models.Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        path = os.path.join(self.temp_dir.name, "holiday.mp4")
        with open(path, "wb") as handle:
            handle.write(b"test")

        with self.Session() as db:
            category = models.Category(name="Halloween")
            db.add(category)
            db.flush()
            db.add(models.Preroll(filename="holiday.mp4", path=path,
                                  category_id=category.id, enabled=True))
            db.commit()
            self.category_id = category.id

        self.scheduler = scheduler_module.Scheduler()

    def _configure(self, **fields):
        with self.Session() as db:
            db.add(models.Setting(**fields))
            db.commit()

    def _apply(self, plex_push_succeeds=True):
        """Run the apply with the Plex network call stubbed out."""
        connector = MagicMock()
        connector.set_preroll.return_value = plex_push_succeeds
        # Report a platform that matches the host building the fixture paths.
        # An unreported platform is treated as POSIX, and the preflight then
        # rejects this test's own Windows temp paths before any push happens -
        # a real guard, but not the thing under test here.
        connector.get_server_info.return_value = {
            "platform": "Windows" if os.name == "nt" else "Linux"}
        with patch.object(scheduler_module, "PlexConnector", return_value=connector):
            with self.Session() as db:
                result = self.scheduler._apply_category_to_plex(self.category_id, db)
                db.commit()
        return result, connector

    def _category_marked(self):
        with self.Session() as db:
            return db.query(models.Category).filter(
                models.Category.id == self.category_id).first().apply_to_plex


class CategoryApplyAcrossServersTests(MultiServerFixture):
    # --- both servers together ------------------------------------------

    def test_plugin_marker_is_set_even_when_plex_is_configured(self):
        """The regression this feature exists to fix.

        The marker used to be written only on the branch taken when Plex was
        absent, so a household running Plex and Jellyfin got a correct Plex and
        a Jellyfin that never heard about the schedule.
        """
        self._configure(plex_url="http://plex:32400", plex_token="t",
                        jellyfin_url="http://jellyfin:8096", jellyfin_api_key="k")
        result, connector = self._apply()

        self.assertTrue(self._category_marked(), "plugin channel was not told")
        connector.set_preroll.assert_called_once()
        self.assertTrue(result.plex)
        self.assertTrue(result.plugin)

    def test_plugin_survives_a_failing_plex(self):
        self._configure(plex_url="http://plex:32400", plex_token="t",
                        emby_url="http://emby:8096", emby_api_key="k")
        result, _ = self._apply(plex_push_succeeds=False)

        self.assertFalse(result.plex)
        self.assertTrue(result.plugin)
        self.assertTrue(result, "caller would skip recording the active category")
        self.assertTrue(self._category_marked())

    def test_three_servers_at_once(self):
        self._configure(plex_url="http://plex:32400", plex_token="t",
                        jellyfin_url="http://jellyfin:8096", jellyfin_api_key="k",
                        emby_url="http://emby:8096", emby_api_key="k")
        result, _ = self._apply()
        self.assertTrue(result.plex)
        self.assertTrue(result.plugin)

    # --- single server, unchanged behaviour ------------------------------

    def test_plex_only_still_reports_failure(self):
        """Most installs have one server; their behaviour must not drift."""
        self._configure(plex_url="http://plex:32400", plex_token="t")
        result, _ = self._apply(plex_push_succeeds=False)

        self.assertFalse(result)
        self.assertFalse(result.plex)
        self.assertIsNone(result.plugin)
        self.assertFalse(self._category_marked())

    def test_plex_only_success(self):
        self._configure(plex_url="http://plex:32400", plex_token="t")
        result, _ = self._apply()
        self.assertTrue(result)
        self.assertIsNone(result.plugin)

    def test_plugin_only_never_touches_plex(self):
        self._configure(jellyfin_url="http://jellyfin:8096", jellyfin_api_key="k")
        result, connector = self._apply()

        connector.set_preroll.assert_not_called()
        self.assertIsNone(result.plex)
        self.assertTrue(result.plugin)
        self.assertTrue(self._category_marked())

    def test_no_server_configured_is_falsy(self):
        self._configure()
        result, connector = self._apply()

        connector.set_preroll.assert_not_called()
        self.assertFalse(result)
        self.assertFalse(result.configured)

    def test_empty_category_applies_nowhere(self):
        self._configure(plex_url="http://plex:32400", plex_token="t",
                        jellyfin_url="http://jellyfin:8096")
        with self.Session() as db:
            empty = models.Category(name="Empty")
            db.add(empty)
            db.commit()
            empty_id = empty.id
        connector = MagicMock()
        with patch.object(scheduler_module, "PlexConnector", return_value=connector):
            with self.Session() as db:
                result = self.scheduler._apply_category_to_plex(empty_id, db)

        self.assertFalse(result)
        connector.set_preroll.assert_not_called()


class ClearAcrossServersTests(MultiServerFixture):
    """Clearing has to reach both channels for the same reason applying does."""

    def _clear(self, plex_push_succeeds=True):
        connector = MagicMock()
        connector.set_preroll.return_value = plex_push_succeeds
        with patch.object(scheduler_module, "PlexConnector", return_value=connector):
            with self.Session() as db:
                result = self.scheduler._clear_plex_prerolls(db)
                db.commit()
        return result, connector

    def test_clear_unmarks_the_plugin_category_even_with_plex_configured(self):
        self._configure(plex_url="http://plex:32400", plex_token="t",
                        jellyfin_url="http://jellyfin:8096")
        self._apply()
        self.assertTrue(self._category_marked())

        result, _ = self._clear()
        self.assertFalse(self._category_marked(),
                         "Jellyfin would still advertise the cleared category")
        self.assertTrue(result.plugin)

    def test_clear_reports_plex_failure_without_losing_the_plugin(self):
        self._configure(plex_url="http://plex:32400", plex_token="t",
                        emby_url="http://emby:8096")
        result, _ = self._clear(plex_push_succeeds=False)
        self.assertFalse(result.plex)
        self.assertTrue(result.plugin)
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
