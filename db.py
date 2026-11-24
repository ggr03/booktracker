"""
SQLite-backed storage for LNRelease data.

Why a DB at all (vs. the previous "regenerate a static HTML file" approach):
- Search needs to span every year that's ever been synced, not just the
  year currently being viewed. A DB makes that a single indexed query
  instead of re-fetching/re-parsing every year's data on every search.
- Star state needs to survive re-syncs (new volumes of a starred series
  should show up already starred). Storing stars keyed by series `slug`
  and joining against releases makes that automatic: star the slug once,
  every past AND future volume with that slug is starred.
- Syncing is now a diff against existing rows, so re-running `sync` when
  nothing changed touches zero rows instead of rewriting a whole file.

Note on performance: for the browser-side table itself (rendering /
filtering / sorting one year's ~1-2k rows), a DB doesn't make anything
faster -- that was already instant as an in-memory JS array and still is.
The DB's value is entirely on the Python/server side: cross-year search,
incremental sync, and star persistence.
"""
from __future__ import annotations

import csv as _csv
import io as _io
import re as _re
import hashlib as _hashlib
import sqlite3
import datetime
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Any, Optional

import config as _config

# Resolved per-OS (see config.default_db_path): an existing DB next to
# app.py is kept in place; new installs use the per-user data directory.
DEFAULT_DB_PATH = _config.default_db_path()
_LEGACY_DB_PATH = _config.LEGACY_LNRELEASE_DB  # pre-rename filename

CSV_URL_DEFAULT = "https://raw.githubusercontent.com/LNRelease/lnrelease.github.io/main/books.csv"

# books.csv `format` field -> one of our three independent flags.
_CSV_FORMAT_MAP = {
    "digital": "ebook",
    "paperback": "print",
    "physical": "print",
    "hardback": "print",
    "hardcover": "print",
    "audiobook": "audiobook",
    "audio": "audiobook",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS releases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT NOT NULL,
    title       TEXT NOT NULL,
    volume      TEXT,
    date        TEXT NOT NULL,
    year        INTEGER NOT NULL,
    publisher   TEXT,
    url         TEXT,
    ebook       INTEGER NOT NULL DEFAULT 0,
    print       INTEGER NOT NULL DEFAULT 0,
    audiobook   INTEGER NOT NULL DEFAULT 0,
    source      TEXT NOT NULL DEFAULT 'lnrelease',
    author      TEXT,
    subtitle    TEXT,
    narrator    TEXT,
    series_title TEXT,
    runtime_minutes INTEGER,
    isbn        TEXT,
    cover_url   TEXT,
    genres      TEXT,
    description TEXT,
    language    TEXT,
    external_id TEXT,
    source_label TEXT,
    updated_at  TEXT NOT NULL,
    UNIQUE(title, volume, date)
);
CREATE INDEX IF NOT EXISTS idx_releases_year ON releases(year);
CREATE INDEX IF NOT EXISTS idx_releases_slug ON releases(slug);
CREATE INDEX IF NOT EXISTS idx_releases_title ON releases(title);

