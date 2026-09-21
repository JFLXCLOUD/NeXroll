import datetime
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import models
from backend import scheduler as scheduler_module
from backend.backup_utils import remap_sequence_blocks
from backend.sequence_conditions import (
    PlaybackContext,
    block_to_play,
    condition_holds,
    describe_condition,
    evaluate_rule,
    has_conditions,
)

# A Friday.
FRIDAY_EVENING = datetime.datetime(2026, 9, 18, 21, 30)


def ctx(now=FRIDAY_EVENING, media_type=None, trailers=None):
    counter = None if trailers is None else (lambda source: trailers.get(source, 0))
    return PlaybackContext(now=now, media_type=media_type, trailer_count=counter)


def cond(*rules, match="all"):
    return {"match": match, "rules": list(rules)}


class RuleTests(unittest.TestCase):
    def test_trailers_available_compares_against_the_minimum(self):
        rule = {"kind": "trailers_available", "source": "movies", "min": 2}
        self.assertTrue(evaluate_rule(rule, ctx(trailers={"movies": 2})))
        self.assertFalse(evaluate_rule(rule, ctx(trailers={"movies": 1})))

    def test_trailers_available_defaults_to_at_least_one_from_both(self):
        rule = {"kind": "trailers_available"}
        self.assertTrue(evaluate_rule(rule, ctx(trailers={"both": 1})))
        self.assertFalse(evaluate_rule(rule, ctx(trailers={"both": 0})))

    def test_trailer_count_is_asked_once_per_source(self):
        calls = []
        context = PlaybackContext(now=FRIDAY_EVENING,
                                  trailer_count=lambda s: calls.append(s) or 3)
        rule = {"kind": "trailers_available", "source": "tv"}
        evaluate_rule(rule, context)
        evaluate_rule(rule, context)
        self.assertEqual(calls, ["tv"])

    def test_media_type_matches_case_insensitively(self):
        rule = {"kind": "media_type", "value": "episode"}
        self.assertTrue(evaluate_rule(rule, ctx(media_type="Episode")))
        self.assertFalse(evaluate_rule(rule, ctx(media_type="Movie")))

    def test_media_type_is_unknown_when_the_caller_cannot_say(self):
        self.assertIsNone(evaluate_rule({"kind": "media_type", "value": "movie"}, ctx()))

    def test_time_window_same_day(self):
        rule = {"kind": "time_window", "start": "20:00", "end": "23:00"}
        self.assertTrue(evaluate_rule(rule, ctx()))
        self.assertFalse(evaluate_rule(rule, ctx(now=FRIDAY_EVENING.replace(hour=19))))
        # The end is exclusive.
        self.assertFalse(evaluate_rule(rule, ctx(now=FRIDAY_EVENING.replace(hour=23, minute=0))))

    def test_overnight_window_belongs_to_the_day_it_opened(self):
        rule = {"kind": "time_window", "start": "22:00", "end": "03:00", "days": ["friday"]}
        saturday_1am = datetime.datetime(2026, 9, 19, 1, 0)
        friday_1am = datetime.datetime(2026, 9, 18, 1, 0)
        self.assertTrue(evaluate_rule(rule, ctx(now=saturday_1am)))
        self.assertFalse(evaluate_rule(rule, ctx(now=friday_1am)))
        self.assertTrue(evaluate_rule(rule, ctx(now=FRIDAY_EVENING.replace(hour=23))))

    def test_malformed_time_window_is_unknown(self):
        self.assertIsNone(evaluate_rule({"kind": "time_window", "start": "late", "end": "3"}, ctx()))

    def test_negate_inverts_a_known_answer_only(self):
        self.assertFalse(evaluate_rule(
            {"kind": "trailers_available", "negate": True}, ctx(trailers={"both": 4})))
        self.assertIsNone(evaluate_rule(
            {"kind": "media_type", "value": "movie", "negate": True}, ctx()))

    def test_unknown_kind_is_unknown(self):
        self.assertIsNone(evaluate_rule({"kind": "moon_phase"}, ctx()))


