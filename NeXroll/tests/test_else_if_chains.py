"""Else if chains: the first matching block in a chain plays, and only that one.

Issue #44 asked for one genre preroll per movie, chosen in priority order,
with a fallback when no genre matches. Before chains, every conditional block
was checked on its own, so a Horror + Sci-Fi movie played both genre blocks.
"""

import datetime
import os
import tempfile
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import models
from backend import scheduler as scheduler_module
from backend.backup_utils import remap_sequence_blocks
from backend.sequence_conditions import (
    PlaybackContext,
    chain_bounds,
    chain_choice,
    needs_evaluation,
    sequence_block_to_play,
    skip_reason,
)

NOW = datetime.datetime(2026, 9, 30, 20, 0)


def genre(*values, negate=False):
    return {"match": "all", "rules": [{"kind": "genre", "values": list(values), "negate": negate}]}


def ctx(genres=None, server="jellyfin", pool_count=None):
    return PlaybackContext(now=NOW, server=server, genre_lookup=lambda: genres, trailer_pool_count=pool_count)


def played(blocks, context):
    out = []
    for i in range(len(blocks)):
        chosen = sequence_block_to_play(blocks, i, context)
        if chosen is not None:
            out.append(chosen.get("name") or chosen.get("type"))
    return out


def genre_switch(fallback_as="otherwise"):
    """Horror, else if Sci-Fi, else if Action, else the house intro."""
    blocks = [
        {"type": "random", "name": "Horror", "condition": genre("Horror")},
        {"type": "random", "name": "Sci-Fi", "condition": genre("Science Fiction"), "else_if": True},
        {"type": "random", "name": "Action", "condition": genre("Action"), "else_if": True},
    ]
    if fallback_as == "otherwise":
        blocks[-1]["otherwise"] = {"type": "random", "name": "House", "category_id": 9}
    else:
        blocks.append({"type": "random", "name": "House", "else_if": True})
    return blocks