CREATE TABLE IF NOT EXISTS stars (
    slug        TEXT PRIMARY KEY,
    starred_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS volume_status (
    release_id  INTEGER PRIMARY KEY,
    status      TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    FOREIGN KEY(release_id) REFERENCES releases(id)
);

CREATE TABLE IF NOT EXISTS series_format_pref (
    slug        TEXT PRIMARY KEY,
    formats     TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- "My Books" -- books imported from an external CSV (Goodreads export).
-- Deliberately a SEPARATE table from `releases`: the user explicitly asked
-- that these not be mixed with LNRelease/starred data, even though the same
-- book may appear in both. Only 5 fields are kept (Title, Author,
-- Publisher, Date Published, Date Read); all other Goodreads columns are
-- ignored. `imported_signature` is a hash of (title, author, date_published)
-- and makes re-imports idempotent -- same book imported twice is skipped.
CREATE TABLE IF NOT EXISTS imported_books (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    imported_signature  TEXT NOT NULL UNIQUE,
    title               TEXT NOT NULL,
    author              TEXT,
    publisher           TEXT,
    date_published      TEXT,
    date_read           TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_imported_books_date_read ON imported_books(date_read);
CREATE INDEX IF NOT EXISTS idx_imported_books_title ON imported_books(title COLLATE NOCASE);
"""

# The four reading-status values. Stored/keyed with underscores
# internally; the UI is responsible for the "To-Read" / "Reading" / etc.
# display labels.
STATUSES = ("to_read", "reading", "read", "dropped")
DEFAULT_STATUS = "to_read"

# Shared SELECT column list for every "give me releases" query, so a new
# metadata field only needs to be added here once instead of in five
# separate hand-written SELECT strings.
RELEASE_COLS = (
    "r.id, r.slug, r.title, r.volume, r.date, r.year, r.publisher, r.url, r.author, "
    "r.subtitle, r.narrator, r.series_title, r.runtime_minutes, r.isbn, r.cover_url, "
    "r.genres, r.description, r.language, r.external_id, r.source_label, r.source, "
    "r.ebook, r.print, r.audiobook"
)

# Statuses that cascade forward to every chronologically-later volume of
# the same series when set on one volume:
#   - dropped: if you dropped a series at volume N, you're not planning to
#     pick up N+1, N+2, ... either, unless you explicitly change them.
#   - to_read: marking an earlier volume "to read" implies later ones you
#     haven't touched yet are also still "to read" (this mostly matters
#     for walking a status back -- e.g. un-reading a "read" run).
# "reading" and "read" do not cascade -- they describe your position, not
# a blanket statement about volumes you haven't gotten to.
_FORWARD_CASCADE_STATUSES = {"dropped", "to_read"}


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns introduced after a user's DB was first created.
    CREATE TABLE IF NOT EXISTS (in SCHEMA) only helps brand-new DBs --
    existing DB files need ALTER TABLE for anything added later, since
    SQLite has no 'ADD COLUMN IF NOT EXISTS'."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(releases)")}
    new_cols = {
        "source": "TEXT NOT NULL DEFAULT 'lnrelease'",
        "author": "TEXT",
        "subtitle": "TEXT",
        "narrator": "TEXT",
        "series_title": "TEXT",
        "runtime_minutes": "INTEGER",
        "isbn": "TEXT",
        "cover_url": "TEXT",
        "genres": "TEXT",
        "description": "TEXT",
        "language": "TEXT",
        "external_id": "TEXT",
        "source_label": "TEXT",
    }
    for col, decl in new_cols.items():
        if col not in cols:
            conn.execute(f"ALTER TABLE releases ADD COLUMN {col} {decl}")
    conn.commit()


def _migrate_legacy_db_file(db_path: Path) -> None:
    """Book Tracker used to be called 'LNRelease', with a DB file named
    lnrelease.db. If the (new-name) DB doesn't exist yet but the old one
    does, adopt it instead of silently starting an empty database."""
    if db_path == _config.LEGACY_APP_DIR_DB and not db_path.exists() and _LEGACY_DB_PATH.exists():
        _LEGACY_DB_PATH.rename(db_path)
        print(f"Renamed {_LEGACY_DB_PATH.name} -> {db_path.name} (Book Tracker was previously LNRelease).")


# DB files whose schema/migrations have already been applied by this
# process. get_conn() runs on every request, so doing the CREATE TABLE /
# ALTER TABLE pass only once per file keeps requests cheap.
_initialized_paths: set = set()


def get_conn(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    key = str(db_path.resolve())
    if key not in _initialized_paths:
        _migrate_legacy_db_file(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=15)
    conn.row_factory = sqlite3.Row
    if key not in _initialized_paths:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.executescript(SCHEMA)
        _migrate(conn)
        _initialized_paths.add(key)
    return conn


def _parse_csv_rows(csv_text: str) -> List[List[str]]:
    reader = _csv.reader(_io.StringIO(csv_text))
    return [row for row in reader if len(row) >= 8]


def _group_csv(csv_text: str) -> Dict[tuple, Dict[str, Any]]:
    """Group raw CSV rows by (title, volume, date) into one release event
    each, with independent ebook/print/audiobook flags and a slug."""
    groups: Dict[tuple, List[List[str]]] = defaultdict(list)
    for row in _parse_csv_rows(csv_text):
        slug, url, publisher, title, volume, fmt, isbn, date = row[:8]
        groups[(title, volume, date)].append([slug, url, publisher, fmt])

    out = {}
    for key, rows in groups.items():
        title, volume, date_str = key
        try:
            datetime.date.fromisoformat(date_str)
        except ValueError:
            continue

        has_ebook = has_print = has_audiobook = False
        chosen_url = chosen_publisher = chosen_slug = None
        for slug, url, publisher, fmt in rows:
            flag = _CSV_FORMAT_MAP.get(fmt.strip().lower())
            if flag == "ebook":
                has_ebook = True
            elif flag == "print":
                has_print = True
            elif flag == "audiobook":
                has_audiobook = True
            if chosen_url is None or flag == "ebook":
                chosen_url, chosen_publisher, chosen_slug = url, publisher, slug
            if chosen_slug is None:
                chosen_slug = slug

        out[key] = {
            "slug": chosen_slug,
            "title": title,
            "volume": volume or None,
            "date": date_str,
            "year": int(date_str[:4]),
            "publisher": chosen_publisher,
            "url": chosen_url,
            "ebook": int(has_ebook),
            "print": int(has_print),
            "audiobook": int(has_audiobook),
        }
    return out


def sync_from_csv(csv_text: str, db_path: Path = DEFAULT_DB_PATH) -> Dict[str, int]:
    """Upsert releases parsed from books.csv into the DB. Only rows that
    are new or actually changed get written -- unchanged rows are skipped
    entirely, so a re-sync with no real changes touches zero rows."""
    conn = get_conn(db_path)
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
    added = updated = unchanged = 0

    incoming = _group_csv(csv_text)
    starred_slugs = {r["slug"] for r in conn.execute("SELECT slug FROM stars").fetchall()}

    existing = {}
    for row in conn.execute("SELECT title, volume, date, slug, publisher, url, ebook, print, audiobook FROM releases"):
        existing[(row["title"], row["volume"], row["date"])] = row

    for key, item in incoming.items():
        old = existing.get(key)
        if old is None:
            cur = conn.execute(
                "INSERT INTO releases (slug, title, volume, date, year, publisher, url, ebook, print, audiobook, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (item["slug"], item["title"], item["volume"], item["date"], item["year"],
                 item["publisher"], item["url"], item["ebook"], item["print"], item["audiobook"], now),
            )
            added += 1

            # A brand-new volume of an already-starred series: if the
            # immediately preceding volume was dropped, this one inherits
            # that (extends the cascade to a volume that didn't exist yet
            # when the drop happened). Every other case is left alone --
            # it correctly defaults to "to read" via COALESCE at read time.
            if item["slug"] in starred_slugs:
                new_id = cur.lastrowid
                preceding = conn.execute(
                    "SELECT vs.status FROM releases r LEFT JOIN volume_status vs ON vs.release_id = r.id "
                    "WHERE r.slug = ? AND r.date < ? ORDER BY r.date DESC LIMIT 1",
                    (item["slug"], item["date"]),
                ).fetchone()
                if preceding is not None and preceding["status"] == "dropped":
                    conn.execute(
                        "INSERT INTO volume_status (release_id, status, updated_at) VALUES (?, 'dropped', ?)",
                        (new_id, now),
                    )
        else:
            changed = (
                old["slug"] != item["slug"] or old["publisher"] != item["publisher"] or
                old["url"] != item["url"] or old["ebook"] != item["ebook"] or
                old["print"] != item["print"] or old["audiobook"] != item["audiobook"]
            )
            if changed:
                conn.execute(
                    "UPDATE releases SET slug=?, publisher=?, url=?, ebook=?, print=?, audiobook=?, updated_at=? "
                    "WHERE title=? AND volume=? AND date=?",
                    (item["slug"], item["publisher"], item["url"], item["ebook"], item["print"],
                     item["audiobook"], now, key[0], key[1], key[2]),
                )
                updated += 1
            else:
                unchanged += 1

    conn.commit()
    conn.close()
    return {"added": added, "updated": updated, "unchanged": unchanged, "total": len(incoming)}


def get_years(db_path: Path = DEFAULT_DB_PATH) -> List[int]:
    conn = get_conn(db_path)
    rows = conn.execute("SELECT DISTINCT year FROM releases ORDER BY year").fetchall()
    conn.close()
    return [r["year"] for r in rows]


def get_year_releases(year: int, db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    conn = get_conn(db_path)
    rows = conn.execute(
        f"SELECT {RELEASE_COLS}, (s.slug IS NOT NULL) AS starred, "
        "COALESCE(vs.status, '') AS status "
        "FROM releases r LEFT JOIN stars s ON s.slug = r.slug "
        "LEFT JOIN volume_status vs ON vs.release_id = r.id "
        "WHERE r.year = ? ORDER BY r.date, r.title",
        (year,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_releases(query: str, db_path: Path = DEFAULT_DB_PATH, limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_conn(db_path)
    like = f"%{query}%"
    rows = conn.execute(
        f"SELECT {RELEASE_COLS}, (s.slug IS NOT NULL) AS starred, "
        "COALESCE(vs.status, '') AS status "
        "FROM releases r LEFT JOIN stars s ON s.slug = r.slug "
        "LEFT JOIN volume_status vs ON vs.release_id = r.id "
        "WHERE r.title LIKE ? COLLATE NOCASE "
        "ORDER BY r.date DESC LIMIT ?",
        (like, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


FORMAT_PREF_VALUES = {"ebook", "print", "audiobook"}


def _attach_format_prefs(conn: sqlite3.Connection, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attach each row's series-level format-tracking preference (a list
    of format keys, or [] meaning 'no preference set -- track/show every
    format'). Done as a second query + Python-side merge rather than a
    SQL join, since the stored value is a single comma-separated column
    that's simplest to split in Python."""
    prefs = {r["slug"]: r["formats"] for r in conn.execute("SELECT slug, formats FROM series_format_pref")}
    for row in rows:
        raw = prefs.get(row["slug"])
        row["format_pref"] = raw.split(",") if raw else []
    return rows


def set_series_format_pref(slug: str, formats: List[str], db_path: Path = DEFAULT_DB_PATH) -> List[str]:
    """Set which format(s) to track to completion for a series. An empty
    list clears the preference (falls back to tracking/showing every
    format, the original behavior)."""
    bad = set(formats) - FORMAT_PREF_VALUES
    if bad:
        raise ValueError(f"invalid format(s): {bad}")
    conn = get_conn(db_path)
    if not formats:
        conn.execute("DELETE FROM series_format_pref WHERE slug = ?", (slug,))
    else:
        conn.execute(
            "INSERT INTO series_format_pref (slug, formats, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(slug) DO UPDATE SET formats=excluded.formats, updated_at=excluded.updated_at",
            (slug, ",".join(formats), _now()),
        )
    conn.commit()
    conn.close()
    return formats


def get_starred_releases(db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """All releases belonging to any starred series, across every year --
    the data behind the /starred page."""
    conn = get_conn(db_path)
    rows = conn.execute(
        f"SELECT {RELEASE_COLS}, 1 AS starred, "
        "COALESCE(vs.status, ?) AS status "
        "FROM releases r JOIN stars s ON s.slug = r.slug "
        "LEFT JOIN volume_status vs ON vs.release_id = r.id "
        "ORDER BY r.title, r.date",
        (DEFAULT_STATUS,),
    ).fetchall()
    result = _attach_format_prefs(conn, [dict(r) for r in rows])
    conn.close()
    return result


def toggle_star(slug: str, db_path: Path = DEFAULT_DB_PATH) -> bool:
    """Toggle star for a series slug. Returns the new starred state.
    Starring also seeds a default 'to_read' status for every volume of
    that series that doesn't already have a status -- the whole point of
    starring is "I want to read this", so that's a sensible default
    rather than making the user set it by hand for every volume."""
    conn = get_conn(db_path)
    row = conn.execute("SELECT 1 FROM stars WHERE slug = ?", (slug,)).fetchone()
    if row:
        conn.execute("DELETE FROM stars WHERE slug = ?", (slug,))
        new_state = False
    else:
        conn.execute("INSERT INTO stars (slug, starred_at) VALUES (?, ?)",
                     (slug, _now()))
        new_state = True
        now = _now()
        release_ids = [r["id"] for r in conn.execute("SELECT id FROM releases WHERE slug = ?", (slug,)).fetchall()]
        for rid in release_ids:
            conn.execute(
                "INSERT OR IGNORE INTO volume_status (release_id, status, updated_at) VALUES (?, ?, ?)",
                (rid, DEFAULT_STATUS, now),
            )
    conn.commit()
    conn.close()
    return new_state


def get_starred_slugs(db_path: Path = DEFAULT_DB_PATH) -> List[str]:
    conn = get_conn(db_path)
    rows = conn.execute("SELECT slug FROM stars").fetchall()
    conn.close()
    return [r["slug"] for r in rows]


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def set_volume_status(release_id: int, status: str, db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """
    Set the reading status of one volume. Returns every (release_id,
    status) pair that actually changed, including cascade effects, so the
    caller can update its UI without a full reload.

    Cascade: setting a volume to 'dropped' or 'to_read' applies the same
    status to every chronologically-later volume of the same series (see
    _FORWARD_CASCADE_STATUSES above) -- e.g. dropping volume 5 also drops
    6, 7, 8... Earlier volumes are never touched by a volume-level change.
    """
    if status not in STATUSES:
        raise ValueError(f"invalid status: {status!r}")

    conn = get_conn(db_path)
    row = conn.execute("SELECT slug, date FROM releases WHERE id = ?", (release_id,)).fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"no release with id {release_id}")

    changed = []
    now = _now()

    def _apply(rid: int, new_status: str):
        conn.execute(
            "INSERT INTO volume_status (release_id, status, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(release_id) DO UPDATE SET status=excluded.status, updated_at=excluded.updated_at",
            (rid, new_status, now),
        )
        changed.append({"id": rid, "status": new_status})

    _apply(release_id, status)

    if status in _FORWARD_CASCADE_STATUSES:
        later = conn.execute(
            "SELECT id FROM releases WHERE slug = ? AND date > ? ORDER BY date",
            (row["slug"], row["date"]),
        ).fetchall()
        for r in later:
            _apply(r["id"], status)

    conn.commit()
    conn.close()
    return changed


def set_series_status(slug: str, status: str, db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Set every volume of a series to the same status (bulk). Returns
    every (release_id, status) pair written."""
    if status not in STATUSES:
        raise ValueError(f"invalid status: {status!r}")

    conn = get_conn(db_path)
    ids = [r["id"] for r in conn.execute("SELECT id FROM releases WHERE slug = ?", (slug,)).fetchall()]
    now = _now()
    changed = []
    for rid in ids:
        conn.execute(
            "INSERT INTO volume_status (release_id, status, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(release_id) DO UPDATE SET status=excluded.status, updated_at=excluded.updated_at",
            (rid, status, now),
        )
        changed.append({"id": rid, "status": status})
    conn.commit()
    conn.close()
    return changed


def get_releases_by_status(status: str, db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """All releases (any year) currently at a given reading status --
    backs the year page's status filter."""
    if status not in STATUSES:
        raise ValueError(f"invalid status: {status!r}")
    conn = get_conn(db_path)
    rows = conn.execute(
        f"SELECT {RELEASE_COLS}, (s.slug IS NOT NULL) AS starred, vs.status "
        "FROM releases r JOIN volume_status vs ON vs.release_id = r.id "
        "LEFT JOIN stars s ON s.slug = r.slug "
        "WHERE vs.status = ? ORDER BY r.title, r.date",
        (status,),
    ).fetchall()
    result = _attach_format_prefs(conn, [dict(r) for r in rows])
    conn.close()
    return result


# ---------------------------------------------------------------------------
# "Add a book" feature: manually-added books/series that came from an
# external search (Google Books / Open Library / Audible) rather than the
# LNRelease CSV feed. These reuse the exact same releases/stars/
# volume_status tables and slug-based grouping as everything else, which is
# what makes them show up in ★ My Starred, the accordion, and the status
# filters automatically -- no separate code path needed there.
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Turn arbitrary text into a stable, URL/DOM-safe slug fragment.
    Falls back to a short hash for text that has no a-z0-9 in it at all,
    so two unrelated titles can never collide into an empty string."""
    s = _re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s or _hashlib.md5((text or "").encode("utf-8")).hexdigest()[:8]


def make_manual_series_slug(kind: str, series_title: str, author: str) -> str:
    """Stable slug for a manually-added series -- shared by every volume
    in it, exactly like an LNRelease slug is shared by every volume of a
    light novel series. Prefixed with 'manual-' so it can never collide
    with a real LNRelease slug."""
    return f"manual-{kind}-{slugify(f'{series_title}-{author}')}"


def make_manual_standalone_slug(kind: str, title: str, author: str, external_id: str) -> str:
    """Slug for a manually-added book with no detected series -- unique
    to this one book (includes the external id) rather than shared."""
    return f"manual-{kind}-{slugify(f'{title}-{author}-{external_id}')}"


def add_manual_entries(entries: List[Dict[str, Any]], db_path: Path = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Insert one or more manually-added volumes (all belonging to the
    same slug, normally -- one call per series, or one call for a single
    standalone book), star that slug, and apply whatever reading status
    each entry asked for (so "I've already read books 1-8 of this" can be
    set in the same action as adding the series).

    Each entry needs: slug, title, date (YYYY-MM-DD), and the ebook/
    print/audiobook flags (0/1). volume, publisher, url, author, status
    are optional (status defaults to 'to_read').

    A volume that's already in the DB (same title/volume/date -- e.g.
    re-adding a series that shares a volume with one already tracked) is
    skipped for insertion but still gets its requested status applied,
    so re-adding is safe and idempotent rather than erroring out.
    """
    conn = get_conn(db_path)
    now = _now()
    added = 0
    skipped = 0
    slugs_seen: List[str] = []
    id_status_pairs: List[tuple] = []

    for e in entries:
        slug = e["slug"]
        if slug not in slugs_seen:
            slugs_seen.append(slug)
        status = e.get("status") or DEFAULT_STATUS
        date = e.get("date") or f"{datetime.date.today().year}-01-01"
        try:
            year = int(str(date)[:4])
        except ValueError:
            year = datetime.date.today().year
        try:
            cur = conn.execute(
                "INSERT INTO releases (slug, title, volume, date, year, publisher, url, author, "
                "subtitle, narrator, series_title, runtime_minutes, isbn, cover_url, genres, "
                "description, language, external_id, source_label, "
                "source, ebook, print, audiobook, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (slug, e.get("title") or "Untitled", e.get("volume"), date, year,
                 e.get("publisher"), e.get("url"), e.get("author"),
                 e.get("subtitle"), e.get("narrator"), e.get("series_title"), e.get("runtime_minutes"),
                 e.get("isbn"), e.get("cover_url"), e.get("genres"),
                 e.get("description"), e.get("language"), e.get("external_id"), e.get("source_label"),
                 "manual",
                 int(bool(e.get("ebook"))), int(bool(e.get("print"))), int(bool(e.get("audiobook"))), now),
            )
            added += 1
            id_status_pairs.append((cur.lastrowid, status))
        except sqlite3.IntegrityError:
            skipped += 1
            existing = conn.execute(
                "SELECT id FROM releases WHERE title = ? AND date = ? AND "
                "(volume IS ? OR volume = ?)",
                (e.get("title") or "Untitled", date, e.get("volume"), e.get("volume")),
            ).fetchone()
            if existing is not None:
                id_status_pairs.append((existing["id"], status))

    for slug in slugs_seen:
        conn.execute("INSERT OR IGNORE INTO stars (slug, starred_at) VALUES (?, ?)", (slug, now))

    for release_id, status in id_status_pairs:
        conn.execute(
            "INSERT INTO volume_status (release_id, status, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(release_id) DO UPDATE SET status=excluded.status, updated_at=excluded.updated_at",
            (release_id, status, now),
        )
    conn.commit()

    placeholders = ",".join("?" * len(slugs_seen)) or "NULL"
    rows = conn.execute(
        f"SELECT {RELEASE_COLS}, 1 AS starred, "
        "COALESCE(vs.status, ?) AS status "
        f"FROM releases r LEFT JOIN volume_status vs ON vs.release_id = r.id "
        f"WHERE r.slug IN ({placeholders}) ORDER BY r.title, r.date",
        (DEFAULT_STATUS, *slugs_seen),
    ).fetchall()
    result_rows = _attach_format_prefs(conn, [dict(r) for r in rows])
    conn.close()
    return {"added": added, "skipped": skipped, "slugs": slugs_seen, "releases": result_rows}


# ---------------------------------------------------------------------------
# Editing a single release's metadata (the "click a book to edit it"
# feature). Works on ANY release row, LNRelease-synced or manually added --
# editing an LNRelease row just means your local corrections stick until
# the next sync overwrites that particular field again from the CSV feed.
# ---------------------------------------------------------------------------

EDITABLE_FIELDS = (
    "title", "subtitle", "author", "narrator", "series_title", "volume",
    "publisher", "language", "runtime_minutes", "isbn", "cover_url",
    "date", "genres", "source_label", "url", "description",
    "ebook", "print", "audiobook",
)


def get_release(release_id: int, db_path: Path = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    """A single release row, in the same shape as everything else
    (starred/status/format_pref included), for prefilling the edit form."""
    conn = get_conn(db_path)
    row = conn.execute(
        f"SELECT {RELEASE_COLS}, (s.slug IS NOT NULL) AS starred, "
        "COALESCE(vs.status, ?) AS status "
        "FROM releases r LEFT JOIN stars s ON s.slug = r.slug "
        "LEFT JOIN volume_status vs ON vs.release_id = r.id "
        "WHERE r.id = ?",
        (DEFAULT_STATUS, release_id),
    ).fetchone()
    if row is None:
        conn.close()
        return None
    result = _attach_format_prefs(conn, [dict(row)])[0]
    conn.close()
    return result


def update_release_metadata(release_id: int, fields: Dict[str, Any], db_path: Path = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Update whichever editable fields were provided (unknown keys are
    silently ignored rather than erroring, so the caller can just forward
    a whole form payload). `date` also recomputes `year` to keep the two
    in sync. Returns the updated row via get_release()."""
    updates = {k: v for k, v in fields.items() if k in EDITABLE_FIELDS}
    if not updates:
        row = get_release(release_id, db_path=db_path)
        if row is None:
            raise ValueError(f"no release with id {release_id}")
        return row

    conn = get_conn(db_path)
    existing = conn.execute("SELECT date FROM releases WHERE id = ?", (release_id,)).fetchone()
    if existing is None:
        conn.close()
        raise ValueError(f"no release with id {release_id}")

    if "ebook" in updates:
        updates["ebook"] = int(bool(updates["ebook"]))
    if "print" in updates:
        updates["print"] = int(bool(updates["print"]))
    if "audiobook" in updates:
        updates["audiobook"] = int(bool(updates["audiobook"]))
    if "runtime_minutes" in updates and updates["runtime_minutes"] not in (None, ""):
        try:
            updates["runtime_minutes"] = int(updates["runtime_minutes"])
        except (TypeError, ValueError):
            updates["runtime_minutes"] = None

    date_value = updates.get("date") or existing["date"]
    try:
        updates["year"] = int(str(date_value)[:4])
    except ValueError:
        pass

    set_clause = ", ".join(f"{col} = ?" for col in updates)
    conn.execute(
        f"UPDATE releases SET {set_clause}, updated_at = ? WHERE id = ?",
        (*updates.values(), _now(), release_id),
    )
    conn.commit()
    conn.close()
    row = get_release(release_id, db_path=db_path)
    if row is None:
        raise ValueError(f"no release with id {release_id}")
    return row


def get_recent_manual_releases(limit: int = 25, db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Recently-added manually-tracked releases (newest first), for the
    "Your Book Tracker items" list at the bottom of the /add page --
    quick feedback on what you've just added, with the same status
    picker + remove control used everywhere else."""
    conn = get_conn(db_path)
    rows = conn.execute(
        f"SELECT {RELEASE_COLS}, (s.slug IS NOT NULL) AS starred, "
        "COALESCE(vs.status, ?) AS status "
        "FROM releases r LEFT JOIN stars s ON s.slug = r.slug "
        "LEFT JOIN volume_status vs ON vs.release_id = r.id "
        "WHERE r.source = 'manual' ORDER BY r.updated_at DESC, r.id DESC LIMIT ?",
        (DEFAULT_STATUS, limit),
    ).fetchall()
    result = _attach_format_prefs(conn, [dict(r) for r in rows])
    conn.close()
    return result


def remove_manual_release(release_id: int, db_path: Path = DEFAULT_DB_PATH) -> None:
    """Delete one manually-added release entirely (not just unstar it --
    this is for undoing an add-page mistake). Refuses to touch an
    LNRelease-synced row; use the star toggle for those instead."""
    conn = get_conn(db_path)
    row = conn.execute("SELECT source FROM releases WHERE id = ?", (release_id,)).fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"no release with id {release_id}")
    if row["source"] != "manual":
        conn.close()
        raise ValueError("only manually-added releases can be removed this way -- unstar an LNRelease title instead")
    conn.execute("DELETE FROM volume_status WHERE release_id = ?", (release_id,))
    conn.execute("DELETE FROM releases WHERE id = ?", (release_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# "My Books" -- imported from an external CSV (Goodreads export).
# Separate table, separate lifecycle, deliberately NOT mixed with the
# `releases` table used by My Starred / the year pages. Only five fields
# are kept: title, author, publisher, date_published, date_read.
# ---------------------------------------------------------------------------

# Sanity caps. A typical Goodreads export with 1,000 books is ~500 KB; the
# 20 MB / 50,000-row caps give 40x headroom on both axes while still
# bounding worst-case work (and memory) if a hostile or malformed file is
# uploaded. The per-request 25 MB Flask cap (see app.py) provides an
# outer defence before this code even runs.
MAX_IMPORT_ROWS = 50_000
MAX_IMPORT_WARNINGS = 100


def _imported_signature(title: str, author: Optional[str], date_published: Optional[str]) -> str:
    """Stable dedupe key for imported books: (title, author, date_published),
    case-insensitively. Publisher is deliberately excluded -- a Goodreads
    export can change 'Publisher' slightly between syncs (e.g. 'Penguin'
    vs 'Penguin Books'), and that shouldn't cause a duplicate. If all three
    are empty (a truly degenerate row) the signature still hashes to a
    stable non-empty string, so a UNIQUE constraint violation still happens
    on re-import rather than silently allowing duplicates."""
    parts = [(x or "").strip().lower() for x in (title, author, date_published)]
    return _hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def _parse_year_only(text: str) -> Optional[str]:
    """'2019' -> '2019'; 'copyright 2019' -> '2019'; '' -> None."""
    if not text:
        return None
    m = _re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", text)
    return m.group(1) if m else None


def _parse_iso_or_goodreads_date(text: str) -> Optional[str]:
    """Goodreads Date Read is 'YYYY/MM/DD'. Also accept 'YYYY-MM-DD'.
    '0000/00/00' (Goodreads' unread placeholder) and anything unparseable
    become None -- treated as unread, matching the user's "blank is
    Unsorted" rule."""
    if not text:
        return None
    text = text.strip()
    if not text or text == "0000/00/00":
        return None
    m = _re.fullmatch(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", text)
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return None


def parse_goodreads_csv(csv_text: str) -> tuple:
    """Parse a Goodreads-format CSV export.

    Returns (rows, warnings, skipped_rows):
      rows        -- list of dicts with keys title, author, publisher,
                     date_published, date_read
      warnings    -- list of fixed human-readable warning strings (capped)
      skipped_rows -- count of rows dropped for having no title

    Raises ValueError only for structural problems (empty file, no
    Title column). The message is a fixed string, never the raw
    exception text.
    """
    if not csv_text or not csv_text.strip():
        raise ValueError("CSV file is empty")

    reader = _csv.DictReader(_io.StringIO(csv_text))
    if not reader.fieldnames:
        raise ValueError("CSV has no header row")

    # Case-insensitive column lookup -- Goodreads exports use Title Case
    # headers, but a hand-edited file might not.
    field_map: Dict[str, str] = {}
    for name in reader.fieldnames:
        if name:
            field_map[name.strip().lower()] = name

    if "title" not in field_map:
        raise ValueError("CSV must have a 'Title' column")

    def col(row: Dict[str, str], key: str) -> str:
        name = field_map.get(key)
        if not name:
            return ""
        return (row.get(name) or "").strip()

    rows: List[Dict[str, Any]] = []
    warnings: List[str] = []
    skipped_rows = 0
    over_limit = False

    for i, raw in enumerate(reader, start=2):  # row 1 is the header
        if i - 1 > MAX_IMPORT_ROWS:
            warnings.append(f"Stopped at row {i} — import limit is {MAX_IMPORT_ROWS} rows")
            over_limit = True
            break
        title = col(raw, "title")
        if not title:
            skipped_rows += 1
            continue
        author = col(raw, "author") or None
        publisher = col(raw, "publisher") or None
        date_published = _parse_year_only(col(raw, "year published"))
        date_read_raw = col(raw, "date read")
        date_read = _parse_iso_or_goodreads_date(date_read_raw)
        if date_read_raw and not date_read and len(warnings) < MAX_IMPORT_WARNINGS:
            # Note: deliberately NOT including `date_read_raw` in the
            # message -- that's user-controlled CSV content, and we don't
            # want it flowing back into any log/error surface.
            warnings.append(f"Row {i}: unrecognized Date Read value — treated as unread")
        rows.append({
            "title": title,
            "author": author,
            "publisher": publisher,
            "date_published": date_published,
            "date_read": date_read,
        })

    if not over_limit and len(warnings) > MAX_IMPORT_WARNINGS:
        extra = len(warnings) - MAX_IMPORT_WARNINGS
        warnings = warnings[:MAX_IMPORT_WARNINGS] + [f"…and {extra} more warnings (suppressed)"]

    return rows, warnings, skipped_rows


def add_imported_books(rows: List[Dict[str, Any]], db_path: Path = DEFAULT_DB_PATH) -> Dict[str, int]:
    """Bulk-insert parsed CSV rows into `imported_books`.

    Returns {added, skipped, errors}. `skipped` counts dedupe hits (rows
    whose signature already exists) -- re-importing the same Goodreads
    export a second time should report 'skipped: N' and add nothing.
    """
    conn = get_conn(db_path)
    now = _now()
    added = 0
    skipped = 0
    errors = 0
    for row in rows:
        sig = _imported_signature(row["title"], row.get("author"), row.get("date_published"))
        try:
            conn.execute(
                "INSERT INTO imported_books "
                "(imported_signature, title, author, publisher, date_published, date_read, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (sig, row["title"], row.get("author"), row.get("publisher"),
                 row.get("date_published"), row.get("date_read"), now, now),
            )
            added += 1
        except sqlite3.IntegrityError:
            skipped += 1
        except sqlite3.Error:
            errors += 1
    conn.commit()
    conn.close()
    return {"added": added, "skipped": skipped, "errors": errors}


def get_imported_books(db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """All imported books, in a stable order (by title). The page splits
    them into Book Read / Unsorted client-side based on date_read."""
    conn = get_conn(db_path)
    rows = conn.execute(
        "SELECT id, title, author, publisher, date_published, date_read "
        "FROM imported_books ORDER BY title COLLATE NOCASE"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_imported_book(book_id: int, fields: Dict[str, Any], db_path: Path = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Update editable fields of an imported book. `date_read` is the only
    field the UI currently changes, but title/author/publisher/date_published
    are accepted too for future-proofing; changing any of them recomputes
    the dedupe signature so the DB stays consistent.

    Raises KeyError if the book doesn't exist (caller maps that to 404),
    ValueError if the supplied data is invalid or would collide with
    another row (caller maps that to 400).
    """
    editable = {"date_read", "title", "author", "publisher", "date_published"}
    updates: Dict[str, Any] = {k: v for k, v in fields.items() if k in editable}
    if not updates:
        raise ValueError("no editable fields provided")

    # Normalize empty strings to NULL and strip whitespace.
    for k in list(updates.keys()):
        v = updates[k]
        if isinstance(v, str):
            v = v.strip()
            if v == "" or v == "0000-00-00":
                updates[k] = None
            else:
                updates[k] = v

    if "date_read" in updates and updates["date_read"]:
        try:
            datetime.date.fromisoformat(updates["date_read"])
        except ValueError:
            raise ValueError("date_read must be YYYY-MM-DD")

    conn = get_conn(db_path)
    existing = conn.execute(
        "SELECT id, title, author, date_published FROM imported_books WHERE id = ?", (book_id,)
    ).fetchone()
    if existing is None:
        conn.close()
        raise KeyError(book_id)

    if any(k in updates for k in ("title", "author", "date_published")):
        new_title = updates.get("title", existing["title"])
        new_author = updates.get("author", existing["author"])
        new_dp = updates.get("date_published", existing["date_published"])
        updates["imported_signature"] = _imported_signature(new_title, new_author, new_dp)

    set_clause = ", ".join(f"{col} = ?" for col in updates)
    try:
        conn.execute(
            f"UPDATE imported_books SET {set_clause}, updated_at = ? WHERE id = ?",
            (*updates.values(), _now(), book_id),
        )
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError("a book with those details already exists")
    conn.commit()
    row = conn.execute(
        "SELECT id, title, author, publisher, date_published, date_read "
        "FROM imported_books WHERE id = ?", (book_id,)
    ).fetchone()
    conn.close()
    return dict(row)


def remove_imported_book(book_id: int, db_path: Path = DEFAULT_DB_PATH) -> None:
    conn = get_conn(db_path)
    row = conn.execute("SELECT id FROM imported_books WHERE id = ?", (book_id,)).fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"no imported book with id {book_id}")
    conn.execute("DELETE FROM imported_books WHERE id = ?", (book_id,))
    conn.commit()
    conn.close()