class ConditionTests(unittest.TestCase):
    def test_all_requires_every_rule(self):
        c = cond({"kind": "media_type", "value": "movie"},
                 {"kind": "trailers_available", "min": 1})
        self.assertTrue(condition_holds(c, ctx(media_type="movie", trailers={"both": 1})))
        self.assertFalse(condition_holds(c, ctx(media_type="movie", trailers={"both": 0})))

    def test_any_needs_one_rule(self):
        c = cond({"kind": "media_type", "value": "episode"},
                 {"kind": "trailers_available", "min": 1}, match="any")
        self.assertTrue(condition_holds(c, ctx(media_type="movie", trailers={"both": 1})))
        self.assertFalse(condition_holds(c, ctx(media_type="movie", trailers={"both": 0})))

    def test_an_unanswerable_rule_counts_as_not_met(self):
        # Plex never says what is playing: a genre or media-type block must
        # not play before every movie there.
        self.assertFalse(condition_holds(cond({"kind": "media_type", "value": "episode"}), ctx()))
        self.assertFalse(condition_holds(cond({"kind": "genre", "values": ["Horror"]}), ctx()))
        # "unless" too: not knowing is not the same as knowing it isn't.
        self.assertFalse(condition_holds(cond({"kind": "genre", "values": ["Horror"], "negate": True}), ctx()))

    def test_any_is_met_by_one_answerable_rule(self):
        c = cond({"kind": "genre", "values": ["Horror"]},
                 {"kind": "trailers_available", "min": 1}, match="any")
        self.assertTrue(condition_holds(c, ctx(trailers={"both": 2})))

    def test_empty_or_missing_condition_holds(self):
        self.assertTrue(condition_holds(None, ctx()))
        self.assertTrue(condition_holds({"rules": []}, ctx()))


class GenreRuleTests(unittest.TestCase):
    def genre_ctx(self, genres):
        return PlaybackContext(now=FRIDAY_EVENING, genre_lookup=lambda: genres)

    def test_matches_any_listed_genre_case_insensitively(self):
        rule = {"kind": "genre", "values": ["horror", "Thriller"]}
        self.assertTrue(evaluate_rule(rule, self.genre_ctx(["Drama", "Horror"])))
        self.assertFalse(evaluate_rule(rule, self.genre_ctx(["Comedy"])))

    def test_negated_genre(self):
        rule = {"kind": "genre", "values": ["Horror"], "negate": True}
        self.assertTrue(evaluate_rule(rule, self.genre_ctx(["Family"])))
        self.assertFalse(evaluate_rule(rule, self.genre_ctx(["Horror"])))

    def test_unknown_genres_are_unknown(self):
        self.assertIsNone(evaluate_rule({"kind": "genre", "values": ["Horror"]}, self.genre_ctx(None)))

    def test_a_rule_with_no_genres_chosen_is_unknown(self):
        self.assertIsNone(evaluate_rule({"kind": "genre", "values": []}, self.genre_ctx(["Horror"])))

    def test_genres_are_looked_up_once_and_only_when_asked(self):
        calls = []
        context = PlaybackContext(now=FRIDAY_EVENING, genre_lookup=lambda: calls.append(1) or ["Horror"])
        evaluate_rule({"kind": "trailers_available"}, context)
        self.assertEqual(calls, [])
        evaluate_rule({"kind": "genre", "values": ["Horror"]}, context)
        evaluate_rule({"kind": "genre", "values": ["Comedy"]}, context)
        self.assertEqual(calls, [1])

    def test_needs_playback_info(self):
        from backend.sequence_conditions import needs_playback_info
        self.assertTrue(needs_playback_info(cond({"kind": "genre", "values": ["Horror"]})))
        self.assertFalse(needs_playback_info(cond({"kind": "time_window", "start": "1:00", "end": "2:00"})))


