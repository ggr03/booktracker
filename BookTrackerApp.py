"""
Book Tracker -- local web app for tracking light novel releases
(synced from LNRelease) plus any other book, ebook, or audiobook you
add yourself from Google Books, Open Library, Audible/Audnexus, or an
Amazon product URL.

    python BookTrackerApp.py sync              # fetch books.csv, upsert into SQLite (diff-only)
    python BookTrackerApp.py serve             # start the web server (default: http://127.0.0.1:7077)
    python BookTrackerApp.py serve --lan       # ...reachable from other devices on your network
    python BookTrackerApp.py paths             # show where the DB, config and logs live on this OS
    python BookTrackerApp.py init-config       # create a private config.ini for API tokens/settings
    python BookTrackerApp.py install-service   # start automatically at login (systemd/launchd/Windows)
    python BookTrackerApp.py uninstall-service
    python BookTrackerApp.py --version         # print the version string and exit

Runs the same on Linux (Debian/Ubuntu/MX, RHEL/Rocky/Alma/Fedora),
macOS, and Windows; see BookTrackerCfg.py for per-OS file locations and
BookTrackerService.py for the per-OS autostart integration.

Star clicks POST straight to this server, which writes to SQLite -- that's
why this needs to be a running server rather than a static HTML file.
"""
from __future__ import annotations

import sys

if sys.version_info < (3, 11):
    sys.exit(f"Book Tracker needs Python 3.11 or newer (this is {sys.version.split()[0]}). "
             "See README.md > Setup for how to install it on your OS.")

import argparse
import atexit
import datetime
import ipaddress
import os
import platform
import signal
import socket
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from flask import Flask, jsonify, redirect, request, abort

import BookTrackerCfg as config
import BookTrackerDB as db
import BookTrackerLogs as logs
import BookTrackerSearch as external_search
import BookTrackerTemplate as template
from BookTrackerVer import APP_NAME, VERSION

app = Flask(__name__)
# Global request-body cap. Nothing in this app legitimately needs more
# than a few MB per request (the largest is a CSV import); capping it
# here means an oversized upload is rejected before it can consume
# memory or disk, and Werkzeug short-circuits with a 413 automatically.
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25 MB

# Per-file cap for the CSV importer specifically. Deliberately smaller
# than the global cap so the import handler itself gets a clean error
# message rather than the generic Werkzeug 413, and so short reads
# (`f.read(MAX+1)`) don't ever pull the whole oversized body into memory.
MAX_CSV_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB

DB_PATH = db.DEFAULT_DB_PATH
DEFAULT_PORT = 7077


# ---------------------------------------------------------------------
# Activity-log helpers (see BookTrackerLogs.py for the files).
# ---------------------------------------------------------------------

def _q(value, limit: int = 200) -> str:
    """A value made safe for a one-line log entry: quoted, newlines
    escaped (so user-supplied text can't forge extra log lines), capped."""
    text = "" if value is None else str(value)
    text = text.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n")
    if len(text) > limit:
        text = text[:limit] + "..."
    return f'"{text}"'


def _series_label(slug: str) -> str:
    try:
        conn = db.get_conn(DB_PATH)
        try:
            row = conn.execute(
                "SELECT COALESCE(series_title, title) AS t FROM releases WHERE slug = ? "
                "ORDER BY date LIMIT 1", (slug,)).fetchone()
        finally:
            conn.close()
        return f"{_q(row['t'])} [{slug}]" if row else f"[{slug}]"
    except Exception:
        return f"[{slug}]"


def _release_label(release_id: int) -> str:
    try:
        row = db.get_release(int(release_id), db_path=DB_PATH)
    except Exception:
        row = None
    if not row:
        return f"release #{release_id}"
    vol = f" vol {row['volume']}" if row.get("volume") else ""
    return f"{_q(row.get('title'))}{vol} (release #{release_id})"


def _imported_label(book_id: int) -> str:
    try:
        conn = db.get_conn(DB_PATH)
        try:
            row = conn.execute("SELECT title, author FROM imported_books WHERE id = ?",
                               (book_id,)).fetchone()
        finally:
            conn.close()
        if row:
            return f"{_q(row['title'])} by {_q(row['author'])} (#{book_id})"
    except Exception:
        pass
    return f"book #{book_id}"


