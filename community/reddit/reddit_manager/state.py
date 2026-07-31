from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .snapshot_io import write_json_atomic


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_local_state(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        return {"schema_version": 1, "branding": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": 1, "branding": {}}
    if not isinstance(value, dict):
        return {"schema_version": 1, "branding": {}}
    branding = value.get("branding")
    if not isinstance(branding, dict):
        branding = {}
    return {"schema_version": 1, "branding": branding}


def managed_branding_hashes(path: Path) -> dict[str, str]:
    branding = read_local_state(path)["branding"]
    return {
        key: value["sha256"]
        for key, value in branding.items()
        if isinstance(value, dict) and isinstance(value.get("sha256"), str)
    }


def mark_branding_applied(
    state_path: Path, *, asset_kind: str, asset_path: Path, digest: str
) -> None:
    state = read_local_state(state_path)
    state["branding"][asset_kind] = {
        "sha256": digest,
        "source": Path(asset_path).name,
    }
    write_json_atomic(Path(state_path), state)
