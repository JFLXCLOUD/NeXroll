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


class CommunityFileUrlTests(unittest.TestCase):
    def url(self, preroll_id="", sent="", base="https://prerolls.uk"):
        env = lift("_community_file_url", _get_community_base_url=lambda db: base)
        return env["_community_file_url"](None, preroll_id, sent)

    def test_always_the_server_in_use_plus_the_path(self):
        path = "/Holidays/Christmas/Snow%20-%20Plex.mp4"
        self.assertEqual(self.url(path), "https://prerolls.uk" + path)
        # The url stored in an index built on a server that has gone is ignored.
        self.assertEqual(self.url(path, "https://usa.prerolls.uk" + path), "https://prerolls.uk" + path)
        self.assertEqual(self.url(path, base="https://home.prerolls.uk/"), "https://home.prerolls.uk" + path)

    def test_a_sent_url_only_gives_its_path(self):
        self.assertEqual(self.url("", "http://127.0.0.1:9393/backup/database"), "https://prerolls.uk/backup/database")
        self.assertEqual(self.url("", "http://169.254.169.254/latest/meta-data?x=1"),
                         "https://prerolls.uk/latest/meta-data")

    def test_nothing_usable_gives_nothing(self):
        for preroll_id, sent in (("", ""), ("", "https://evil.test"), ("//evil.test/x.mp4", ""), ("/a\\b.mp4", "")):
            with self.subTest(preroll_id=preroll_id, sent=sent):
                self.assertEqual(self.url(preroll_id, sent), "")
        self.assertEqual(self.url("/x.mp4", base=None), "")


@unittest.skipIf(os.name == "nt", "file modes apply on Linux and macOS; Windows uses the folder's ACLs")
class SecretsFileModeTests(unittest.TestCase):
    def test_secrets_file_is_owner_only(self):
        from backend import secure_store
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "secrets.json")
            secure_store._atomic_write(path, b"{}")
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            os.chmod(path, 0o644)  # as written before 2.3.0
            secure_store._owner_only(path)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
