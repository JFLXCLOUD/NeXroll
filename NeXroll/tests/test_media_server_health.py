import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import requests

from backend import health_summary, media_server_health as health


def response(status=200, data=None, content=b''):
    res = Mock(status_code=status, content=content)
    res.json.return_value = data if data is not None else {"Id": "server-id", "Version": "1.0"}
    res.__enter__ = Mock(return_value=res)
    res.__exit__ = Mock(return_value=False)
    return res


@pytest.mark.parametrize('name,path,header', [
    ('Plex', '/base/', 'X-Plex-Token'),
    ('Jellyfin', '/base/System/Info', 'Authorization'),
    ('Emby', '/base/emby/System/Info', 'X-Emby-Token'),
])
def test_authenticated_probe_and_shutdown_recovery(name, path, header):
    good = response(content=b'<MediaContainer machineIdentifier="server-id"/>')
    with patch.object(health.requests, 'get', side_effect=[good, requests.ConnectionError('secret'), good]) as get:
        states = [health.probe_server(name, 'http://server/base', 'secret') for _ in range(3)]
    assert [s['status'] for s in states] == ['ok', 'error', 'ok']
    assert states[1]['detail'] == f'No connection to media server ({name})'
    assert get.call_args.args[0] == 'http://server' + path
    assert header in get.call_args.kwargs['headers']
    assert get.call_args.kwargs['timeout'] == (3, 3)
    assert get.call_args.kwargs['allow_redirects'] is False


@pytest.mark.parametrize('status', [401, 403, 500, 302])
def test_failed_http_is_not_healthy(status):
    with patch.object(health.requests, 'get', return_value=response(status)):
        result = health.probe_server('Jellyfin', 'http://server', 'secret')
    assert result['status'] == 'error'
    assert 'secret' not in str(result)
    if status in (401, 403):
        assert 'rejected its credentials' in result['detail']


@pytest.mark.parametrize('data', [{}, [], {'Id': 'id'}, {'Version': '1'}])
def test_proxy_or_wrong_service_does_not_count(data):
    with patch.object(health.requests, 'get', return_value=response(data=data)):
        assert health.probe_server('Jellyfin', 'http://server', 'secret')['status'] == 'error'


def test_invalid_xml_and_json_do_not_count():
    invalid = response(content=b'<html>Login</html>')
    invalid.json.side_effect = ValueError('invalid json')
    with patch.object(health.requests, 'get', return_value=invalid):
        for name in ('Plex', 'Jellyfin', 'Emby'):
            assert health.probe_server(name, 'http://server', 'secret')['status'] == 'error'


@pytest.mark.parametrize('error', [requests.Timeout(), requests.exceptions.SSLError()])
def test_timeout_and_certificate_failure(error):
    with patch.object(health.requests, 'get', side_effect=error):
        assert health.probe_server('Jellyfin', 'http://server', 'secret')['status'] == 'error'


def test_missing_credentials_and_plugin_registration_do_not_prove_connectivity():
    with patch.object(health.requests, 'get') as get:
        assert health.probe_server('Jellyfin', 'http://server', None)['status'] == 'error'
        assert health.probe_server('Jellyfin', None, None)['status'] == 'warn'
        get.assert_not_called()


@pytest.mark.parametrize('name,attr', [('Plex', 'plex_token'), ('Jellyfin', 'jellyfin_api_key'), ('Emby', 'emby_api_key')])
@pytest.mark.parametrize('legacy', [False, True])
def test_secure_store_and_legacy_database_credentials(name, attr, legacy):
    setting = SimpleNamespace(**{name.lower() + '_url': 'http://server', attr: 'legacy' if legacy else None})
    with patch.object(health.secure_store, 'get_' + attr, return_value='secure'), \
         patch.object(health, 'probe_server', return_value={'name': name, 'status': 'ok', 'detail': ''}) as probe:
        health.check_media_servers(setting, [{'server_type': name}])
    probe.assert_called_once_with(name, 'http://server', 'legacy' if legacy else 'secure')


def test_stale_plugin_never_masks_failed_direct_connection():
    setting = SimpleNamespace(jellyfin_url='http://offline', jellyfin_api_key='secret')
    with patch.object(health.requests, 'get', side_effect=requests.ConnectionError()):
        results = health.check_media_servers(setting, [{'server_type': 'Jellyfin', 'last_seen': '2020-01-01'}])
    assert results[0]['status'] == 'error'


def test_no_configuration_does_not_probe():
    with patch.object(health.requests, 'get') as get:
        assert health.check_media_servers(None, []) == []
        get.assert_not_called()


def test_emby_url_already_contains_prefix():
    with patch.object(health.requests, 'get', return_value=response()) as get:
        health.probe_server('Emby', 'http://server/emby/', 'secret')
    assert get.call_args.args[0] == 'http://server/emby/System/Info'


def test_summary_endpoint_uses_live_results_and_never_hides_probe_failure():
    # Execute the actual route without importing main's startup workers.
    tree = ast.parse((Path(__file__).parents[1] / 'backend/main.py').read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'system_health_summary')
    node.decorator_list = []
    node.returns = None
    node.args.defaults = []
    for arg in node.args.args:
        arg.annotation = None
    env = dict(health_summary=health_summary, models=SimpleNamespace(Setting=object(), Preroll=object()),
               scheduler=SimpleNamespace(running=True, thread=SimpleNamespace(is_alive=lambda: True)),
               PLUGIN_CLIENTS={}, _LAST_SCAN_STATS={}, PREROLLS_INDEX_PATH=None)
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<health-route>', 'exec'), env)
    db = Mock()
    db.query.return_value.count.return_value = 1
    offline = [{'name': 'Jellyfin', 'status': 'error', 'detail': 'No connection to media server (Jellyfin)'}]
    with patch.object(health, 'check_media_servers', return_value=offline):
        summary = env['system_health_summary'](0, db)
    assert summary['status'] == 'degraded'
    assert summary['note'] == offline[0]['detail']
    with patch.object(health, 'check_media_servers', side_effect=RuntimeError('secret')):
        summary = env['system_health_summary'](0, db)
    assert summary['status'] == 'attention'
    assert 'Unable to check' in summary['note']
    assert 'secret' not in str(summary)
