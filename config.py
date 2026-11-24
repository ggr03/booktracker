"""
Per-OS file locations and user configuration for Book Tracker.

Everything platform-specific about *where files live* is in this one
module, so the rest of the app never has to care whether it's running on
Linux, macOS, or Windows.

Locations (overridable with environment variables, see below):

    Linux / BSD   config: $XDG_CONFIG_HOME/booktracker   (~/.config/booktracker)
                  data:   $XDG_DATA_HOME/booktracker     (~/.local/share/booktracker)
    macOS         config + data: ~/Library/Application Support/Book Tracker
    Windows       config: %APPDATA%\\BookTracker
                  data:   %LOCALAPPDATA%\\BookTracker

Settings come from, highest priority first:
  1. environment variables (HARDCOVER_API_TOKEN, GOOGLE_BOOKS_API_KEY,
     BOOKTRACKER_DB, BOOKTRACKER_HOST, BOOKTRACKER_PORT, ...)
  2. config.ini in the config directory above (created by
     `python app.py init-config`, readable only by you)
  3. built-in defaults

Only the standard library is used here (configparser, not tomllib), so
this has no dependencies beyond Python itself (3.11+).
"""
from __future__ import annotations

import configparser
import os
import sys
from pathlib import Path
from typing import Optional

APP_DIR = Path(__file__).resolve().parent
_SLUG = "booktracker"
_MAC_WIN_NAME_MAC = "Book Tracker"
_MAC_WIN_NAME_WIN = "BookTracker"

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"


def config_dir() -> Path:
    override = os.environ.get("BOOKTRACKER_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    if IS_WINDOWS:
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / _MAC_WIN_NAME_WIN
    if IS_MACOS:
        return Path.home() / "Library" / "Application Support" / _MAC_WIN_NAME_MAC
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / _SLUG


def data_dir() -> Path:
    override = os.environ.get("BOOKTRACKER_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if IS_WINDOWS:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / _MAC_WIN_NAME_WIN
    if IS_MACOS:
        return Path.home() / "Library" / "Application Support" / _MAC_WIN_NAME_MAC
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / _SLUG


def log_dir() -> Path:
    if IS_MACOS:
        return Path.home() / "Library" / "Logs" / _MAC_WIN_NAME_MAC
    return data_dir() / "logs"


def config_file() -> Path:
    return config_dir() / "config.ini"


# ---------------------------------------------------------------------------
# Database location
# ---------------------------------------------------------------------------

LEGACY_APP_DIR_DB = APP_DIR / "booktracker.db"
LEGACY_LNRELEASE_DB = APP_DIR / "lnrelease.db"


def default_db_path() -> Path:
    """Where the SQLite DB lives when --db isn't given.

    Existing installs keep working untouched: if a DB already sits next to
    app.py (the pre-2026.11 layout), it's used in place. New installs put
    it in the per-user data directory instead, which is the only option
    that works when the app itself is installed somewhere read-only
    (e.g. C:\\Program Files, /opt, /Applications).
    """
    env = os.environ.get("BOOKTRACKER_DB") or get("database", "path")
    if env:
        return Path(env).expanduser()
    if LEGACY_APP_DIR_DB.exists() or LEGACY_LNRELEASE_DB.exists():
        return LEGACY_APP_DIR_DB
    return data_dir() / "booktracker.db"


# ---------------------------------------------------------------------------
# config.ini
# ---------------------------------------------------------------------------

_CONFIG_TEMPLATE = """\
# Book Tracker settings. Environment variables of the same meaning
# override anything set here. Keep this file private: it can hold API
# tokens. (It's created readable only by your user account.)

[api]
# Hardcover personal API token -- https://hardcover.app/account/api
# Paste it with or without the leading "Bearer ".
hardcover_token =
# Optional Google Books API key (only needed if you hit its rate limit).
google_books_key =

[server]
# 127.0.0.1 = only this computer can open the app (recommended).
# 0.0.0.0   = any device on your network can open it -- note the app has
#             no login, so anyone on that network can edit your data.
host = 127.0.0.1
port = 7077
# Extra host names (comma-separated) allowed in the browser address bar
# when serving on the network, e.g. mybox.lan. IP addresses always work.
allowed_hosts =

[sync]
# Re-sync the LNRelease feed automatically while the server runs.
auto_sync = true
# Hours between automatic syncs.
interval_hours = 24

[database]
# Leave empty for the default location (see `python app.py paths`).
path =
"""

_ENV_ALIASES = {
    ("api", "hardcover_token"): "HARDCOVER_API_TOKEN",
    ("api", "google_books_key"): "GOOGLE_BOOKS_API_KEY",
    ("server", "host"): "BOOKTRACKER_HOST",
    ("server", "port"): "BOOKTRACKER_PORT",
    ("server", "allowed_hosts"): "BOOKTRACKER_ALLOWED_HOSTS",
    ("sync", "auto_sync"): "BOOKTRACKER_AUTO_SYNC",
    ("sync", "interval_hours"): "BOOKTRACKER_SYNC_HOURS",
}

_parser: Optional[configparser.ConfigParser] = None


def _load() -> configparser.ConfigParser:
    global _parser
    if _parser is None:
        _parser = configparser.ConfigParser(interpolation=None)
        try:
            _parser.read(config_file(), encoding="utf-8")
        except (configparser.Error, OSError) as e:
            print(f"warning: could not read {config_file()}: {e}", file=sys.stderr)
    return _parser


def reload() -> None:
    global _parser
    _parser = None


def get(section: str, key: str, default: str = "") -> str:
    env_name = _ENV_ALIASES.get((section, key))
    if env_name:
        val = os.environ.get(env_name, "").strip()
        if val:
            return val
    val = _load().get(section, key, fallback="").strip()
    return val or default


def get_bool(section: str, key: str, default: bool) -> bool:
    raw = get(section, key, "")
    if not raw:
        return default
    return raw.lower() in ("1", "true", "yes", "on")


def get_int(section: str, key: str, default: int) -> int:
    try:
        return int(get(section, key, "") or default)
    except ValueError:
        return default


def secret(section: str, key: str) -> str:
    val = get(section, key)
    # People often paste the whole "Bearer eyJ..." string from Hardcover.
    if val.lower().startswith("bearer "):
        val = val[7:].strip()
    return val


def _write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if IS_WINDOWS:
        # %APPDATA% is already per-user (ACL'd to the account).
        path.write_text(text, encoding="utf-8")
        return
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.chmod(str(path), 0o600)


def init_config(hardcover_token: str = "", google_key: str = "",
                host: str = "") -> Path:
    """Create config.ini if missing. Never overwrites an existing file,
    except to fill in values that are currently blank."""
    path = config_file()
    if path.exists():
        text = path.read_text(encoding="utf-8")
    else:
        text = _CONFIG_TEMPLATE
    fills = {"hardcover_token": hardcover_token, "google_books_key": google_key, "host": host}
    lines = text.splitlines()
    for i, line in enumerate(lines):
        k, sep, v = line.partition("=")
        name = k.strip()
        if sep and name in fills and fills[name] and not v.strip():
            lines[i] = f"{name} = {fills[name]}"
    _write_private(path, "\n".join(lines) + "\n")
    reload()
    return path