class BlockToPlayTests(unittest.TestCase):
    def setUp(self):
        self.guarded = {
            "type": "coming_soon_list",
            "condition": cond({"kind": "trailers_available", "min": 1}),
        }

    def test_unconditional_block_always_plays(self):
        block = {"type": "random", "category_id": 1}
        self.assertIs(block_to_play(block, ctx(trailers={"both": 0})), block)

    def test_condition_met_plays_the_block(self):
        self.assertIs(block_to_play(self.guarded, ctx(trailers={"both": 3})), self.guarded)

    def test_condition_unmet_without_alternative_skips(self):
        self.assertIsNone(block_to_play(self.guarded, ctx(trailers={"both": 0})))

    def test_condition_unmet_plays_the_alternative(self):
        otherwise = {"type": "random", "category_id": 4, "count": 1}
        block = dict(self.guarded, otherwise=otherwise)
        self.assertIs(block_to_play(block, ctx(trailers={"both": 0})), otherwise)

    def test_alternative_of_an_unsupported_type_is_ignored(self):
        block = dict(self.guarded, otherwise={"type": "separator", "duration": 3})
        self.assertIsNone(block_to_play(block, ctx(trailers={"both": 0})))

    def test_has_conditions(self):
        self.assertFalse(has_conditions([{"type": "random"}]))
        self.assertTrue(has_conditions([{"type": "random"}, self.guarded]))
        self.assertFalse(has_conditions(None))

    def test_describe_condition(self):
        text = describe_condition(cond(
            {"kind": "trailers_available", "source": "movies", "min": 2},
            {"kind": "time_window", "start": "20:00", "end": "23:00", "negate": True},
        ))
        self.assertEqual(text, "at least 2 movies trailer(s) available and not between 20:00 and 23:00")


