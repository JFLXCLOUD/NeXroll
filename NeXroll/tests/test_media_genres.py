import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import media_genres, models


def response(status, payload):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload
    return r


class ItemGenreTests(unittest.TestCase):
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

    def test_asks_the_server_the_plugin_named_first(self):
        with patch.object(media_genres.requests, "get",
                          return_value=response(200, {"Items": [{"Genres": ["Horror", "Thriller"]}]})) as get:
            self.assertEqual(media_genres.item_genres(self.db, "abc", "emby"), ["Horror", "Thriller"])
        self.assertEqual(get.call_args.args[0], "http://emby:8096/emby/Items")
        self.assertEqual(get.call_args.kwargs["params"]["Ids"], "abc")
        self.assertEqual(get.call_args.kwargs["headers"], {"X-Emby-Token": "emby-key"})

    def test_jellyfin_uses_the_authorization_header(self):
        with patch.object(media_genres.requests, "get",
                          return_value=response(200, {"Items": [{"Genres": ["Comedy"]}]})) as get:
            media_genres.item_genres(self.db, "abc", "jellyfin")
        self.assertEqual(get.call_args.args[0], "http://jf:8096/Items")
        self.assertIn("Authorization", get.call_args.kwargs["headers"])

    def test_an_episode_takes_its_series_genres(self):
        replies = [
            response(200, {"Items": [{"Type": "Episode", "Genres": [], "SeriesId": "s1"}]}),
            response(200, {"Items": [{"Genres": ["Animation"]}]}),
        ]
        with patch.object(media_genres.requests, "get", side_effect=replies) as get:
            self.assertEqual(media_genres.item_genres(self.db, "ep1", "jellyfin"), ["Animation"])
        self.assertEqual(get.call_args.kwargs["params"]["Ids"], "s1")

    def test_falls_back_to_the_other_server(self):
        replies = [response(404, {}), response(200, {"Items": [{"Genres": ["Drama"]}]})]
        with patch.object(media_genres.requests, "get", side_effect=replies):
            self.assertEqual(media_genres.item_genres(self.db, "abc", "jellyfin"), ["Drama"])

    def test_unreachable_servers_mean_unknown_and_are_not_cached(self):
        with patch.object(media_genres.requests, "get", side_effect=OSError("down")):
            self.assertIsNone(media_genres.item_genres(self.db, "abc", "jellyfin"))
        with patch.object(media_genres.requests, "get",
                          return_value=response(200, {"Items": [{"Genres": ["Horror"]}]})) as get:
            self.assertEqual(media_genres.item_genres(self.db, "abc", "jellyfin"), ["Horror"])
            self.assertEqual(media_genres.item_genres(self.db, "abc", "jellyfin"), ["Horror"])
        self.assertEqual(get.call_count, 1)  # the second answer came from the cache

    def test_no_item_id_is_unknown_without_asking(self):
        with patch.object(media_genres.requests, "get") as get:
            self.assertIsNone(media_genres.item_genres(self.db, "", "jellyfin"))
            self.assertIsNone(media_genres.item_genres(self.db, "0", "emby"))
        get.assert_not_called()

    def test_library_genres_merge_both_servers(self):
        replies = [
            response(200, {"Items": [{"Name": "Horror"}, {"Name": "Comedy"}]}),
            response(200, {"Items": [{"Name": "horror"}, {"Name": "Anime"}]}),
        ]
        with patch.object(media_genres.requests, "get", side_effect=replies):
            self.assertEqual(media_genres.library_genres(self.db), ["Anime", "Comedy", "Horror"])


if __name__ == "__main__":
    unittest.main()
