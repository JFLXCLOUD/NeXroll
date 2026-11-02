#!/bin/sh
# NeXroll's container entrypoint.
#
# NeXroll runs as root, as it always has, unless NEXROLL_RUN_AS_PUID is true.
# Then it runs as PUID:PGID (default 99:100, the Unraid convention): this
# script creates that user, gives it the files NeXroll created as root (in
# /data and in the preroll and NeX-Up folders set in Settings; files that
# belong to anyone else are left alone), and starts NeXroll as that user.
#
# PUID and PGID were documented, and set by the Unraid template, for years
# before the image used them, so honouring them by default would have changed
# the user of every existing install on update. Hence the explicit switch.
#
# Once the switch is on, it fails closed: if NeXroll can't be dropped to
# PUID:PGID (bad IDs, PUID 0, /data not writable by that user), the container
# refuses to start instead of quietly running as root. Set NEXROLL_ALLOW_ROOT=true
# to allow the root fallback.
set -eu

truthy() {
    case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
        1|true|yes|on) return 0 ;;
        *) return 1 ;;
    esac
}

say() {
    printf 'NeXroll: %s\n' "$*" >&2
}

# The drop was asked for but can't be done: stop, unless root is explicitly
# allowed (then return, and the caller starts NeXroll as root).
root_or_stop() {
    if truthy "${NEXROLL_ALLOW_ROOT:-}"; then
        say "$1 NEXROLL_ALLOW_ROOT is true, so NeXroll is running as root."
        return 0
    fi
    say "$1 Refusing to run as root; fix this, or set NEXROLL_ALLOW_ROOT=true to allow it."
    exit 1
}

# Off, or already started as another user (Docker's `user:` setting): run as is.
if ! truthy "${NEXROLL_RUN_AS_PUID:-}" || [ "$(id -u)" != "0" ]; then
    if [ "$(id -u)" = "0" ]; then
        say "WARNING: running as root. Set NEXROLL_RUN_AS_PUID=true (with PUID/PGID) to run as a normal user."
    fi
    exec "$@"
fi

PUID="${PUID:-99}"
PGID="${PGID:-100}"
case "$PUID:$PGID" in
    *[!0-9:]*|:*|*:)
        root_or_stop "PUID and PGID must be numbers (got '$PUID' and '$PGID')."
        exec "$@"
        ;;
esac
if [ "$PUID" = "0" ]; then
    root_or_stop "PUID is 0."
    exec "$@"
fi

# The group and user, unless the image already has ones with these IDs.
if ! getent group "$PGID" >/dev/null 2>&1; then
    groupadd --gid "$PGID" nexroll
fi
if ! getent passwd "$PUID" >/dev/null 2>&1; then
    useradd --uid "$PUID" --gid "$PGID" --no-create-home --home-dir /data/.home \
        --shell /usr/sbin/nologin nexroll
fi

# Where NeXroll writes: /data, the preroll folder, and the preroll and NeX-Up
# folders set in Settings (read from the database, one path per line).
list_folders() {
    printf '%s\n' /data
    [ -n "${NEXROLL_PREROLL_PATH:-}" ] && printf '%s\n' "$NEXROLL_PREROLL_PATH"
    db="${NEXROLL_DB_PATH:-${NEXROLL_DB_DIR:-/data}/nexroll.db}"
    if [ -f "$db" ]; then
        python - "$db" <<'PY' 2>/dev/null || true
import sqlite3, sys
try:
    con = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True, timeout=5)
    names = {r[1] for r in con.execute("PRAGMA table_info(settings)")}
    cols = [c for c in ("preroll_folder", "nexup_storage_path") if c in names]
    row = con.execute(f"SELECT {', '.join(cols)} FROM settings LIMIT 1").fetchone() if cols else None
    for value in row or ():
        if value and value.strip().startswith("/"):
            print(value.strip())
except Exception:
    pass
PY
    fi
}

mkdir -p /data/.home

# Never the image's own files, whatever a setting says.
system_folder() {
    case "$1" in
        /|/app|/app/*|/bin|/bin/*|/boot|/boot/*|/dev|/dev/*|/etc|/etc/*|/lib|/lib/*|/lib64|/lib64/*|\
        /opt|/opt/*|/proc|/proc/*|/root|/root/*|/run|/run/*|/sbin|/sbin/*|/sys|/sys/*|/usr|/usr/*|\
        /var|/var/*|/tmp|/tmp/*) return 0 ;;
        *) return 1 ;;
    esac
}

# Hand over what NeXroll created as root. Only root-owned entries change, so
# media that belongs to anyone else stays as it is. A share that refuses
# chown (CIFS, NFS with root squash) is reported, not fatal.
list_folders | sort -u | while IFS= read -r folder; do
    [ -d "$folder" ] || continue
    if system_folder "$folder"; then
        say "not changing owners in $folder (a system folder); check that setting."
        continue
    fi
    if ! find "$folder" -user 0 -exec chown -h "$PUID:$PGID" {} + 2>/dev/null; then
        say "could not give everything in $folder to $PUID:$PGID; check its permissions on the host."
    fi
done

can_write() {
    setpriv --reuid="$PUID" --regid="$PGID" --clear-groups test -w "$1"
}

# Without its data folder NeXroll can't start as that user.
if ! can_write /data; then
    root_or_stop "user $PUID:$PGID can't write to /data; give that user the folder mounted at /data on the host."
    exec "$@"
fi
list_folders | sort -u | while IFS= read -r folder; do
    if [ -d "$folder" ] && ! can_write "$folder"; then
        say "user $PUID:$PGID can't write to $folder; uploads and downloads there will fail until it can."
    fi
done

export HOME=/data/.home
say "running as $PUID:$PGID."
exec setpriv --reuid="$PUID" --regid="$PGID" --clear-groups "$@"
