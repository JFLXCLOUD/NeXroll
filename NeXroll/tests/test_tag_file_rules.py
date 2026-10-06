"""Tag and file path rules on sequence blocks (Jellyfin/Emby only).

Prompted by a Jellyfin user who wanted an IMAX preroll before IMAX movies:
Jellyfin has no IMAX flag, so the movie is recognised by a tag the user adds
or by "IMAX" in its file name.
"""
import datetime
import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import media_genres, models
from backend import scheduler as scheduler_module
from backend.sequence_conditions import (
    PlaybackContext,
    condition_holds,
    describe_condition,
    evaluate_rule,
    needs_playback_info,
)

NOW = datetime.datetime(2026, 10, 9, 20, 0)


def cond(*rules, match="all"):
    return {"match": match, "rules": list(rules)}


def response(status, payload):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload
    return r


class TagRuleTests(unittest.TestCase):
    def ctx(self, tags):
        return PlaybackContext(now=NOW, tag_lookup=lambda: tags)

    def test_matches_any_listed_tag_ignoring_capitals(self):
        rule = {"kind": "tag", "values": ["imax", "4K Remaster"]}
        self.assertTrue(evaluate_rule(rule, self.ctx(["Favorites", "IMAX"])))
        self.assertFalse(evaluate_rule(rule, self.ctx(["Favorites"])))
        self.assertFalse(evaluate_rule(rule, self.ctx([])))

    def test_negated_tag(self):
        rule = {"kind": "tag", "values": ["IMAX"], "negate": True}
        self.assertTrue(evaluate_rule(rule, self.ctx(["Kids"])))
        self.assertFalse(evaluate_rule(rule, self.ctx(["IMAX"])))

    def test_unknown_tags_are_unknown_and_not_met_either_way(self):
        self.assertIsNone(evaluate_rule({"kind": "tag", "values": ["IMAX"]}, self.ctx(None)))
        self.assertFalse(condition_holds(cond({"kind": "tag", "values": ["IMAX"], "negate": True}), self.ctx(None)))

    def test_a_rule_with_no_tags_chosen_is_unknown(self):
        self.assertIsNone(evaluate_rule({"kind": "tag", "values": [" "]}, self.ctx(["IMAX"])))

    def test_tags_are_looked_up_once_and_only_when_asked(self):
        calls = []
        context = PlaybackContext(now=NOW, tag_lookup=lambda: calls.append(1) or ["IMAX"])
        evaluate_rule({"kind": "genre", "values": ["Horror"]}, context)
        self.assertEqual(calls, [])
        evaluate_rule({"kind": "tag", "values": ["IMAX"]}, context)
        evaluate_rule({"kind": "tag", "values": ["Kids"]}, context)
        self.assertEqual(calls, [1])

    def test_a_failing_lookup_is_unknown(self):
        def boom():
            raise RuntimeError("server gone")
        self.assertIsNone(evaluate_rule({"kind": "tag", "values": ["IMAX"]}, PlaybackContext(now=NOW, tag_lookup=boom)))


class FilePathRuleTests(unittest.TestCase):
    def ctx(self, path):
        return PlaybackContext(now=NOW, path_lookup=lambda: path)

    def test_matches_text_anywhere_in_the_path_ignoring_capitals(self):
        rule = {"kind": "file_name", "values": ["IMAX"]}
        self.assertTrue(evaluate_rule(rule, self.ctx("/movies/Dune (2021)/Dune (2021) - imax.mkv")))
        self.assertTrue(evaluate_rule(rule, self.ctx("/movies/Dune (2021) {edition-IMAX}/Dune.mkv")))
        self.assertFalse(evaluate_rule(rule, self.ctx("/movies/Dune (2021)/Dune (2021).mkv")))

    def test_any_of_several_texts(self):
        rule = {"kind": "file_name", "values": ["IMAX", "Remux"]}
        self.assertTrue(evaluate_rule(rule, self.ctx("/m/Heat (1995) Remux.mkv")))

    def test_windows_paths_compare_with_forward_slashes(self):
        rule = {"kind": "file_name", "values": ["Movies\\IMAX"]}
        self.assertTrue(evaluate_rule(rule, self.ctx("D:\\Movies\\IMAX\\Oppenheimer.mkv")))

    def test_negated_and_unknown(self):
        rule = {"kind": "file_name", "values": ["IMAX"], "negate": True}
        self.assertTrue(evaluate_rule(rule, self.ctx("/m/Heat.mkv")))
        self.assertFalse(evaluate_rule(rule, self.ctx("/m/Heat IMAX.mkv")))
        self.assertIsNone(evaluate_rule(rule, self.ctx(None)))
        self.assertIsNone(evaluate_rule({"kind": "file_name", "values": []}, self.ctx("/m/x.mkv")))


class DescribeAndPlaybackTests(unittest.TestCase):
    def test_both_need_the_jellyfin_or_emby_plugin(self):
        self.assertTrue(needs_playback_info(cond({"kind": "tag", "values": ["IMAX"]})))
        self.assertTrue(needs_playback_info(cond({"kind": "file_name", "values": ["IMAX"]})))

    def test_descriptions(self):
        self.assertEqual(describe_condition(cond({"kind": "tag", "values": ["IMAX", "3D"]})), "tag is IMAX or 3D")
        self.assertEqual(describe_condition(cond({"kind": "file_name", "values": ["IMAX"], "negate": True})),
                         'not file path contains "IMAX"')


class PlaybackContextTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        models.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.db.add(models.Setting())
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_preview_values_are_used_as_given(self):
        context = scheduler_module.playback_context(self.db, tags=["IMAX"], file_path="/m/Dune - IMAX.mkv")
        self.assertTrue(condition_holds(cond({"kind": "tag", "values": ["imax"]}), context))
        self.assertTrue(condition_holds(cond({"kind": "file_name", "values": ["IMAX"]}), context))

    def test_plex_knows_neither(self):
        context = scheduler_module.playback_context(self.db, media_type="movie")
        self.assertFalse(condition_holds(cond({"kind": "tag", "values": ["IMAX"]}), context))
        self.assertFalse(condition_holds(cond({"kind": "file_name", "values": ["IMAX"]}), context))

    def test_genre_tag_and_path_come_from_one_item_lookup(self):
        details = {"genres": ["Science Fiction"], "tmdb": "438631", "tags": ["IMAX"], "path": "/m/Dune.mkv"}
        with patch("backend.media_genres.item_details", return_value=details) as lookup:
            context = scheduler_module.playback_context(self.db, item_id="abc", server_type="jellyfin")
            self.assertTrue(condition_holds(cond({"kind": "tag", "values": ["IMAX"]},
                                                 {"kind": "genre", "values": ["Science Fiction"]},
                                                 {"kind": "file_name", "values": ["dune"]}), context))
        lookup.assert_called_once()


class ItemLookupTests(unittest.TestCase):
    def setUp(self):
        media_genres.clear_cache()
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        models.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.db.add(models.Setting(jellyfin_url="http://jf:8096/", emby_url="http://emby:8096"))
        self.db.commit()
        self.keys = patch.multiple(
            media_genres.secure_store,
            get_jellyfin_api_key=MagicMock(return_value="jf-key"),
            get_emby_api_key=MagicMock(return_value="emby-key"),
        )
        self.keys.start()

    def tearDown(self):
        self.keys.stop()
        self.db.close()
        self.engine.dispose()

    def test_jellyfin_reports_tags_and_path_and_is_not_asked_for_emby_fields(self):
        item = {"Genres": ["Drama"], "Tags": ["IMAX", "imax", " "], "Path": "/m/Oppenheimer - IMAX.mkv"}
        with patch.object(media_genres.requests, "get", return_value=response(200, {"Items": [item]})) as get:
            details = media_genres.item_details(self.db, "abc", "jellyfin")
        self.assertEqual(details["tags"], ["IMAX"])
        self.assertEqual(details["path"], "/m/Oppenheimer - IMAX.mkv")
        fields = get.call_args.kwargs["params"]["Fields"].split(",")
        self.assertIn("Tags", fields)
        self.assertIn("Path", fields)
        self.assertNotIn("TagItems", fields)

    def test_emby_tags_come_from_tag_items(self):
        item = {"Genres": [], "TagItems": [{"Name": "IMAX", "Id": 7}], "Path": "D:\\Movies\\Dune.mkv"}
        with patch.object(media_genres.requests, "get", return_value=response(200, {"Items": [item]})) as get:
            details = media_genres.item_details(self.db, "abc", "emby")
        self.assertEqual(details["tags"], ["IMAX"])
        self.assertIn("TagItems", get.call_args.kwargs["params"]["Fields"])

    def test_an_episode_without_tags_takes_its_series_tags_and_keeps_its_genres(self):
        replies = [
            response(200, {"Items": [{"Type": "Episode", "Genres": ["Comedy"], "Tags": [], "SeriesId": "s1",
                                      "Path": "/tv/Show/S01E01.mkv"}]}),
            response(200, {"Items": [{"Genres": ["Drama"], "Tags": ["Anime"]}]}),
        ]
        with patch.object(media_genres.requests, "get", side_effect=replies):
            details = media_genres.item_details(self.db, "ep1", "jellyfin")
        self.assertEqual(details["genres"], ["Comedy"])
        self.assertEqual(details["tags"], ["Anime"])
        self.assertEqual(details["path"], "/tv/Show/S01E01.mkv")

    def test_a_movie_without_tags_does_not_ask_again(self):
        with patch.object(media_genres.requests, "get",
                          return_value=response(200, {"Items": [{"Genres": ["Drama"]}]})) as get:
            details = media_genres.item_details(self.db, "abc", "jellyfin")
        self.assertEqual(details["tags"], [])
        self.assertIsNone(details["path"])
        self.assertEqual(get.call_count, 1)

    def test_library_tags_merge_jellyfin_filters_and_emby_tags(self):
        replies = [
            response(200, {"Genres": ["Drama"], "Tags": ["IMAX", "Kids"]}),
            response(200, {"Items": [{"Name": "imax"}, {"Name": "3D"}]}),
        ]
        with patch.object(media_genres.requests, "get", side_effect=replies) as get:
            self.assertEqual(media_genres.library_tags(self.db), ["3D", "IMAX", "Kids"])
        urls = [c.args[0] for c in get.call_args_list]
        self.assertEqual(urls, ["http://jf:8096/Items/Filters", "http://emby:8096/emby/Tags"])

    def test_library_tags_skip_a_server_that_fails(self):
        replies = [response(500, {}), response(200, {"Items": [{"Name": "IMAX"}]})]
        with patch.object(media_genres.requests, "get", side_effect=replies):
            self.assertEqual(media_genres.library_tags(self.db), ["IMAX"])


if __name__ == "__main__":
    unittest.main()
