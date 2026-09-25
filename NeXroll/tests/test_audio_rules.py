import datetime
import json
from unittest.mock import Mock, patch

import pytest

from backend import media_audio as audio, models, scheduler
from backend.sequence_conditions import PlaybackContext, evaluate_rule, sequence_block_to_play
from backend.trailer_filters import has_trailer_policy
from tests.test_trailer_filters import db, route


def stream(codec='dts', **kwargs):
    return {'Type': 'Audio', 'Codec': codec, 'Index': 1, **kwargs}


def details(*streams, **kwargs):
    return audio.describe_audio({'MediaSources': [{'MediaStreams': list(streams), **kwargs}]})


@pytest.mark.parametrize('raw,expected', [('AC-3', 'ac3'), ('e_ac_3', 'eac3'), ('TRUEHD', 'truehd'),
    ('DCA', 'dts'), ('DTS-HD MA', 'dts'), ('pcm_s24le', 'pcm'), ('aac', 'aac'), ('flac', 'flac'),
    ('THX', None), ('Atmos', None), ('MLP', None), (None, None)])
def test_codec_mapping_does_not_infer_branded_spatial_formats(raw, expected):
    assert audio.codec_format(raw) == expected


def test_default_track_uses_explicit_index_flag_or_single_track():
    assert details(stream('ac3'))['default'] == 'ac3'
    assert details(stream('dts', IsDefault=True), stream('aac', Index=2))['default'] == 'dts'
    assert details(stream('dts'), stream('aac', Index=2), DefaultAudioStreamIndex=2)['default'] == 'aac'
    assert details(stream('dts'), stream('aac', Index=2))['default'] is None
    assert details(stream('dts', IsDefault=True), stream('aac', Index=2, IsDefault=True))['default'] is None
    assert details(stream('dts'), DefaultAudioStreamIndex=99)['default'] is None


def test_multiple_editions_and_missing_metadata_are_unknown_default():
    got = audio.describe_audio({'MediaSources': [{'MediaStreams': [stream('dts')]}, {'MediaStreams': [stream('ac3')]}]})
    assert got['default'] is None and got['formats'] == ['ac3', 'dts']
    assert audio.describe_audio({}) is None
    assert audio.describe_audio({'MediaStreams': [stream('ac3')]})['default'] == 'ac3'


def test_partial_metadata_can_match_any_known_track_but_cannot_prove_unless():
    got = details(stream('dts'), stream(None, Index=2))
    assert audio.matches_audio(got, ['dts'], 'any') is True
    assert audio.matches_audio(got, ['ac3'], 'any') is None
    assert audio.matches_audio(details(stream('dts')), ['ac3'], 'any') is False
    assert audio.matches_audio(details(stream('dts')), [], 'any') is None


def test_rule_unknown_is_not_negated_to_true_and_lookup_is_lazy_cached(db):
    lookup = Mock(return_value=None)
    ctx = PlaybackContext(now=datetime.datetime(2026, 9, 25), audio_lookup=lookup)
    for negate in (False, True):
        assert evaluate_rule({'kind': 'audio_format', 'values': ['dts'], 'negate': negate}, ctx) is None
    assert lookup.call_count == 1
    with patch.object(audio, 'item_audio', return_value=details(stream('dts'))) as get:
        ctx = scheduler.playback_context(db, item_id='item', server_type='jellyfin')
        get.assert_not_called()
        for _ in range(2): assert evaluate_rule({'kind': 'audio_format', 'values': ['dts']}, ctx)
        assert get.call_count == 1


def test_lookup_uses_named_server_and_connection_scoped_cache():
    audio._cache.clear()
    servers = [('emby', 'http://emby', {'X-Emby-Token': 'fake'}, '/emby'),
               ('jellyfin', 'http://jf', {'Authorization': 'fake'}, '')]
    with patch('backend.media_genres._servers', return_value=servers), patch.object(audio.requests, 'get') as get:
        get.return_value.json.return_value = {'Items': [{'MediaStreams': [stream('dts')]}]}
        assert audio.item_audio(None, 'same-id', 'jellyfin')['default'] == 'dts'
        assert get.call_args.args[0] == 'http://jf/Items'
        assert get.call_args.kwargs['timeout'] == 1.0
        assert audio.item_audio(None, 'same-id', 'jellyfin')['default'] == 'dts'
        assert get.call_count == 1
        servers[1] = ('jellyfin', 'http://new-jf', {'Authorization': 'new'}, '')
        audio.item_audio(None, 'same-id', 'jellyfin')
        assert get.call_count == 2
        get.side_effect = OSError('offline')
        assert audio.item_audio(None, 'other', 'jellyfin') is None
        assert get.call_count == 3  # no Emby fallback
        assert audio.item_audio(None, 'same-id', 'plex') is None
        assert audio.item_audio(None, '0', 'emby') is None
        assert get.call_count == 3
    audio._cache.clear()


