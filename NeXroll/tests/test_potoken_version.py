"""The YouTube PO-token provider: the version that must run, and the one to install.

Earlier bgutil servers listened on every network interface, and 2.0.0 fixed a
remote code execution hole reachable that way (GHSA-qpv9-8xfj-xx9m). NeXroll
started them with only --port, so an install older than 2.0.0 is left stopped
and offered as an update instead.

2.0.1 and 2.0.2 only update the server's npm dependencies for security
advisories. Raising the minimum to them would have stopped every working 2.0.0
install until its user clicked Update, so they are the release NeXroll
installs (PROVIDER_VERSION) while 2.0.0 stays the minimum: an older 2.0.x keeps
running and the pages offer the update.
"""
import json
import re
from pathlib import Path

import pytest

from backend import nexup_potoken as potoken


def provider(tmp_path, version):
    server = tmp_path / "bgutil-provider" / "server"
    (server / "build").mkdir(parents=True)
    (server / "build" / "main.js").write_text("// provider")
    (server / "package.json").write_text(json.dumps({"name": "bgutil-ytdlp-pot-provider", "version": version}))
    return server


def test_the_minimum_stays_at_the_security_fix():
    assert potoken.MIN_PROVIDER_VERSION == "2.0.0"


@pytest.mark.parametrize("version,outdated", [("1.3.1", True), ("1.3.2", True), ("2.0.0", False), ("2.1.0", False), ("10.0.0", False)])
def test_versions_before_2_0_0_are_outdated(tmp_path, version, outdated):
    assert potoken.provider_is_outdated(provider(tmp_path, version)) is outdated


@pytest.mark.parametrize("version,update", [("1.3.1", True), ("2.0.0", True), ("2.0.1", True),
                                            (potoken.PROVIDER_VERSION, False), ("2.1.0", False)])
def test_providers_older_than_the_release_nexroll_installs_can_update(tmp_path, version, update):
    assert potoken.provider_update_available(provider(tmp_path, version)) is update


def test_an_unreadable_version_is_not_called_outdated(tmp_path):
    server = tmp_path / "server"
    server.mkdir()
    assert potoken.provider_is_outdated(server) is False
    assert potoken.provider_is_outdated(None) is False
    assert potoken.provider_update_available(server) is False


def manager_for(tmp_path, monkeypatch, server):
    manager = potoken.POTokenManager(base_dir=str(tmp_path), log=lambda *a: None, port=4999)
    monkeypatch.setattr(manager, "server_dir", lambda: Path(server))
    monkeypatch.setattr(manager, "is_healthy", lambda timeout=3.0: False)
    monkeypatch.setattr(potoken, "find_node", lambda: "node")
    monkeypatch.setattr(potoken, "node_major_minor", lambda node: (22, 12))
    return manager


def test_an_outdated_provider_is_not_started(tmp_path, monkeypatch):
    manager = manager_for(tmp_path, monkeypatch, provider(tmp_path, "1.3.1"))
    monkeypatch.setattr(potoken.subprocess, "Popen", lambda *a, **k: pytest.fail("an outdated provider was started"))
    status = manager.start()
    assert status["outdated"] is True and status["update_available"] is False
    assert status["installed_version"] == "1.3.1" and status["required_version"] == potoken.MIN_PROVIDER_VERSION


class ExitedProcess:
    pid = 1
    returncode = 1

    def poll(self):
        return 1


def test_a_2_0_0_provider_still_starts_and_offers_the_update(tmp_path, monkeypatch):
    manager = manager_for(tmp_path, monkeypatch, provider(tmp_path, "2.0.0"))
    started = []
    monkeypatch.setattr(potoken.subprocess, "Popen", lambda cmd, **k: started.append(cmd) or ExitedProcess())
    status = manager.start()
    assert started and started[0][-2:] == ["--port", "4999"]
    assert status["outdated"] is False and status["update_available"] is True
    assert status["installed_version"] == "2.0.0"
    assert status["recommended_version"] == potoken.PROVIDER_VERSION


def test_the_current_release_offers_nothing(tmp_path, monkeypatch):
    manager = manager_for(tmp_path, monkeypatch, provider(tmp_path, potoken.PROVIDER_VERSION))
    status = manager.status()
    assert status["outdated"] is False and status["update_available"] is False


def test_the_image_the_installer_and_the_plugin_agree_on_the_version():
    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    requirements = (root / "requirements.txt").read_text(encoding="utf-8")
    assert f"ARG BGUTIL_VERSION={potoken.PROVIDER_VERSION}" in dockerfile
    assert f"bgutil-ytdlp-pot-provider>={potoken.PROVIDER_VERSION}" in requirements


def test_the_image_and_the_windows_install_override_basic_ftp_alike():
    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    main_py = (root / "NeXroll" / "backend" / "main.py").read_text(encoding="utf-8")
    docker = re.search(r"overrides\.basic-ftp=(\^[\d.]+)", dockerfile).group(1)
    windows = re.search(r'\["basic-ftp"\] = "(\^[\d.]+)"', main_py).group(1)
    assert docker == windows
    # 6.2.4 fixes GHSA-r4jh-29pc-gfqr and GHSA-5pm8-86m8-9m6r; the provider's
    # own override (2.0.2) pins 6.2.1.
    assert tuple(int(p) for p in docker[1:].split(".")) >= (6, 2, 4)