class SharedResolverTests(unittest.TestCase):
    """The resolver every apply path and the plugin now share."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        models.Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.temp_dir = tempfile.TemporaryDirectory()
        storage = self.temp_dir.name
        os.makedirs(os.path.join(storage, "dynamic_prerolls"))

        def media(name):
            path = os.path.join(storage, name)
            with open(path, "wb") as f:
                f.write(b"test")
            return path

        self.coming_soon = media(os.path.join("dynamic_prerolls", "coming_soon_grid.mp4"))
        with self.Session() as db:
            intros = models.Category(name="Intros")
            db.add(intros)
            db.flush()
            house = models.Preroll(filename="house.mp4", path=media("house.mp4"),
                                   category_id=intros.id, enabled=True)
            gone = models.Preroll(filename="gone.mp4", path=os.path.join(storage, "gone.mp4"),
                                  category_id=intros.id, enabled=True)
            db.add_all([house, gone, models.Setting(nexup_storage_path=storage)])
            db.commit()
            self.intros_id = intros.id
            self.house_id = house.id
            self.gone_id = gone.id
            self.house_path = os.path.abspath(house.path)

    def tearDown(self):
        self.engine.dispose()
        self.temp_dir.cleanup()

    def add_trailer(self, db, title="Upcoming"):
        path = os.path.join(self.temp_dir.name, f"{title}.mp4")
        with open(path, "wb") as f:
            f.write(b"test")
        db.add(models.ComingSoonTrailer(title=title, status="downloaded",
                                        is_enabled=True, local_path=path))
        db.commit()

    def guarded_list(self, **extra):
        block = {"type": "coming_soon_list", "layout": "grid",
                 "condition": cond({"kind": "trailers_available", "min": 1})}
        block.update(extra)
        return block

    def test_unmet_condition_skips_the_block(self):
        with self.Session() as db:
            paths = scheduler_module.resolve_sequence_paths(
                [self.guarded_list(), {"type": "fixed", "preroll_ids": [self.house_id]}],
                db, ("test",))
        self.assertEqual(paths, [self.house_path])

    def test_met_condition_plays_the_block(self):
        with self.Session() as db:
            self.add_trailer(db)
            paths = scheduler_module.resolve_sequence_paths([self.guarded_list()], db, ("test",))
        self.assertEqual(paths, [os.path.abspath(self.coming_soon)])

    def test_unmet_condition_plays_the_alternative(self):
        block = self.guarded_list(otherwise={"type": "random", "category_id": self.intros_id, "count": 1})
        with self.Session() as db:
            paths = scheduler_module.resolve_sequence_paths([block], db, ("test",))
        self.assertEqual(paths, [self.house_path])

    def test_disabled_trailers_do_not_count_as_available(self):
        with self.Session() as db:
            self.add_trailer(db)
            db.query(models.ComingSoonTrailer).update({"is_enabled": False})
            db.commit()
            paths = scheduler_module.resolve_sequence_paths([self.guarded_list()], db, ("test",))
        self.assertEqual(paths, [])

    def test_media_type_condition_uses_the_context(self):
        block = {"type": "fixed", "preroll_ids": [self.house_id],
                 "condition": cond({"kind": "media_type", "value": "episode"})}
        with self.Session() as db:
            movie = scheduler_module.resolve_sequence_paths(
                [block], db, ("test",), context=scheduler_module.playback_context(db, media_type="Movie"))
            episode = scheduler_module.resolve_sequence_paths(
                [block], db, ("test",), context=scheduler_module.playback_context(db, media_type="Episode"))
        self.assertEqual(movie, [])
        self.assertEqual(episode, [self.house_path])

    def test_genre_condition_plays_the_alternative_on_plex(self):
        block = {"type": "fixed", "preroll_ids": [self.house_id],
                 "condition": cond({"kind": "genre", "values": ["Horror"]}),
                 "otherwise": {"type": "coming_soon_list", "layout": "grid"}}
        with self.Session() as db:
            horror = scheduler_module.resolve_sequence_paths(
                [block], db, ("test",), context=scheduler_module.playback_context(db, genres=["Horror"]))
            plex = scheduler_module.resolve_sequence_paths(
                [block], db, ("test",), context=scheduler_module.playback_context(db, media_type="movie"))
        self.assertEqual(horror, [self.house_path])
        self.assertEqual(plex, [os.path.abspath(self.coming_soon)])

    def test_fixed_block_skips_missing_files_on_every_path(self):
        with self.Session() as db:
            paths = scheduler_module.resolve_sequence_paths(
                [{"type": "fixed", "preroll_ids": [self.gone_id, self.house_id]}], db, ("test",))
        self.assertEqual(paths, [self.house_path])

    def test_plex_schedule_apply_honours_conditions(self):
        connector = MagicMock()
        connector.get_server_info.return_value = {"platform": "Windows"}
        connector.set_preroll.return_value = True
        schedule = scheduler_module.models.Schedule(
            id=1, name="Guarded", category_id=None,
            sequence=json.dumps([
                self.guarded_list(),
                {"type": "fixed", "preroll_ids": [self.house_id]},
            ]),
        )
        with self.Session() as db:
            db.query(models.Setting).update({"plex_url": "http://plex.invalid", "plex_token": "t"})
            db.commit()
            with patch.object(scheduler_module, "PlexConnector", return_value=connector):
                self.assertTrue(scheduler_module.Scheduler()._apply_schedule_sequence_to_plex(schedule, db))
        self.assertEqual(connector.set_preroll.call_args.args[0], self.house_path)


class RemapOtherwiseTests(unittest.TestCase):
    def test_alternative_category_is_remapped(self):
        blocks = [{"type": "coming_soon_list",
                   "condition": cond({"kind": "trailers_available"}),
                   "otherwise": {"type": "random", "category_id": 5, "count": 1}}]
        out = remap_sequence_blocks(blocks, {}, {5: 50})
        self.assertEqual(out[0]["otherwise"]["category_id"], 50)
        self.assertEqual(out[0]["condition"], blocks[0]["condition"])

    def test_unmappable_alternative_is_dropped_but_block_kept(self):
        blocks = [{"type": "coming_soon_list",
                   "condition": cond({"kind": "trailers_available"}),
                   "otherwise": {"type": "random", "category_id": 5, "count": 1}}]
        out = remap_sequence_blocks(blocks, {}, {})
        self.assertEqual(len(out), 1)
        self.assertNotIn("otherwise", out[0])


if __name__ == "__main__":
    unittest.main()
