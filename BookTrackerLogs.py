"""
Book Tracker's activity logs -- one file per kind of event, all in the
Logs folder (see BookTrackerCfg.log_dir(): "Logs" next to
BookTrackerApp.py by default).

    appStartup.log           every server start: version, Python, OS, DB, address
    appShutdown.log          every server stop: reason and uptime
    manualBookAdditions.log  books added by hand on the Add Book page
    starredBookUpdates.log   star/unstar, reading-status and format changes,
                             edits and removals of starred/manual books
    myBooksImports.log       Goodreads CSV imports into My Books, plus edits
                             and removals of My Books rows
    appErrors.log            unhandled errors (with tracebacks), failed
                             external lookups, failed syncs
    serverOutput.log         raw console output, only for background runs
                             without a console (Windows pythonw, macOS
                             launchd, Linux autostart); systemd keeps that in
                             the journal instead

Each file rotates at 1 MB, keeping 5 old copies (appErrors.log.1 ...).
Only the standard library is used, so this behaves the same on Linux,
macOS and Windows. The Logs folder holds your book titles, so it's
excluded from git.
"""
from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Dict, Optional

import BookTrackerCfg as config

STARTUP = "appStartup"
SHUTDOWN = "appShutdown"
MANUAL_ADDITIONS = "manualBookAdditions"
STARRED_UPDATES = "starredBookUpdates"
MY_BOOKS_IMPORTS = "myBooksImports"
ERRORS = "appErrors"
SERVER_OUTPUT = "serverOutput"

ALL_LOGS = (STARTUP, SHUTDOWN, MANUAL_ADDITIONS, STARRED_UPDATES, MY_BOOKS_IMPORTS, ERRORS)

_MAX_BYTES = 1_000_000
_BACKUPS = 5
_FORMAT = logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s", "%Y-%m-%d %H:%M:%S")

_loggers: Dict[str, logging.Logger] = {}
_log_dir: Optional[Path] = None


def log_dir() -> Path:
    global _log_dir
    if _log_dir is None:
        _log_dir = config.log_dir()
    return _log_dir


def log_file(name: str) -> Path:
    return log_dir() / f"{name}.log"


def _handler(name: str) -> logging.Handler:
    try:
        log_dir().mkdir(parents=True, exist_ok=True)
        h: logging.Handler = logging.handlers.RotatingFileHandler(
            str(log_file(name)), maxBytes=_MAX_BYTES, backupCount=_BACKUPS,
            encoding="utf-8", delay=True)
    except OSError as e:
        # Never let logging stop the app from running.
        print(f"warning: can't write {name}.log in {log_dir()}: {e}", file=sys.stderr)
        h = logging.NullHandler()
    h.setFormatter(_FORMAT)
    return h


def get(name: str) -> logging.Logger:
    """The logger that writes to Logs/<name>.log (one of the constants above)."""
    if name not in _loggers:
        lg = logging.getLogger(f"booktracker.{name}")
        lg.setLevel(logging.INFO)
        lg.propagate = False          # keep each kind of event in its own file
        lg.addHandler(_handler(name))
        _loggers[name] = lg
    return _loggers[name]


def setup(flask_app=None) -> None:
    """Route errors from Flask, Waitress and anything else that uses the
    logging module into appErrors.log, in addition to the console.
    (Flask logs every unhandled request exception, with its traceback,
    at ERROR level through app.logger, which propagates to the root.)"""
    root = logging.getLogger()
    if not any(getattr(h, "_booktracker", False) for h in root.handlers):
        h = _handler(ERRORS)
        h.setLevel(logging.ERROR)
        h._booktracker = True  # type: ignore[attr-defined]
        root.addHandler(h)
    if flask_app is not None:
        flask_app.logger.setLevel(logging.INFO)


def server_output_path() -> Path:
    return log_file(SERVER_OUTPUT)


# Convenience wrappers ------------------------------------------------------

def startup(msg: str, *args) -> None:
    get(STARTUP).info(msg, *args)


def shutdown(msg: str, *args) -> None:
    get(SHUTDOWN).info(msg, *args)


def manual_addition(msg: str, *args) -> None:
    get(MANUAL_ADDITIONS).info(msg, *args)


def starred_update(msg: str, *args) -> None:
    get(STARRED_UPDATES).info(msg, *args)


def my_books(msg: str, *args) -> None:
    get(MY_BOOKS_IMPORTS).info(msg, *args)


def error(msg: str, *args, exc_info=False) -> None:
    get(ERRORS).error(msg, *args, exc_info=exc_info)


def warning(msg: str, *args) -> None:
    get(ERRORS).warning(msg, *args)
