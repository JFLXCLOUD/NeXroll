"""Security fixes: helpers are lifted out of backend/main.py with ast, as the
other backup tests do, so the app (and its dependencies) is not imported."""
import ast
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

SOURCE = ast.parse((Path(__file__).parents[1] / "backend" / "main.py").read_text(encoding="utf-8"))


def lift(*names, **env):
    nodes = []
    for node in SOURCE.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            node.decorator_list = []
            node.returns = None
            for arg in node.args.args:
                arg.annotation = None
            nodes.append(node)
    scope = dict(os=os, **env)
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), "<main>", "exec"), scope)
    return scope


class ApiKeyScopeTests(unittest.TestCase):
    def check(self, permissions, needed):
        record = SimpleNamespace(permissions=permissions, expires_at=None, last_used_at=None)
        query = SimpleNamespace(filter=lambda *a: SimpleNamespace(first=lambda: record))
        db = SimpleNamespace(query=lambda *a: query, commit=lambda: None)
        models = SimpleNamespace(APIKey=SimpleNamespace(key_hash=1, is_active=1))
        env = lift("validate_api_key", Optional=lambda x: x, _hash_api_key=lambda k: k, models=models,
                   utcnow=lambda: 0)
        return env["validate_api_key"]("k", needed, db) is not None

    def test_read_key_cannot_write(self):
        self.assertTrue(self.check("read", "read"))
        self.assertFalse(self.check("read", "write"))
        self.assertFalse(self.check("read", "full"))

    def test_full_key_can_do_everything(self):
        for needed in ("read", "write", "full"):
            self.assertTrue(self.check("full", needed))


class WithinDirectoryTests(unittest.TestCase):
    def test_traversal_absolute_and_symlink_are_refused(self):
        within = lift("_is_within_directory")["_is_within_directory"]
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as other:
            os.symlink(other, os.path.join(root, "link"))
            self.assertTrue(within(root, os.path.join(root, "a", "b.mp4")))
            self.assertFalse(within(root, os.path.join(root, "..", "x")))
            self.assertFalse(within(root, os.path.join(root, "/etc/passwd")))
            self.assertFalse(within(root, os.path.join(root, "link", "x")))


class SameOriginTests(unittest.TestCase):
    def test_origin_match(self):
        env = lift("_normalize_url", "_same_origin")
        same = env["_same_origin"]
        self.assertTrue(same("192.168.1.5:32400", "http://192.168.1.5:32400/"))
        self.assertTrue(same("https://plex.example", "https://PLEX.example:443"))
        self.assertFalse(same("http://evil.test:32400", "http://192.168.1.5:32400"))
        self.assertFalse(same("https://192.168.1.5:32400", "http://192.168.1.5:32400"))
        self.assertFalse(same("http://192.168.1.5:9999", "http://192.168.1.5:32400"))
        self.assertFalse(same("ftp://192.168.1.5:32400", "http://192.168.1.5:32400"))


class BackupSecretsTests(unittest.TestCase):
    def test_export_redacts_keys_and_restore_keeps_existing_ones(self):
        import datetime
        columns = [SimpleNamespace(name=n) for n in ("id", "plex_url", "nexup_radarr_api_key", "plex_token")]
        models = SimpleNamespace(Setting=SimpleNamespace(__table__=SimpleNamespace(columns=columns)))
        scope = lift("_export_settings", models=models, datetime=datetime, _SETTINGS_BACKUP_SKIP={"id"},
                     _SETTINGS_SECRET_COLUMNS=frozenset({"plex_token", "nexup_radarr_api_key"}))
        row = SimpleNamespace(id=1, plex_url="http://p", nexup_radarr_api_key="K", plex_token="T")
        self.assertEqual(scope["_export_settings"](row)["nexup_radarr_api_key"], "K")
        redacted = scope["_export_settings"](row, include_secrets=False)
        self.assertEqual(redacted, {"plex_url": "http://p"})

        restore = lift("_restore_settings", models=models, _SETTINGS_BACKUP_SKIP={"id"},
                       _SETTINGS_SECRET_COLUMNS=frozenset({"plex_token", "nexup_radarr_api_key"}),
                       _SETTINGS_CATEGORY_FKS=(), _SETTINGS_SEQUENCE_FKS=(), _SETTINGS_PREROLL_IDS=(),
                       _SETTINGS_DATETIME_COLUMNS=(), _SETTINGS_PATH_COLUMNS=(), _SETTINGS_FILE_PATH_COLUMNS=(),
                       _file_log=lambda *a: None, Optional=lambda x: x)["_restore_settings"]
        db = SimpleNamespace(query=lambda *a: SimpleNamespace(first=lambda: row))
        restore(db, {"plex_url": "http://new", "nexup_radarr_api_key": "", "plex_token": None}, {}, {})
        self.assertEqual((row.plex_url, row.nexup_radarr_api_key, row.plex_token), ("http://new", "K", "T"))


class SecretsFileModeTests(unittest.TestCase):
    def test_secrets_file_is_owner_only(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("secure_store", Path(__file__).parents[1] / "backend" / "secure_store.py")
        store = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(store)
        with tempfile.TemporaryDirectory() as root:
            old = dict(os.environ)
            os.environ["NEXROLL_SECRETS_DIR"] = root
            try:
                path = os.path.join(root, "secrets.json")
                open(path, "w").write("{}")
                os.chmod(path, 0o644)
                os.chmod(root, 0o755)
                store._secrets_file_path()
                self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
                self.assertEqual(os.stat(root).st_mode & 0o777, 0o700)
                os.remove(path)
                store._atomic_write(path, b"{}")
                self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            finally:
                os.environ.clear()
                os.environ.update(old)


class DownloadTargetTests(unittest.TestCase):
    def test_only_public_http_targets(self):
        check = lift("_normalize_url", "_same_origin", "_check_download_target")["_check_download_target"]
        check("http://8.8.8.8/a.mp4")
        for bad in ("http://127.0.0.1/x", "http://10.1.2.3/x", "http://192.168.0.5:9393/x",
                    "http://169.254.169.254/latest", "http://[::1]/x", "http://0.0.0.0/x",
                    "file:///etc/passwd", "ftp://8.8.8.8/x", "http:///x"):
            with self.subTest(url=bad), self.assertRaises(ValueError):
                check(bad)
        check("http://192.168.0.5:8080/a.mp4", "http://192.168.0.5:8080")  # the configured community server
        with self.assertRaises(ValueError):
            check("http://192.168.0.5:9999/a.mp4", "http://192.168.0.5:8080")


if __name__ == "__main__":
    unittest.main()