# ---------------------------------------------------------------------
# Request guard: Host allowlist (DNS-rebinding defence) + same-origin
# check on every state-changing request (CSRF defence). The app has no
# login, so without this any web page you visit could POST to
# http://localhost:7077 and delete or edit your books.
# ---------------------------------------------------------------------

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _split_host(host_header: str) -> str:
    host = (host_header or "").strip().lower()
    if host.startswith("["):                    # [::1]:7077
        return host[1:].split("]", 1)[0]
    if host.count(":") == 1:                    # name:port / v4:port
        return host.rsplit(":", 1)[0]
    return host


def _allowed_hostnames() -> set:
    names = {"localhost"}
    try:
        hn = socket.gethostname().lower()
        names |= {hn, hn.split(".")[0], hn.split(".")[0] + ".local"}
        names.add(socket.getfqdn().lower())
    except OSError:
        pass
    extra = config.get("server", "allowed_hosts")
    names |= {h.strip().lower() for h in extra.split(",") if h.strip()}
    return names


_ALLOWED_HOSTNAMES = _allowed_hostnames()


def host_is_allowed(host_header: str) -> bool:
    host = _split_host(host_header)
    if not host:
        return False
    try:
        ipaddress.ip_address(host)
        return True                             # IP literals can't be DNS-rebound
    except ValueError:
        pass
    return host in _ALLOWED_HOSTNAMES or host.endswith(".localhost")


@app.before_request
def _request_guard():
    if not host_is_allowed(request.host):
        abort(403, "Unrecognised host name. Open the app by IP address, or add this "
                   "name to allowed_hosts in config.ini.")
    if request.method in _SAFE_METHODS:
        return None
    fetch_site = request.headers.get("Sec-Fetch-Site")
    if fetch_site and fetch_site not in ("same-origin", "none"):
        abort(403, "Cross-site request blocked")
    origin = request.headers.get("Origin")
    if origin is not None:
        if origin == "null" or urlparse(origin).netloc.lower() != request.host.lower():
            abort(403, "Cross-origin request blocked")
    return None


def _external_error_response(e: "external_search.ExternalSearchError", status: int = 502):
    """Turn a caught ExternalSearchError into a JSON error response.

    ExternalSearchError's message is deliberately curated, user-facing
    text (rate-limit hints, "isn't configured" notices, etc.) -- see
    BookTrackerSearch.py, where every raise site builds that text itself
    rather than embedding a raw exception or a URL that might carry a
    credential in its query string. So returning it to the browser here
    is intentional and safe, not a stack-trace leak. Logging it
    server-side too just keeps a record for anyone tailing the process.
    """
    app.logger.warning("external_search error: %s", e)
    logs.warning("External lookup failed (%s %s): %s", request.method, request.path, e)
    return jsonify({"error": str(e)}), status


@app.route("/")
def index():
    years = db.get_years(db_path=DB_PATH)
    if not years:
        return "No data yet. Run: python BookTrackerApp.py sync", 500
    today_year = datetime.date.today().year
    if today_year in years:
        target = today_year
    else:
        # Not synced for the current year (unlikely) -- fall back to the
        # closest past year, or otherwise the earliest year available.
        past_years = [y for y in years if y <= today_year]
        target = max(past_years) if past_years else years[0]
    return redirect(f"/year/{target}")


@app.route("/year/<int:year>")
def year_page(year: int):
    years = db.get_years(db_path=DB_PATH)
    if year not in years:
        abort(404, f"No data for year {year}. Available years: {years}")
    releases = db.get_year_releases(year, db_path=DB_PATH)
    today = datetime.date.today()
    initial_month = today.month if today.year == year else (
        int(releases[0]["date"][5:7]) if releases else 1
    )
    return template.render_year_page(year, releases, years, initial_month)


@app.route("/starred")
def starred_page():
    releases = db.get_starred_releases(db_path=DB_PATH)
    return template.render_starred_page(releases)


@app.route("/add")
def add_page():
    recent = db.get_recent_manual_releases(db_path=DB_PATH)
    return template.render_add_page(recent)


# ---------------------------------------------------------------------
# "My Books" -- imported from a Goodreads-format CSV. Kept deliberately
# separate from `releases`/`stars`; the same book may legitimately exist
# in both places. See BookTrackerDB.py's imported_books section for the storage
# details.
# ---------------------------------------------------------------------

@app.route("/my_books")
def my_books_page():
    books = db.get_imported_books(db_path=DB_PATH)
    return template.render_my_books_page(books)