class ChainTests(unittest.TestCase):
    def test_first_matching_genre_wins(self):
        for fallback in ("otherwise", "block"):
            blocks = genre_switch(fallback)
            self.assertEqual(played(blocks, ctx(["Horror"])), ["Horror"])
            self.assertEqual(played(blocks, ctx(["Science Fiction", "Horror"])), ["Horror"])
            self.assertEqual(played(blocks, ctx(["Action", "Science Fiction"])), ["Sci-Fi"])
            self.assertEqual(played(blocks, ctx(["Action", "Thriller"])), ["Action"])

    def test_no_match_plays_the_fallback(self):
        for fallback in ("otherwise", "block"):
            blocks = genre_switch(fallback)
            self.assertEqual(played(blocks, ctx(["Comedy"])), ["House"])
            self.assertEqual(played(blocks, ctx([])), ["House"])

    def test_unknown_genre_plays_the_fallback(self):
        # Plex never says what is playing, and a failed lookup is unknown too.
        for fallback in ("otherwise", "block"):
            self.assertEqual(played(genre_switch(fallback), ctx(None, server="plex")), ["House"])
            self.assertEqual(played(genre_switch(fallback), ctx(None)), ["House"])

    def test_the_fallback_otherwise_plays_in_the_last_slot(self):
        blocks = genre_switch("otherwise")
        context = ctx(["Comedy"])
        self.assertIsNone(sequence_block_to_play(blocks, 0, context))
        self.assertIsNone(sequence_block_to_play(blocks, 1, context))
        self.assertEqual(sequence_block_to_play(blocks, 2, context), blocks[2]["otherwise"])

    def test_an_earlier_members_otherwise_never_plays(self):
        blocks = genre_switch("block")
        blocks[0]["otherwise"] = {"type": "random", "name": "Ignored", "category_id": 1}
        self.assertEqual(played(blocks, ctx(["Comedy"])), ["House"])
        self.assertEqual(played(blocks, ctx(["Action"])), ["Action"])

    def test_a_matched_last_member_hides_its_own_otherwise(self):
        blocks = genre_switch("otherwise")
        self.assertEqual(played(blocks, ctx(["Horror"])), ["Horror"])

    def test_blocks_outside_the_chain_play_as_before(self):
        blocks = [{"type": "fixed", "name": "Studio"}] + genre_switch("otherwise") + [
            {"type": "nexup_trailers", "name": "Trailers"},
            {"type": "random", "name": "Late", "condition": genre("Horror")},
        ]
        self.assertEqual(played(blocks, ctx(["Horror"])), ["Studio", "Horror", "Trailers", "Late"])
        self.assertEqual(played(blocks, ctx(["Comedy"])), ["Studio", "House", "Trailers"])

    def test_the_studio_intro_is_not_part_of_a_chain_that_follows_it(self):
        # The chain starts at the first conditional block; an unconditional
        # block above it has no else_if after it, so it is a chain of one.
        blocks = [{"type": "fixed", "name": "Studio"}] + genre_switch("otherwise")
        self.assertEqual(chain_bounds(blocks, 0), (0, 0))
        self.assertEqual(chain_bounds(blocks, 2), (1, 3))

    def test_two_chains_in_a_row_are_independent(self):
        blocks = genre_switch("block") + [
            {"type": "random", "name": "Late", "condition": {"rules": [
                {"kind": "time_window", "start": "19:00", "end": "23:00"}]}},
            {"type": "random", "name": "Daytime", "else_if": True},
        ]
        self.assertEqual(played(blocks, ctx(["Horror"])), ["Horror", "Late"])

    def test_else_if_on_the_first_block_starts_the_chain(self):
        blocks = genre_switch("block")
        blocks[0]["else_if"] = True
        self.assertEqual(played(blocks, ctx(["Horror"])), ["Horror"])

    def test_a_member_after_an_unconditional_one_never_plays(self):
        blocks = [{"type": "random", "name": "Always"},
                  {"type": "random", "name": "Never", "else_if": True}]
        self.assertEqual(played(blocks, ctx(["Horror"])), ["Always"])

    def test_without_the_flag_every_block_is_checked_on_its_own(self):
        blocks = genre_switch("block")
        for block in blocks:
            block.pop("else_if", None)
        self.assertEqual(played(blocks, ctx(["Horror", "Science Fiction"])), ["Horror", "Sci-Fi", "House"])

    def test_the_chain_is_decided_once(self):
        lookups = []
        context = PlaybackContext(now=NOW, genre_lookup=lambda: lookups.append(1) or ["Comedy"])
        blocks = genre_switch("block")
        for i in range(len(blocks)):
            sequence_block_to_play(blocks, i, context)
        self.assertEqual(chain_choice(blocks, 0, context), (3, blocks[3]))
        # replace() copies share the genre cache only per copy; the chain
        # cache keeps the whole chain to one evaluation per member.
        self.assertLessEqual(len(lookups), 3)

    def test_needs_evaluation_covers_unconditional_members(self):
        blocks = genre_switch("block") + [{"type": "fixed"}]
        self.assertEqual([needs_evaluation(blocks, i) for i in range(5)], [True, True, True, True, False])

    def test_skip_reasons(self):
        blocks = genre_switch("block")
        context = ctx(["Action"])
        self.assertIn("condition not met", skip_reason(blocks, 0, context))
        self.assertIn("block 3", skip_reason(blocks, 0, context))
        self.assertEqual(skip_reason(blocks, 3, context), "block 3 in its Else if chain already played")


