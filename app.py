"""
Book Tracker -- local web app for tracking light novel releases
(synced from LNRelease) plus any other book, ebook, or audiobook you
add yourself from Google Books, Open Library, Audible/Audnexus, or an
Amazon product URL.

    python app.py sync          # fetch books.csv, upsert into SQLite (diff-only)
    python app.py serve         # start the local web server (default: http://127.0.0.1:7077)
    python app.py --version     # print the version string and exit

Star clicks POST straight to this server, which writes to SQLite -- that's
why this needs to be a running server rather than a static HTML file.
"""
from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

import requests
from flask import Flask, jsonify, redirect, request, abort

import db
import external_search
import template
from version import APP_NAME, VERSION

app = Flask(__name__)
DB_PATH = db.DEFAULT_DB_PATH
DEFAULT_PORT = 7077


@app.route("/")
def index():
    years = db.get_years(db_path=DB_PATH)
    if not years:
        return "No data yet. Run: python app.py sync", 500
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
    return jsonify({"changed": changed})


@app.route("/api/series_status", methods=["POST"])
def api_series_status():
    body = request.get_json(silent=True) or {}
    slug = body.get("slug")
    status = body.get("status")
    if not slug or status not in db.STATUSES:
        abort(400, f"slug and a valid status ({db.STATUSES}) are required")
    changed = db.set_series_status(slug, status, db_path=DB_PATH)
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
    return jsonify({"slug": slug, "formats": result})


@app.route("/api/by_status/<status>")
def api_by_status(status):
    if status not in db.STATUSES:
        abort(404, f"unknown status {status!r}")
    return jsonify(db.get_releases_by_status(status, db_path=DB_PATH))


# ---------------------------------------------------------------------
# "Add a book" (its own page, /add) -- search Google Books / Open
# Library / Audible, or paste a product URL (Amazon / Audible / Google
# Books / Open Library / a bare ASIN), review & edit the fetched
# metadata, then add it straight to ★ My Starred. See external_search.py
# for source details and limitations.
# ---------------------------------------------------------------------

@app.route("/api/external_provider_status")
def api_external_provider_status():
    """Whether each provider that needs a credential is actually
    configured -- lets the Add page show a hint instead of a confusing
    error on first use."""
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
            return jsonify({"error": str(e)}), 502
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
            # Structured title/author search (not a single blended string) --
            # a blended query can rank an unrelated same-titled book by a
            # different author above the one actually meant.
            results = external_search.search_google_books(q, author)
    except external_search.ExternalSearchError as e:
        return jsonify({"error": str(e)}), 502
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
        return jsonify({"error": str(e)}), 502
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
        return jsonify({"error": str(e)}), 502
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
    return jsonify(row)


@app.route("/api/release/<int:release_id>/remove", methods=["POST"])
def api_remove_release(release_id: int):
    try:
        db.remove_manual_release(release_id, db_path=DB_PATH)
    except ValueError as e:
        abort(404, str(e))
    return jsonify({"removed": release_id})


def cmd_sync(args):
    print(f"Fetching {args.csv_url} ...")
    resp = requests.get(args.csv_url, timeout=30)
    resp.raise_for_status()
    stats = db.sync_from_csv(resp.text, db_path=Path(args.db))
    print(f"Sync complete: {stats['added']} added, {stats['updated']} updated, "
          f"{stats['unchanged']} unchanged (of {stats['total']} releases in the feed).")


def _local_ip() -> str:
    """Best-effort guess at this machine's LAN IP, for a friendlier startup message."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def cmd_serve(args):
    global DB_PATH
    DB_PATH = Path(args.db)
    years = db.get_years(db_path=DB_PATH)
    if not years:
        print("No data in the DB yet. Run `python app.py sync` first.", file=sys.stderr)
        sys.exit(1)
    print(f"{APP_NAME} {VERSION}")
    print(f"Years available: {years}")
    print(f"Local:   http://127.0.0.1:{args.port}")
    if args.host == "0.0.0.0":
        print(f"Network: http://{_local_ip()}:{args.port}  (reachable from other devices on your LAN)")
    else:
        print(f"Serving on http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)


def main():
    p = argparse.ArgumentParser(description=f"{APP_NAME} local app")
    p.add_argument("--version", action="version", version=f"{APP_NAME} {VERSION}")
    p.add_argument("--db", default=str(db.DEFAULT_DB_PATH), help="SQLite DB path")
    sub = p.add_subparsers(dest="command", required=True)

    sync_p = sub.add_parser("sync", help="Fetch books.csv and upsert into the DB")
    sync_p.add_argument("--csv-url", default=db.CSV_URL_DEFAULT)
    sync_p.set_defaults(func=cmd_sync)

    serve_p = sub.add_parser("serve", help="Start the local web server")
    serve_p.add_argument("--host", default="0.0.0.0")
    serve_p.add_argument("--port", type=int, default=DEFAULT_PORT)
    serve_p.add_argument("--debug", action="store_true")
    serve_p.set_defaults(func=cmd_serve)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
