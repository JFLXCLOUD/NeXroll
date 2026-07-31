from __future__ import annotations

from .errors import ConfigurationError


AUTOMOD_BEGIN = "# BEGIN NEXROLL MANAGED RULES"
AUTOMOD_END = "# END NEXROLL MANAGED RULES"
SIDEBAR_BEGIN = "<!-- BEGIN NEXROLL MANAGED SIDEBAR -->"
SIDEBAR_END = "<!-- END NEXROLL MANAGED SIDEBAR -->"


def merge_managed_block(
    existing: str | None,
    desired: str,
    *,
    begin: str,
    end: str,
    label: str,
) -> str:
    current = str(existing or "").replace("\r\n", "\n").replace("\r", "\n")
    managed = str(desired or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    begin_count = current.count(begin)
    end_count = current.count(end)

    if begin_count == 0 and end_count == 0:
        prefix = current.rstrip()
        separator = "\n\n" if prefix else ""
        return f"{prefix}{separator}{begin}\n{managed}\n{end}\n"
    if begin_count != 1 or end_count != 1:
        raise ConfigurationError(
            f"{label} has malformed NeXroll management markers. "
            "Nothing will be changed until the markers are repaired."
        )

    start = current.find(begin)
    finish = current.find(end)
    if finish < start:
        raise ConfigurationError(
            f"{label} has reversed NeXroll management markers. "
            "Nothing will be changed until the markers are repaired."
        )
    finish += len(end)
    replacement = f"{begin}\n{managed}\n{end}"
    return f"{current[:start]}{replacement}{current[finish:]}"