@app.route("/api/imported_books")
def api_imported_books():
    """Full current list -- used by the page after an import so the UI
    reflects whatever was actually committed without a full reload."""
    return jsonify(db.get_imported_books(db_path=DB_PATH))


@app.route("/api/import_books_csv", methods=["POST"])
def api_import_books_csv():
    if "file" not in request.files:
        abort(400, "No file uploaded (form field must be named 'file')")
    f = request.files["file"]
    if not f or not f.filename:
        abort(400, "No file selected")

    # Cap the read so an oversized upload never gets buffered in memory
    # in full. If we got MAX+1 bytes back, the file is too big.
    raw = f.read(MAX_CSV_UPLOAD_BYTES + 1)
    if len(raw) > MAX_CSV_UPLOAD_BYTES:
        logs.my_books("IMPORT REJECTED %s: file larger than %d MB", _q(f.filename),
                      MAX_CSV_UPLOAD_BYTES // (1024 * 1024))
        abort(413, f"CSV file too large (max {MAX_CSV_UPLOAD_BYTES // (1024 * 1024)} MB)")

    try:
        text = raw.decode("utf-8-sig")  # utf-8-sig strips a leading BOM (Goodreads exports have one)
    except UnicodeDecodeError:
        try:
            text = raw.decode("latin-1")
        except UnicodeDecodeError:
            abort(400, "Could not read CSV — expected UTF-8 or Latin-1 text")

    try:
        rows, warnings, skipped_rows = db.parse_goodreads_csv(text)
    except ValueError:
        # parse_goodreads_csv only raises ValueError for structural
        # problems (empty file, missing Title column); the message it
        # would have raised is discarded here in favour of a fixed,
        # user-friendly one, so no user-controlled text can end up in
        # the response.
        logs.my_books("IMPORT REJECTED %s: empty or missing a Title column", _q(f.filename))
        abort(400, "CSV is empty or missing a Title column")

    result = db.add_imported_books(rows, db_path=DB_PATH)
    result["warnings"] = warnings
    result["skipped_rows"] = skipped_rows
    logs.my_books("IMPORT %s: %d rows read, %d added, %d already in My Books, "
                  "%d unreadable rows skipped, %d warnings",
                  _q(f.filename), len(rows), result.get("added", 0), result.get("skipped", 0),
                  len(skipped_rows) if isinstance(skipped_rows, (list, tuple)) else (skipped_rows or 0),
                  len(warnings) if isinstance(warnings, (list, tuple)) else 0)
    return jsonify(result)


@app.route("/api/imported_book/<int:book_id>/update", methods=["POST"])
def api_update_imported_book(book_id: int):
    body = request.get_json(silent=True) or {}
    label = _imported_label(book_id)
    try:
        row = db.update_imported_book(book_id, body, db_path=DB_PATH)
    except KeyError:
        # db.update_imported_book raises KeyError specifically for
        # "no such row" -- a clean 404, message is a fixed string.
        abort(404, "No book with that id")
    except ValueError:
        # Validation/duplicate errors -- fixed message, no leaked
        # exception text.
        abort(400, "Invalid update — check the date format (YYYY-MM-DD) and try again")
    changes = ", ".join(f"{k}={_q(v, 60)}" for k, v in sorted(body.items()) if isinstance(k, str))
    logs.my_books("EDITED %s: %s", label, changes or "(no fields)")
    return jsonify(row)


@app.route("/api/imported_book/<int:book_id>/remove", methods=["POST"])
def api_remove_imported_book(book_id: int):
    label = _imported_label(book_id)
    try:
        db.remove_imported_book(book_id, db_path=DB_PATH)
    except ValueError:
        abort(404, "No book with that id")
    logs.my_books("REMOVED %s", label)
    return jsonify({"removed": book_id})


# ---------------------------------------------------------------------
# Existing routes below -- unchanged in behavior from the previous version.
# ---------------------------------------------------------------------

@app.route("/api/years")
def api_years():
    return jsonify(db.get_years(db_path=DB_PATH))


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    return jsonify(db.search_releases(q, db_path=DB_PATH))


@app.route("/api/star", methods=["POST"])
def api_star():
    body = request.get_json(silent=True) or {}
    slug = body.get("slug")
    if not slug:
        abort(400, "slug is required")
    starred = db.toggle_star(slug, db_path=DB_PATH)
    logs.starred_update("%s %s", "STARRED" if starred else "UNSTARRED", _series_label(slug))
    return jsonify({"slug": slug, "starred": starred})


@app.route("/api/volume_status", methods=["POST"])
def api_volume_status():
    body = request.get_json(silent=True) or {}
    release_id = body.get("release_id")
    status = body.get("status")
    if not release_id or status not in db.STATUSES:
        abort(400, f"release_id and a valid status ({db.STATUSES}) are required")
    try:
        changed = db.set_volume_status(int(release_id), status, db_path=DB_PATH)
    except ValueError as e:
        abort(400, str(e))
    logs.starred_update("STATUS %s -> %s", _release_label(release_id), status)
    return jsonify({"changed": changed})


@app.route("/api/series_status", methods=["POST"])
def api_series_status():
    body = request.get_json(silent=True) or {}
    slug = body.get("slug")
    status = body.get("status")
    if not slug or status not in db.STATUSES:
        abort(400, f"slug and a valid status ({db.STATUSES}) are required")
    changed = db.set_series_status(slug, status, db_path=DB_PATH)
    logs.starred_update("SERIES STATUS %s -> %s (%d volumes)", _series_label(slug), status,
                        len(changed) if isinstance(changed, list) else 0)
    return jsonify({"changed": changed})


@app.route("/api/series_format_pref", methods=["POST"])
def api_series_format_pref():
    body = request.get_json(silent=True) or {}
    slug = body.get("slug")
    formats = body.get("formats")
    if not slug or not isinstance(formats, list):
        abort(400, "slug and a formats list are required")
    try:
        result = db.set_series_format_pref(slug, formats, db_path=DB_PATH)
    except ValueError as e:
        abort(400, str(e))
    logs.starred_update("FORMATS %s -> %s", _series_label(slug), ", ".join(result) or "(none)")
    return jsonify({"slug": slug, "formats": result})


@app.route("/api/by_status/<status>")
def api_by_status(status):
    if status not in db.STATUSES:
        abort(404, f"unknown status {status!r}")
    return jsonify(db.get_releases_by_status(status, db_path=DB_PATH))


@app.route("/api/external_provider_status")
def api_external_provider_status():
    return jsonify({
        "hardcover_configured": bool(external_search.HARDCOVER_API_TOKEN),
        "google_books_key_set": bool(external_search.GOOGLE_BOOKS_API_KEY),
    })


@app.route("/api/external_search")
def api_external_search():
    kind = request.args.get("kind", "book")
    provider = request.args.get("provider", "")
    q = request.args.get("q", "").strip()
    author = request.args.get("author", "").strip()
    if provider == "amazon":
        return jsonify({"error": "Amazon has no public search API -- paste a product URL instead."}), 400
    if provider == "audnexus":
        if not external_search.looks_like_asin(q):
            return jsonify({"error": "Audnexus only supports lookup by ASIN -- type or paste one."}), 400
        try:
            return jsonify([external_search.get_audnexus_book(q)])
        except external_search.ExternalSearchError as e:
            return _external_error_response(e)
    if len(q) < 2:
        return jsonify([])
    try:
        if provider == "audible" or kind == "audiobook":
            results = external_search.search_audiobooks(f"{q} {author}".strip())
        elif provider == "openlibrary":
            results = external_search.search_open_library(q, author)
        elif provider == "hardcover":
            results = external_search.search_hardcover(q, author)
        else:
            results = external_search.search_google_books(q, author)
    except external_search.ExternalSearchError as e:
        return _external_error_response(e)
    return jsonify(results)


@app.route("/api/external_detail")
def api_external_detail():
    kind = request.args.get("kind", "book")
    source = request.args.get("source", "")
    external_id = request.args.get("external_id", "")
    if not external_id:
        abort(400, "external_id is required")
    try:
        if kind == "audiobook":
            detail = external_search.get_audiobook_detail(source, external_id)
        else:
            detail = external_search.get_book_detail(source, external_id)
    except external_search.ExternalSearchError as e:
        return _external_error_response(e)
    return jsonify(detail)


@app.route("/api/external_fetch_url", methods=["POST"])
def api_external_fetch_url():
    body = request.get_json(silent=True) or {}
    url = (body.get("url") or "").strip()
    if not url:
        abort(400, "url is required")
    try:
        detail = external_search.fetch_by_url(url)
    except external_search.ExternalSearchError as e:
        return _external_error_response(e)
    return jsonify(detail)


@app.route("/api/external_add", methods=["POST"])
def api_external_add():
    body = request.get_json(silent=True) or {}
    kind = body.get("kind")
    formats = body.get("formats") or []
    volume = body.get("volume") or {}
    if kind not in ("book", "audiobook") or not volume.get("title"):
        abort(400, "kind ('book' or 'audiobook') and a volume with a title are required")

    author = volume.get("author") or ""
    series_title = (volume.get("series_title") or "").strip()
    if series_title:
        slug = db.make_manual_series_slug(kind, series_title, author)
    else:
        slug = db.make_manual_standalone_slug(kind, volume.get("title", ""), author, volume.get("external_id", ""))

    entry = {
        "slug": slug,
        "title": volume.get("title") or "Untitled",
        "subtitle": volume.get("subtitle"),
        "volume": volume.get("volume"),
        "date": volume.get("date"),
        "publisher": volume.get("publisher"),
        "url": volume.get("url"),
        "author": author or None,
        "narrator": volume.get("narrator"),
        "series_title": series_title or None,
        "runtime_minutes": volume.get("runtime_minutes"),
        "isbn": volume.get("isbn"),
        "cover_url": volume.get("cover_url"),
        "genres": volume.get("genres"),
        "description": volume.get("description"),
        "language": volume.get("language"),
        "external_id": volume.get("external_id"),
        "source_label": volume.get("source_label"),
        "ebook": 1 if "ebook" in formats else 0,
        "print": 1 if "print" in formats else 0,
        "audiobook": 1 if "audiobook" in formats else 0,
        "status": volume.get("status") if volume.get("status") in db.STATUSES else db.DEFAULT_STATUS,
    }
    result = db.add_manual_entries([entry], db_path=DB_PATH)
    fmt_list = [k for k in ("ebook", "print", "audiobook") if entry[k]] or ["(none)"]
    series = f" | series {_q(series_title)} vol {entry['volume']}" if series_title else ""
    logs.manual_addition(
        "%s %s by %s | %s, formats: %s | source: %s%s | status: %s",
        "ADDED" if result.get("added") else "ALREADY PRESENT (status updated)",
        _q(entry["title"]), _q(author or "unknown"), kind, ", ".join(fmt_list),
        entry.get("source_label") or "manual entry", series, entry["status"])
    return jsonify(result)


@app.route("/api/release/<int:release_id>")
def api_get_release(release_id: int):
    row = db.get_release(release_id, db_path=DB_PATH)
    if row is None:
        abort(404, f"no release with id {release_id}")
    return jsonify(row)


@app.route("/api/release/<int:release_id>/update", methods=["POST"])
def api_update_release(release_id: int):
    body = request.get_json(silent=True) or {}
    try:
        row = db.update_release_metadata(release_id, body, db_path=DB_PATH)
    except ValueError as e:
        abort(404, str(e))
    fields = ", ".join(sorted(k for k in body if isinstance(k, str))) or "(none)"
    logs.starred_update("EDITED %s: fields %s", _release_label(release_id), fields)
    return jsonify(row)


@app.route("/api/release/<int:release_id>/remove", methods=["POST"])
def api_remove_release(release_id: int):
    label = _release_label(release_id)
    try:
        db.remove_manual_release(release_id, db_path=DB_PATH)
    except ValueError as e:
        abort(404, str(e))
    logs.starred_update("REMOVED manually-added book %s", label)
    return jsonify({"removed": release_id})


def run_sync(db_path: Path, csv_url: str = db.CSV_URL_DEFAULT) -> dict:
    resp = requests.get(csv_url, timeout=30)
    resp.raise_for_status()
    stats = db.sync_from_csv(resp.text, db_path=Path(db_path))
    _stamp_path(db_path).write_text(str(time.time()), encoding="utf-8")
    return stats


def cmd_sync(args):
    print(f"Fetching {args.csv_url} ...")
    try:
        stats = run_sync(Path(args.db), args.csv_url)
    except Exception as e:
        logs.error("Manual sync failed: %s: %s", type(e).__name__, e)
        raise
    print(f"Sync complete: {stats['added']} added, {stats['updated']} updated, "
          f"{stats['unchanged']} unchanged (of {stats['total']} releases in the feed).")


# ---------------------------------------------------------------------
# Built-in periodic sync. Replaces the old systemd timer so the same
# behaviour works on every OS with no extra scheduler to install.
# ---------------------------------------------------------------------

def _stamp_path(db_path: Path) -> Path:
    db_path = Path(db_path)
    return db_path.with_name(db_path.name + ".last-sync")


def _last_sync_time(db_path: Path) -> float:
    try:
        return float(_stamp_path(db_path).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return 0.0


def _auto_sync_loop(db_path: Path, interval_hours: int) -> None:
    interval = max(1, interval_hours) * 3600
    while True:
        due_in = _last_sync_time(db_path) + interval - time.time()
        if due_in <= 0:
            try:
                stats = run_sync(db_path)
                app.logger.info("auto-sync: %s added, %s updated", stats["added"], stats["updated"])
                print(f"[auto-sync] {stats['added']} added, {stats['updated']} updated "
                      f"({datetime.datetime.now():%Y-%m-%d %H:%M})", flush=True)
                due_in = interval
            except Exception as e:  # network down etc. -- retry in an hour
                logs.error("Auto-sync failed: %s: %s (retrying in 1 hour)", type(e).__name__, e)
                print(f"[auto-sync] failed: {type(e).__name__}; retrying in 1 hour", flush=True)
                due_in = 3600
        time.sleep(min(due_in, 3600))


def _local_ip() -> str:
    """Best-effort guess at this machine's LAN IP, for a friendlier startup
    message. (A UDP connect() sends no packets; it just picks a route.)"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _redirect_output(log_file: str) -> None:
    """For background launches (pythonw on Windows, launchd on macOS)
    where there's no console: send prints/tracebacks to a log file."""
    path = Path(log_file).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = fh


def _install_shutdown_logging(started: float) -> dict:
    """Write one appShutdown.log line however the server stops: Ctrl+C,
    systemd/launchd stop (SIGTERM), closing the console on Windows
    (SIGBREAK), a crash, or a normal return. A hard kill (SIGKILL, Task
    Manager "End task") can't be caught by any program, so those leave
    a START with no matching STOP."""
    state = {"reason": "normal exit"}

    def on_signal(signum, _frame):
        try:
            state["reason"] = f"received {signal.Signals(signum).name}"
        except ValueError:
            state["reason"] = f"received signal {signum}"
        raise SystemExit(0)

    for name in ("SIGTERM", "SIGINT", "SIGHUP", "SIGBREAK"):
        sig = getattr(signal, name, None)
        if sig is not None:
            try:
                signal.signal(sig, on_signal)
            except (ValueError, OSError):
                pass

    def on_exit():
        up = int(time.time() - started)
        logs.shutdown("STOP %s %s | reason: %s | uptime %dh %02dm %02ds | pid %d",
                      APP_NAME, VERSION, state["reason"], up // 3600, up % 3600 // 60, up % 60,
                      os.getpid())
        print(f"{APP_NAME} stopped ({state['reason']}).", flush=True)

    atexit.register(on_exit)
    return state


def cmd_serve(args):
    global DB_PATH
    if args.log_file:
        _redirect_output(args.log_file)
    logs.setup(app)
    started = time.time()
    DB_PATH = Path(args.db)
    host = "0.0.0.0" if args.lan else (args.host or config.get("server", "host", "127.0.0.1"))
    port = args.port or config.get_int("server", "port", DEFAULT_PORT)
    auto_sync = (not args.no_auto_sync) and config.get_bool("sync", "auto_sync", True)

    years = db.get_years(db_path=DB_PATH)
    if not years:
        if auto_sync:
            print("No data yet -- running the first sync ...", flush=True)
            try:
                run_sync(DB_PATH)
            except Exception as e:
                logs.error("First sync failed: %s: %s", type(e).__name__, e)
                print(f"First sync failed ({type(e).__name__}); the server will start anyway "
                      "and retry later.", file=sys.stderr, flush=True)
        else:
            print("No data in the DB yet. Run `python BookTrackerApp.py sync` first.", file=sys.stderr)
            sys.exit(1)
        years = db.get_years(db_path=DB_PATH)

    if auto_sync:
        threading.Thread(target=_auto_sync_loop, name="auto-sync", daemon=True,
                         args=(DB_PATH, config.get_int("sync", "interval_hours", 24))).start()

    print(f"{APP_NAME} {VERSION}")
    print(f"Database: {DB_PATH}")
    print(f"Years available: {years}")
    print(f"Local:   http://127.0.0.1:{port}")
    if host in ("0.0.0.0", "::"):
        print(f"Network: http://{_local_ip()}:{port}  (reachable from other devices on your LAN"
              " -- there is no login, so only do this on a network you trust)")
    elif host not in ("127.0.0.1", "localhost", "::1"):
        print(f"Serving on http://{host}:{port}")
    sys.stdout.flush()

    logs.startup(
        "START %s %s | Python %s | %s %s | pid %d | db %s | listening on %s:%d | "
        "auto-sync %s | logs %s",
        APP_NAME, VERSION, platform.python_version(), platform.system(), platform.release(),
        os.getpid(), DB_PATH, host, port, "on" if auto_sync else "off", logs.log_dir())
    shutdown_state = _install_shutdown_logging(started)

    if args.debug:
        # Auto-reload + verbose logs only. Werkzeug's interactive debugger
        # is never enabled: it allows running arbitrary code from the
        # browser, which with --lan means anyone on the network.
        import logging
        logging.basicConfig(level=logging.DEBUG)
        app.run(host=host, port=port, use_reloader=True, use_debugger=False)
        return
    try:
        from waitress import serve as waitress_serve
    except ImportError:
        print("(waitress not installed -- using Flask's development server; "
              "run `pip install -r requirements.txt`)", file=sys.stderr)
        app.run(host=host, port=port)
        return
    try:
        waitress_serve(app, host=host, port=port, threads=8, ident=APP_NAME)
    except SystemExit:
        raise
    except BaseException as e:
        shutdown_state["reason"] = f"crashed: {type(e).__name__}"
        logs.error("Server stopped unexpectedly", exc_info=True)
        raise


def cmd_paths(args):
    print(f"App folder:   {config.APP_DIR}")
    print(f"Database:     {Path(args.db)}")
    cf = config.config_file()
    print(f"Config file:  {cf}{'' if cf.exists() else '  (not created yet: python BookTrackerApp.py init-config)'}")
    print(f"Data folder:  {config.data_dir()}")
    print(f"Log folder:   {logs.log_dir()}")


def cmd_init_config(args):
    existed = config.config_file().exists()
    path = config.init_config()
    print(f"{'Config already exists' if existed else 'Created'}: {path}")
    print("Edit it to add your Hardcover token (hardcover_token = ...).")


def cmd_install_service(args):
    import BookTrackerService as service
    service.install(lan=args.lan, port=args.port)


def cmd_uninstall_service(args):
    import BookTrackerService as service
    service.uninstall()


def main():
    p = argparse.ArgumentParser(description=f"{APP_NAME} local app")
    p.add_argument("--version", action="version", version=f"{APP_NAME} {VERSION}")
    p.add_argument("--db", default=str(db.DEFAULT_DB_PATH), help="SQLite DB path")
    sub = p.add_subparsers(dest="command", required=True)

    sync_p = sub.add_parser("sync", help="Fetch books.csv and upsert into the DB")
    sync_p.add_argument("--csv-url", default=db.CSV_URL_DEFAULT)
    sync_p.set_defaults(func=cmd_sync)

    serve_p = sub.add_parser("serve", help="Start the web server")
    serve_p.add_argument("--host", default=None,
                         help="Address to listen on (default: config.ini, else 127.0.0.1)")
    serve_p.add_argument("--lan", action="store_true",
                         help="Listen on all interfaces (same as --host 0.0.0.0)")
    serve_p.add_argument("--port", type=int, default=None, help=f"Port (default {DEFAULT_PORT})")
    serve_p.add_argument("--no-auto-sync", action="store_true",
                         help="Don't re-sync the LNRelease feed in the background")
    serve_p.add_argument("--log-file", default=None, help="Append output to this file")
    serve_p.add_argument("--debug", action="store_true",
                         help="Auto-reload on code changes, verbose logging (no interactive debugger)")
    serve_p.set_defaults(func=cmd_serve)

    sub.add_parser("paths", help="Show file locations").set_defaults(func=cmd_paths)
    sub.add_parser("init-config", help="Create config.ini").set_defaults(func=cmd_init_config)

    inst_p = sub.add_parser("install-service", help="Start automatically at login")
    inst_p.add_argument("--lan", action="store_true", help="Serve on your network, not just this PC")
    inst_p.add_argument("--port", type=int, default=None)
    inst_p.set_defaults(func=cmd_install_service)
    sub.add_parser("uninstall-service", help="Remove the autostart entry").set_defaults(
        func=cmd_uninstall_service)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
