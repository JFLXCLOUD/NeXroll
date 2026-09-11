import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.jellyfin_auth import jellyfin_auth_headers
from backend.jellyfin_connector import JellyfinConnector


class JellyfinAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Path(self.temp.name) / 'jellyfin_config.json'
        finder = patch.object(JellyfinConnector, '_find_config_file', return_value=str(self.config))
        finder.start()
        self.addCleanup(finder.stop)

    def assert_token(self, connector, token):
        self.assertIn(f'Token={json.dumps(token)}', connector.headers['Authorization'])
        self.assertNotIn('X-Emby-Token', connector.headers)
        self.assertNotIn('X-MediaBrowser-Token', connector.headers)

    def test_manual_api_key_is_sent_to_plugin_list_in_authorization_header(self):
        connector = JellyfinConnector('http://jellyfin:8096', 'manual-key')
        with patch('backend.jellyfin_connector.requests.request') as request:
            request.return_value.status_code = 200
            request.return_value.content = b'[]'
            request.return_value.json.return_value = []
            self.assertEqual(connector.list_plugins(), [])
            self.assertIn('Token="manual-key"', request.call_args.kwargs['headers']['Authorization'])
        self.assert_token(connector, 'manual-key')

    def test_saved_key_uses_same_authentication_after_restart(self):
        with patch('backend.jellyfin_connector.secure_store.get_jellyfin_api_key', return_value='saved-key'):
            self.assert_token(JellyfinConnector('http://jellyfin:8096'), 'saved-key')

    def test_key_replacement_updates_header_and_does_not_write_secret_to_json(self):
        connector = JellyfinConnector('http://jellyfin:8096', 'old-key')
        with patch('backend.jellyfin_connector.secure_store.set_jellyfin_api_key', return_value=True):
            self.assertTrue(connector.save_stable_key('replacement-key'))
        self.assert_token(connector, 'replacement-key')
        self.assertNotIn('replacement-key', self.config.read_text())

    def test_legacy_key_migration_uses_modern_header_and_removes_plaintext(self):
        self.config.write_text(json.dumps({'api_key':'legacy-key'}))
        with patch('backend.jellyfin_connector.secure_store.get_jellyfin_api_key', return_value=None), \
             patch('backend.jellyfin_connector.secure_store.set_jellyfin_api_key', return_value=True):
            self.assert_token(JellyfinConnector('http://jellyfin:8096'), 'legacy-key')
        self.assertNotIn('api_key', json.loads(self.config.read_text()))

    def test_missing_and_malformed_keys(self):
        self.assertEqual(jellyfin_auth_headers(None), {})
        self.assertEqual(jellyfin_auth_headers('  '), {})
        self.assertIn('Token="key"', jellyfin_auth_headers(' key ')['Authorization'])
        with self.assertRaises(ValueError):
            jellyfin_auth_headers('key\r\nInjected: value')


if __name__ == '__main__':
    unittest.main()