class AvailabilityTests(unittest.TestCase):
    """An intro bound to this/next trailer block follows the chain's choice."""

    @staticmethod
    def pool(criteria):
        return {"library": 4, "upcoming": 0}[criteria["pool"]]

    def blocks(self):
        return [
            {"type": "fixed", "name": "Intro",
             "condition": {"rules": [{"kind": "trailers_available", "pool": "block", "min": 1}]}},
            {"type": "nexup_trailers", "name": "Horror trailers", "condition": genre("Horror")},
            {"type": "library_trailers", "name": "Library trailers", "else_if": True},
        ]

    def test_intro_plays_when_the_chain_picks_a_trailer_block_with_trailers(self):
        self.assertEqual(played(self.blocks(), ctx(["Comedy"], pool_count=self.pool)),
                         ["Intro", "Library trailers"])

    def test_intro_is_skipped_when_the_chain_picks_an_empty_trailer_block(self):
        self.assertEqual(played(self.blocks(), ctx(["Horror"], pool_count=self.pool)), ["Horror trailers"])

    def test_intro_is_skipped_when_the_chain_picks_something_else(self):
        blocks = self.blocks()
        blocks[2] = {"type": "random", "name": "Bumper", "else_if": True}
        self.assertEqual(played(blocks, ctx(["Comedy"], pool_count=self.pool)), ["Bumper"])

    def test_a_trailer_member_checking_itself_does_not_loop(self):
        blocks = [
            {"type": "library_trailers", "name": "Library",
             "condition": {"rules": [{"kind": "trailers_available", "pool": "block", "min": 1}]}},
            {"type": "random", "name": "Bumper", "else_if": True},
        ]
        self.assertEqual(played(blocks, ctx(["Comedy"], pool_count=self.pool)), ["Library"])
        blocks[0]["type"] = "nexup_trailers"
        self.assertEqual(played(blocks, ctx(["Comedy"], pool_count=self.pool)), ["Bumper"])


class ResolverTests(unittest.TestCase):
    """The resolver Plex, the Jellyfin/Emby plugin and previews share."""

    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        models.Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.paths = {}
        with self.Session() as db:
            for name in ("Horror", "SciFi", "House"):
                category = models.Category(name=name)
                db.add(category)
                db.flush()
                path = os.path.join(self.temp_dir.name, f"{name}.mp4")
                with open(path, "wb") as f:
                    f.write(b"test")
                db.add(models.Preroll(filename=f"{name}.mp4", path=path, category_id=category.id, enabled=True))
                self.paths[name] = (category.id, os.path.abspath(path))
            db.add(models.Setting())
            db.commit()

    def tearDown(self):
        self.engine.dispose()
        self.temp_dir.cleanup()

    def sequence(self):
        return [
            {"type": "random", "category_id": self.paths["Horror"][0], "count": 1, "condition": genre("Horror")},
            {"type": "random", "category_id": self.paths["SciFi"][0], "count": 1,
             "condition": genre("Science Fiction"), "else_if": True,
             "otherwise": {"type": "random", "category_id": self.paths["House"][0], "count": 1}},
        ]

    def resolve(self, db, **context):
        return scheduler_module.resolve_sequence_paths(
            self.sequence(), db, ("test",), context=scheduler_module.playback_context(db, **context))

    def test_plugin_and_plex_paths(self):
        with self.Session() as db:
            self.assertEqual(self.resolve(db, genres=["Science Fiction", "Horror"]), [self.paths["Horror"][1]])
            self.assertEqual(self.resolve(db, genres=["Science Fiction"]), [self.paths["SciFi"][1]])
            self.assertEqual(self.resolve(db, genres=["Comedy"]), [self.paths["House"][1]])
            self.assertEqual(self.resolve(db, media_type="movie", server_type="plex"), [self.paths["House"][1]])


class BackupTests(unittest.TestCase):
    def test_the_flag_survives_a_restore_remap(self):
        blocks = [{"type": "random", "category_id": 1, "condition": genre("Horror")},
                  {"type": "random", "category_id": 2, "else_if": True}]
        remapped = remap_sequence_blocks(blocks, {}, {1: 11, 2: 12})
        self.assertEqual([b.get("else_if") for b in remapped], [None, True])
        self.assertEqual([b["category_id"] for b in remapped], [11, 12])

    def test_a_dropped_member_closes_the_gap(self):
        # A member whose category cannot be restored is removed; the chain
        # simply loses that member, since membership is on each block.
        blocks = [{"type": "random", "category_id": 1, "condition": genre("Horror")},
                  {"type": "random", "category_id": 2, "condition": genre("Action"), "else_if": True},
                  {"type": "random", "category_id": 3, "else_if": True}]
        remapped = remap_sequence_blocks(blocks, {}, {1: 11, 3: 13})
        self.assertEqual([b["category_id"] for b in remapped], [11, 13])
        self.assertEqual(chain_bounds(remapped, 1), (0, 1))


if __name__ == "__main__":
    unittest.main()
