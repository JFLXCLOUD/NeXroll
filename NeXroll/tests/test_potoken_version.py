"""The YouTube PO-token provider must be 2.0.0 or later.

Earlier bgutil servers listened on every network interface, and 2.0.0 fixed a
remote code execution hole reachable that way (GHSA-qpv9-8xfj-xx9m). NeXroll
started them with only --port, so an old install is left stopped and offered as
an update instead.
"""
import json
from pathlib import Path

import pytest

from backend import nexup_potoken as potoken


def provider(tmp_path, version):
    server = tmp_path / "bgutil-provider" / "server"
    (server / "build").mkdir(parents=True)
    (server / "build" / "main.js").write_text("// provider")
    (server / "package.json").write_text(json.dumps({"name": "bgutil-ytdlp-pot-provider", "version": version}))
    return server


@pytest.mark.parametrize("version,outdated", [("1.3.1", True), ("1.3.2", True), ("2.0.0", False), ("2.1.0", False), ("10.0.0", False)])
def test_versions_before_2_0_0_are_outdated(tmp_path, version, outdated):
    assert potoken.provider_is_outdated(provider(tmp_path, version)) is outdated


def test_an_unreadable_version_is_not_called_outdated(tmp_path):
    server = tmp_path / "server"
    server.mkdir()
    assert potoken.provider_is_outdated(server) is False
    assert potoken.provider_is_outdated(None) is False


def test_an_outdated_provider_is_not_started(tmp_path, monkeypatch):
    server = provider(tmp_path, "1.3.1")
    manager = potoken.POTokenManager(base_dir=str(tmp_path), log=lambda *a: None, port=4999)
    monkeypatch.setattr(manager, "server_dir", lambda: Path(server))
    monkeypatch.setattr(manager, "is_healthy", lambda timeout=3.0: False)
    monkeypatch.setattr(potoken, "find_node", lambda: "node")
    monkeypatch.setattr(potoken.subprocess, "Popen", lambda *a, **k: pytest.fail("an outdated provider was started"))
    status = manager.start()
    assert status["outdated"] is True
    assert status["installed_version"] == "1.3.1" and status["required_version"] == potoken.PROVIDER_VERSION


def test_the_image_the_installer_and_the_plugin_agree_on_the_version():
    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    requirements = (root / "requirements.txt").read_text(encoding="utf-8")
    assert f"ARG BGUTIL_VERSION={potoken.PROVIDER_VERSION}" in dockerfile
    assert f"bgutil-ytdlp-pot-provider>={potoken.PROVIDER_VERSION}" in requirements
