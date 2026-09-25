import datetime
import json
import os

import pytest

from backend import library_trailers as lt, trailer_quotas as tq, models
from tests.test_library_trailers import LibraryTrailerTestBase, FakeDownloader, movie, NOW


def target(kind='rating', values=None, minimum=2):
    return {'kind': kind, 'values': values or ['G', 'PG'], 'min': minimum}


class QuotaSyncTests(LibraryTrailerTestBase):
    def test_defaults_and_saved_settings_upgrade_without_rewriting_other_fields(self):
        setting = models.Setting(library_trailers_config=json.dumps({'mode': 'picked', 'picked': [4], 'max_downloads': 7}))
        self.assertEqual(lt.load_config(setting)['quotas'], [])
        result = lt.save_config(setting, {'quotas': [target()]})
        self.assertEqual((result['picked'], result['max_downloads']), ([4], 7))
        self.assertEqual(lt.load_config(setting)['quotas'], [target()])
        before = setting.library_trailers_config
        with self.assertRaises(ValueError):
            lt.save_config(setting, {'quotas': [{'kind': 'rating', 'values': [], 'min': 2}]})
        self.assertEqual(setting.library_trailers_config, before)

    def test_overlap_counts_once_and_fills_rest_in_priority_order(self):
        movies = [movie(1, 'Newest', cert='R', days_ago=1),
                  movie(2, 'PG horror', cert='PG', genres=['Horror'], days_ago=20),
                  movie(3, 'G movie', cert='G', days_ago=30), movie(4, 'Other', cert='R', days_ago=50)]
        cfg = self.config(max_downloads=3, quotas=[target(), target('genre', ['Horror'], 1)])
        result = self.sync(movies, cfg)
        self.assertEqual(self.downloader.calls, ['PG horror', 'G movie', 'Newest'])
        self.assertEqual([q['shortfall'] for q in result['quotas']], [0, 0])
        self.assertEqual(result['downloaded'], 3)

    def test_local_files_satisfy_targets_without_consuming_download_slots(self):
        path = self.local_trailer('Local')
        result = self.sync([movie(1, 'Local', cert='PG'), movie(2, 'Download', cert='R')],
                           self.config(max_downloads=1, quotas=[target(minimum=1)]))
        self.assertEqual(result['downloaded'], 1)
        self.assertEqual(result['quotas'][0]['available'], 1)
        self.assertTrue(os.path.isfile(path))

    def test_failed_replacement_preserves_working_trailer_and_retries_another_match(self):
        movies = [movie(1, 'Old', cert='R'), movie(2, 'Fails', cert='PG', days_ago=1), movie(3, 'Works', cert='PG')]
        self.sync(movies[:1], self.config(max_downloads=1))
        old = self.rows()['Old'].local_path
        self.downloader.fail.add('Fails')
        result = self.sync(movies[:2], self.config(max_downloads=1, quotas=[target(minimum=1)]))
        self.assertTrue(os.path.isfile(old))
        self.assertEqual(result['rotated'], 0)
        self.assertEqual(result['quotas'][0]['shortfall'], 1)
        result = self.sync(movies, self.config(max_downloads=1, quotas=[target(minimum=1)]))
        self.assertEqual(result['rotated'], 1)
        self.assertFalse(os.path.exists(old))
        self.assertEqual(result['quotas'][0]['shortfall'], 0)

    def test_rotation_preserves_targets_but_replaces_unneeded_old_download(self):
        movies = [movie(1, 'PG', cert='PG'), movie(2, 'Old R', cert='R'), movie(3, 'New R', cert='R', days_ago=1)]
        self.sync(movies[:2], self.config(max_downloads=2))
        for row in self.rows().values(): row.downloaded_at = NOW - datetime.timedelta(days=10)
        self.db.commit()
        pg_path = self.rows()['PG'].local_path
        result = self.sync(movies, self.config(max_downloads=2, quotas=[target(minimum=1)]))
        self.assertTrue(os.path.isfile(pg_path))
        self.assertIn('New R', self.rows())
        self.assertEqual(result['quotas'][0]['shortfall'], 0)

    def test_full_pool_repairs_targets_without_waiting_a_week(self):
        movies = [movie(1, 'Old', cert='R'), movie(2, 'PG', cert='PG')]
        self.sync(movies[:1], self.config(max_downloads=1))
        result = self.sync(movies, self.config(max_downloads=1, quotas=[target(minimum=1)]))
        self.assertEqual(result['rotated'], 1)
        self.assertEqual(result['quotas'][0]['available'], 1)

    def test_impossible_targets_respect_hard_limit_and_report_shortfall(self):
        movies = [movie(1, 'PG', cert='PG'), movie(2, 'Horror', cert='R', genres=['Horror'])]
        result = self.sync(movies, self.config(max_downloads=1, quotas=[target(minimum=1), target('genre', ['Horror'], 1)]))
        self.assertEqual(len([r for r in self.rows().values() if r.status == 'available']), 1)
        self.assertEqual(sum(q['shortfall'] for q in result['quotas']), 1)
        self.assertTrue(any('Capacity' in q['reason'] for q in result['quotas']))

    def test_filters_and_picks_are_never_bypassed_and_pins_are_protected(self):
        movies = [movie(1, 'Pinned', cert='R'), movie(2, 'PG', cert='PG')]
        self.sync(movies[:1], self.config(max_downloads=1))
        result = self.sync(movies, self.config(max_downloads=1, always_include=[1], quotas=[target(minimum=1)]))
        self.assertEqual(result['downloaded'], 0)
        self.assertIn('Pinned', self.rows())
        result = self.sync(movies, self.config(mode='picked', picked=[1], quotas=[target(minimum=1)]))
        self.assertEqual(result['quotas'][0]['matching_movies'], 0)
        self.assertIn('Only 0 movies', result['quotas'][0]['reason'])

    def test_disabled_trailer_does_not_count_or_get_reenabled(self):
        movies = [movie(1, 'Disabled', cert='PG'), movie(2, 'Enabled', cert='PG')]
        self.sync(movies[:1], self.config(max_downloads=2))
        self.rows()['Disabled'].is_enabled = False; self.db.commit()
        result = self.sync(movies, self.config(max_downloads=2, quotas=[target(minimum=1)]))
        self.assertEqual(result['quotas'][0]['available'], 1)
        self.assertFalse(self.rows()['Disabled'].is_enabled)

    def test_storage_rejection_keeps_working_files_and_cleans_new_download(self):
        movies = [movie(1, 'Old', cert='R'), movie(2, 'Large', cert='PG')]
        self.sync(movies[:1], self.config(max_gb=0.2, max_downloads=1))
        old = self.rows()['Old'].local_path
        self.downloader.size_mb = 500
        result = self.sync(movies, self.config(max_gb=0.2, max_downloads=1, quotas=[target(minimum=1)]))
        self.assertTrue(os.path.isfile(old))
        self.assertEqual(result['downloaded'], 0)
        self.assertEqual(result['rotated'], 0)
        self.assertIn('storage limit', result['quotas'][0]['reason'])
        self.assertFalse(os.path.exists(os.path.join(self.downloader.folder, 'Large_1002_trailer.mp4')))

    def test_downloads_off_preserves_files_even_if_limits_lowered(self):
        movies = [movie(1, 'Old', cert='R')]
        self.sync(movies, self.config())
        path = self.rows()['Old'].local_path
        result = self.sync(movies, self.config(download=False, max_downloads=0, quotas=[target()]))
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(result['removed'], 0)

    def test_retained_genres_refresh_and_preview_uses_playback_metadata(self):
        old = movie(1, 'Retained', cert='PG', genres=['Comedy'])
        self.sync([old], self.config())
        updated = {**old, 'genres': ['Horror']}
        cfg = self.config(quotas=[target('genre', ['Horror'], 1)])
        before = tq.report([updated], self.rows().values(), cfg)
        self.assertEqual(before[0]['available'], 0)
        self.downloader.calls.clear()
        result = self.sync([updated], cfg)
        self.assertEqual(result['quotas'][0]['available'], 1)
        self.assertEqual(self.rows()['Retained'].genre_list(), ['Horror'])
        self.assertEqual(self.downloader.calls, [])

    def test_shrinking_hard_limit_preserves_target_when_possible(self):
        movies = [movie(1, 'R', cert='R'), movie(2, 'PG', cert='PG')]
        self.sync(movies, self.config(max_downloads=2))
        result = self.sync(movies, self.config(max_downloads=1, quotas=[target(minimum=1)]))
        self.assertEqual(result['removed'], 1)
        self.assertIn('PG', self.rows())
        self.assertEqual(result['quotas'][0]['shortfall'], 0)


@pytest.mark.parametrize('value', [None, {}, [{'kind': 'audio', 'values': ['PG'], 'min': 1}],
                                    [target(minimum=1.5)], [target(minimum=True)], [target(minimum=0)],
                                    [target(values=['12'])], [target()] * 13])
def test_invalid_targets_are_rejected(value):
    with pytest.raises(ValueError): tq.normalize_quotas(value, strict=True)


def test_unknown_international_rating_is_not_unrated_and_case_insensitive_genres():
    assert not tq.matches(movie(1, 'Foreign', cert='12'), target(values=['Unrated']))
    assert tq.matches(movie(1, 'Unknown', cert=None), target(values=['Unrated']))
    assert tq.matches(movie(1, 'Horror', genres=['HORROR']), target('genre', ['horror']))