def test_preview_and_alternative_use_the_same_rules(db):
    blocks = [{'type': 'fixed', 'preroll_ids': [1], 'condition': {'rules': [
        {'kind': 'audio_format', 'values': ['dts'], 'track': 'default'}]},
        'otherwise': {'type': 'random', 'category_id': 1}}]
    ctx = scheduler.playback_context(db, audio_format='dts')
    assert sequence_block_to_play(blocks, 0, ctx) is blocks[0]
    ctx = scheduler.playback_context(db)
    assert sequence_block_to_play(blocks, 0, ctx) is blocks[0]['otherwise']
    from backend.sequence_conditions import describe_condition
    from fastapi import HTTPException
    evaluate = route('evaluate_sequence_conditions', sequence_block_to_play=sequence_block_to_play,
                     describe_condition=describe_condition, HTTPException=HTTPException)
    assert evaluate(blocks, 'movie', None, db, 'dts')['blocks'][0]['outcome'] == 'plays'
    assert evaluate(blocks, 'movie', None, db, None)['blocks'][0]['outcome'] == 'otherwise'
    with pytest.raises(HTTPException): evaluate(blocks, 'movie', None, db, 'Atmos')


@pytest.mark.parametrize('selection', ['manual', 'schedule', 'filler'])
def test_unknown_audio_skip_never_falls_back_to_active_category(db, tmp_path, selection):
    path = tmp_path / 'unrestricted.mp4'; path.write_bytes(b'x')
    category = models.Category(name='Unrestricted'); db.add(category); db.flush()
    preroll = models.Preroll(filename=path.name, path=str(path), category_id=category.id, enabled=True)
    db.add(preroll); db.flush()
    blocks = [{'type': 'fixed', 'preroll_ids': [preroll.id], 'condition': {'rules': [
        {'kind': 'audio_format', 'values': ['dts']}]}}]
    assert has_trailer_policy(blocks)
    saved = models.SavedSequence(name='Audio', blocks=json.dumps(blocks));db.add(saved);db.flush()
    setting = db.query(models.Setting).first(); setting.active_category = category.id
    if selection == 'manual':
        setting.applied_sequence_id = saved.id; setting.override_expires_at = datetime.datetime(2026, 9, 26)
    elif selection == 'filler': setting.filler_active = f'sequence:{saved.id}'
    else:
        row = models.Schedule(name='Audio', type='daily', start_date=datetime.datetime(2026, 1, 1),
                              category_id=category.id, sequence=json.dumps(blocks), is_active=True)
        db.add(row);db.flush();setting.active_schedule_id=row.id
    db.commit()
    assert route('_resolve_current_intros')(db)['paths'] == []


def test_audio_only_empty_plex_schedule_clears_previous_list(db):
    setting = db.query(models.Setting).first(); setting.plex_url='http://plex.invalid';setting.plex_token='fake';db.commit()
    schedule = models.Schedule(id=77, name='Audio', type='daily', start_date=datetime.datetime(2026,1,1),
        sequence=json.dumps([{'type':'fixed','preroll_ids':[1], 'condition':{'rules':[{'kind':'audio_format','values':['dts']}]}}]))
    worker = scheduler.Scheduler(); connector=Mock();connector.set_preroll.return_value=True
    with patch.object(scheduler,'PlexConnector',return_value=connector), patch.object(worker,'_defer_preroll_write',return_value=False):
        assert worker._apply_schedule_sequence_to_plex(schedule,db).plex
    connector.set_preroll.assert_called_once_with('')


def test_emby_metadata_request_and_default_index():
    audio._cache.clear()
    servers = [('emby', 'http://emby', {'X-Emby-Token': 'fake'}, '/emby')]
    with patch('backend.media_genres._servers', return_value=servers), patch.object(audio.requests, 'get') as get:
        get.return_value.json.return_value = {'Items': [{'MediaSources': [{
            'DefaultAudioStreamIndex': 2, 'MediaStreams': [stream('aac'), stream('eac3', Index=2)]}]}]}
        result = audio.item_audio(None, 'emby-item', 'emby')
        assert result == {'default': 'eac3', 'formats': ['aac', 'eac3'], 'complete': True}
        assert get.call_args.args[0] == 'http://emby/emby/Items'
        assert get.call_args.kwargs['params']['Ids'] == 'emby-item'
    audio._cache.clear()


def test_export_preserves_audio_rule_scopes_and_negation(db):
    import ast
    from fastapi import HTTPException
    from tests.test_trailer_filters import main_ast
    constants = {}
    for node in main_ast().body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in ('_PORTABLE_BLOCK_FIELDS', '_PORTABLE_OTHERWISE_TYPES'):
            constants[node.targets[0].id] = ast.literal_eval(node.value)
    otherwise = route('_export_otherwise_block', **constants)
    export = route('_build_sequence_export', **constants, _export_otherwise_block=otherwise,
                   app_version='test', HTTPException=HTTPException, _file_log=Mock(), log_event=Mock())
    for scope in ('default', 'any'):
        block = {'type': 'library_trailers', 'count': 1, 'condition': {'match': 'all', 'rules': [
            {'kind': 'audio_format', 'values': ['dts', 'truehd'], 'track': scope, 'negate': True}]}}
        exported = export('Audio', '', [block], 'pattern_only', db)['blocks'][0]
        assert exported['condition'] == block['condition']
