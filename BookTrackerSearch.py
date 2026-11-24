"""
External metadata lookups for Book Tracker's "Add a book" page (search
for, or paste a URL for, a book/ebook/audiobook and add it -- with full
metadata -- to ★ My Starred).

Sources
-------
- Hardcover (api.hardcover.app, GraphQL) -- the default provider for
  ebook/print search & detail. Requires a personal API token (free) --
  set HARDCOVER_API_TOKEN in the environment; get one at
  https://hardcover.app/account/api. NEVER commit this token to a file
  or expose it to a browser -- Hardcover's own docs are explicit that
  the token can delete your account and must only be used from a
  backend. This module only ever calls Hardcover from the Flask server
  process, never from frontend JS, which satisfies that requirement.
- Google Books (googleapis.com/books/v1) -- ebook/print search & detail.
  Works without an API key for this light, occasional usage; set
  GOOGLE_BOOKS_API_KEY in the environment if you hit Google's
  unauthenticated rate limit and it'll be sent along automatically.
- Open Library (openlibrary.org) -- ebook/print search & detail. Open
  Library editions frequently encode series membership right in the
  edition title -- e.g. "Storm Front ((The Dresden Files, Book 1))" --
  or in a dedicated bibliographic `series` field like
  "Dresden files ; bk. 1". We use whichever is present to prefill the
  Series / Series Volume fields on the picked book. This is a
  heuristic (Open Library's edition data is inconsistent), which is
  why those fields land in an editable form rather than being trusted
  blindly -- but it's also why fixing/setting the Series field once is
  enough: every subsequent book you add with the same Series + Author
  groups together on ★ My Starred automatically.
- Audible + Audnexus (api.audible.com / api.audnex.us) -- audiobook
  search & detail. Audible's product-search endpoint (unauthenticated,
  the same one tools like Audiobookshelf use) powers the search list;
  Audnexus (a community aggregator over Audible's own catalog) powers
  the rich single-book detail fetch (narrator, runtime, genres,
  summary, exact series name + position) once you pick a result or
  paste an ASIN/Audible URL directly.
- Amazon -- URL-paste only, best-effort. Amazon has no public product-
  catalog API (the Product Advertising API requires an active
  affiliate account with sales volume), so there's no keyword search
  for it here -- only "paste a product page URL and we'll try to
  scrape the title/author/cover off the page". Amazon actively blocks
  a lot of non-browser traffic, so this can fail; when it does, the
  ASIN from the URL is still extracted and the rest of the form is
  just left for you to fill in by hand.

Goodreads is not used at all: its public API was closed to new
registrations in December 2020.

Everything here runs against free, rate-limited public endpoints with
no uptime guarantee -- callers should expect the occasional empty
result, timeout, or partial record, and treat what comes back as a
prefilled starting point for the editable form, not ground truth.
"""
from __future__ import annotations

import os
import re
import sys
import time
import json
import html as _html
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse

import requests

import BookTrackerCfg as _config

REQUEST_TIMEOUT = 8
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 BookTracker/2026.08.05-01")

# Caps how much of a fetched page's HTML the scraping regexes below ever
# scan. Amazon's actual product markup we care about is always near the
# top of the page, well under this -- the cap exists purely so a page
# that returns pathologically large or malformed HTML (whether by
# accident or by a malicious server) can't make regex matching take an
# unbounded amount of time.
MAX_SCRAPED_HTML_CHARS = 1_500_000

# Read from the environment first, then config.ini (see BookTrackerCfg.py) --
# never from a file inside the app folder, so tokens can't end up in git.
GOOGLE_BOOKS_API_KEY = _config.secret("api", "google_books_key")
HARDCOVER_API_TOKEN = _config.secret("api", "hardcover_token")


class ExternalSearchError(Exception):
    """Raised when a request to an external source fails outright.
    Callers generally catch this per-source so one flaky API doesn't
    sink a combined search."""


def _redact_url(url: str) -> str:
    """The URL with any query string stripped -- safe to put in a
    message shown to the end user. A full URL (including one of ours)
    can carry a credential in the query string -- e.g. Google Books'
    optional `key=...` param -- so error text shown to the browser must
    never include it. requests/urllib3 exception messages often embed
    the full request URL too, which is why the except blocks below
    build their own message instead of including str(e) verbatim."""
    return url.split("?", 1)[0]


def _get(url: str, params: Optional[dict] = None, as_json: bool = True, retries: int = 2) -> Any:
    last_error = None
    for attempt in range(retries + 1):
        resp = None
        try:
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT,
                                 headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            if resp.status_code == 429:
                # Rate-limited. Google Books' unauthenticated quota in
                # particular is shared/IP-based and easy to exhaust with
                # only light traffic -- worth a couple of short-backoff
                # retries before giving up, since it's often a burst
                # limit rather than a hard daily one.
                last_error = requests.HTTPError(f"429 rate-limited by {_redact_url(url)}")
                if attempt < retries:
                    time.sleep(0.6 * (attempt + 1))
                    continue
                raise ExternalSearchError(
                    f"Rate-limited by {url.split('/')[2]} (HTTP 429). This is usually a shared/"
                    "unauthenticated-quota limit, not a per-user one -- wait a bit and try again, "
                    "or (for Google Books specifically) set GOOGLE_BOOKS_API_KEY in the environment."
                )
            resp.raise_for_status()
            return resp.json() if as_json else resp.text
        except requests.RequestException as e:
            last_error = e
            if resp is not None and getattr(resp, "status_code", None) in (500, 502, 503, 504) and attempt < retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            # Full exception detail (which can include the request URL,
            # and therefore any API key in its query string) is logged
            # server-side only -- never included in the message that
            # gets sent back to the browser.
            print(f"[external_search] GET {_redact_url(url)} failed: {e}", file=sys.stderr)
            raise ExternalSearchError(
                f"Request to {_redact_url(url)} failed ({type(e).__name__}). "
                "The source may be temporarily unavailable -- try again in a moment."
            ) from e
    print(f"[external_search] GET {_redact_url(url)} failed: {last_error}", file=sys.stderr)
    raise ExternalSearchError(
        f"Request to {_redact_url(url)} failed"
        f"{f' ({type(last_error).__name__})' if last_error else ''}. "
        "The source may be temporarily unavailable -- try again in a moment."
    )


def _strip_html(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    # Excluding '<' as well as '>' from the "content" class (not just
    # '>') removes the ambiguity that makes this pattern's worst-case
    # matching time scale with input length: with only '>' excluded, a
    # run of unmatched '<' characters gives the regex engine many ways
    # to (mis)pair "start tag" attempts before backtracking out of each.
    text = re.sub(r"<[^<>]+>", " ", text)
    text = _html.unescape(text)
    return re.sub(r"\s+", " ", text).strip() or None


def _year_to_date(year: Any) -> Optional[str]:
    try:
        return f"{int(year):04d}-01-01"
    except (TypeError, ValueError):
        return None


def _normalize_date(raw: Any) -> Optional[str]:
    """Google Books / Open Library dates arrive as 'YYYY', 'YYYY-MM', or
    'YYYY-MM-DD'; Audnexus/Audible send a full ISO datetime. Normalize
    all of them down to YYYY-MM-DD, since that's what the releases
    table requires."""
    if not raw:
        return None
    raw = str(raw)
    if re.fullmatch(r"\d{4}", raw):
        return f"{raw}-01-01"
    if re.fullmatch(r"\d{4}-\d{2}", raw):
        return f"{raw}-01"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    m_full = re.match(r"(\d{4}-\d{2}-\d{2})T", raw)
    if m_full:
        return m_full.group(1)
    m = re.match(r"(\d{4})", raw)
    return f"{m.group(1)}-01-01" if m else None


_MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July",
                "August", "September", "October", "November", "December")
_LOOSE_DATE_FORMATS = ("%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y", "%B %Y", "%b %Y")


def _parse_loose_date(text: Optional[str]) -> Optional[str]:
    """Parse a free-text date like Amazon's "Publication date" bullet
    ("June 28, 2005") or Open Library's edition "publish_date" ("March
    1995", "1995"). Tries ISO-ish forms first, then a handful of
    month-name formats, then falls back to a bare 4-digit year found
    anywhere in the string."""
    if not text:
        return None
    text = text.strip()
    iso = _normalize_date(text)
    if iso:
        return iso
    for fmt in _LOOSE_DATE_FORMATS:
        try:
            import datetime as _dt
            return _dt.datetime.strptime(text, fmt).strftime("%Y-%m-01" if fmt in ("%B %Y", "%b %Y") else "%Y-%m-%d")
        except ValueError:
            continue
    m = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", text)
    return f"{m.group(1)}-01-01" if m else None


# A bare Amazon/Audible ASIN: 10 chars, starts with a letter (almost
# always 'B' for modern ASINs), rest alphanumeric.
_ASIN_RE = re.compile(r"^[A-Z][A-Z0-9]{9}$", re.IGNORECASE)


def looks_like_asin(text: str) -> bool:
    return bool(_ASIN_RE.match((text or "").strip()))


# Book titles/subtitles/series-field strings are inherently short (a
# title is realistically under a couple hundred characters), but
# nothing enforces that upstream -- capping defensively here bounds the
# worst-case cost of the regexes below to a small constant regardless
# of how long a string an API ever hands back.
_MAX_SERIES_TEXT_CHARS = 400

# Matches the "((Series Name, Book N))" / "(Series Name #N)" convention
# Open Library uses on many edition titles, and reused for Google Books
# subtitles like "Artemis Fowl, Book 2".
_SERIES_TITLE_RE = re.compile(
    r"\(+([^,#()]*?)[\s,]*(?:book|vol\.?|volume|#)\s*(\d+(?:\.\d+)?)\s*\)+",
    re.IGNORECASE,
)
# Matches Open Library's dedicated `series` bib field, e.g.
# "Dresden files ; bk. 1" or "The Expanse ; 3".
_SERIES_FIELD_RE = re.compile(
    r"^([^;]*?)\s*;\s*(?:bk\.?|book|vol\.?|volume)?\s*#?\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
# "Artemis Fowl, Book 2" / "Ranger's Apprentice Book 2" / "Mistborn Vol. 2"
_SERIES_COMMA_RE = re.compile(
    r"^([^,:]*?)[,:]?\s+(?:book|bk\.?|vol\.?|volume|no\.?)\s*#?\s*(\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)
# "Book 2 of the Dresden Files" / "Book 2 of Mistborn"
_BOOK_OF_RE = re.compile(
    r"^(?:book|bk\.?|vol\.?|volume)\s*#?\s*(\d+(?:\.\d+)?)\s+of\s+(?:the\s+)?([^()]+?)\s*(?:series)?$",
    re.IGNORECASE,
)
# "Dresden Files #2" / "Mistborn Series #2"
_HASH_RE = re.compile(r"^([^#]*?)\s*#\s*(\d+(?:\.\d+)?)\s*$")


def _extract_series_from_text(*texts: Optional[str]):
    """Best-effort: pull a series name + book number out of one or more
    candidate strings (title, subtitle, ...) -- whichever matches first.
    Tries several conventions publishers/catalogs commonly use. Returns
    (series_title, series_volume), either of which may be None."""
    for text in texts:
        text = (text or "").strip()[:_MAX_SERIES_TEXT_CHARS]
        if not text:
            continue
        m = _SERIES_TITLE_RE.search(text)
        if m:
            return m.group(1).strip(), m.group(2)
        m = _BOOK_OF_RE.match(text)
        if m:
            return m.group(2).strip(), m.group(1)
        m = _HASH_RE.match(text)
        if m:
            return m.group(1).strip(), m.group(2)
        m = _SERIES_COMMA_RE.match(text)
        if m and m.group(1).strip():
            return m.group(1).strip(), m.group(2)
    return None, None


# ---------------------------------------------------------------------
# Google Books
# ---------------------------------------------------------------------

def search_google_books(title: str, author: str = "", limit: int = 12) -> List[Dict[str, Any]]:
    """Structured search using Google Books' intitle:/inauthor: qualifiers
    instead of one blended free-text string -- a blended string ("Contagion
    Robin Cook" as one query) lets Google's relevance ranking surface an
    unrelated same-titled book by a different author above the one you
    meant; qualifying which part is the title and which is the author
    avoids that."""
    parts = []
    if title:
        parts.append(f'intitle:"{title}"')
    if author:
        parts.append(f'inauthor:"{author}"')
    query = " ".join(parts) or title
    params = {"q": query, "maxResults": limit, "printType": "books"}
    if GOOGLE_BOOKS_API_KEY:
        params["key"] = GOOGLE_BOOKS_API_KEY
    data = _get("https://www.googleapis.com/books/v1/volumes", params)
    out = []
    for item in data.get("items", []):
        info = item.get("volumeInfo", {}) or {}
        images = info.get("imageLinks", {}) or {}
        out.append({
            "source": "googlebooks",
            "external_id": item.get("id"),
            "title": info.get("title") or "Untitled",
            "author": ", ".join(info.get("authors", [])) or None,
            "date": _normalize_date(info.get("publishedDate")),
            "publisher": info.get("publisher"),
            "cover_url": (images.get("thumbnail") or images.get("smallThumbnail") or "").replace("http://", "https://") or None,
            "url": info.get("infoLink"),
        })
    return out


def _search_google_books(query: str, limit: int = 12) -> List[Dict[str, Any]]:
    """Unstructured fallback (single blended query string) -- kept for
    search_books()'s combined search; prefer search_google_books() for
    anything driven by separate title/author fields."""
    params = {"q": query, "maxResults": limit, "printType": "books"}
    if GOOGLE_BOOKS_API_KEY:
        params["key"] = GOOGLE_BOOKS_API_KEY
    data = _get("https://www.googleapis.com/books/v1/volumes", params)
    out = []
    for item in data.get("items", []):
        info = item.get("volumeInfo", {}) or {}
        images = info.get("imageLinks", {}) or {}
        out.append({
            "source": "googlebooks",
            "external_id": item.get("id"),
            "title": info.get("title") or "Untitled",
            "author": ", ".join(info.get("authors", [])) or None,
            "date": _normalize_date(info.get("publishedDate")),
            "publisher": info.get("publisher"),
            "cover_url": (images.get("thumbnail") or images.get("smallThumbnail") or "").replace("http://", "https://") or None,
            "url": info.get("infoLink"),
        })
    return out


def get_google_book_detail(volume_id: str) -> Dict[str, Any]:
    """Full single-volume detail -- richer than a search hit: subtitle,
    description, categories (-> genres), ISBN, language."""
    data = _get(f"https://www.googleapis.com/books/v1/volumes/{volume_id}",
                {"key": GOOGLE_BOOKS_API_KEY} if GOOGLE_BOOKS_API_KEY else None)
    info = data.get("volumeInfo", {}) or {}
    images = info.get("imageLinks", {}) or {}
    isbn = None
    for ident in info.get("industryIdentifiers", []) or []:
        if ident.get("type") in ("ISBN_13", "ISBN_10"):
            isbn = ident.get("identifier")
            if ident.get("type") == "ISBN_13":
                break
    series_title, series_volume = _extract_series_from_text(info.get("subtitle"), info.get("title"))
    return {
        "source": "googlebooks",
        "external_id": data.get("id") or volume_id,
        "title": info.get("title") or "Untitled",
        "subtitle": info.get("subtitle"),
        "author": ", ".join(info.get("authors", [])) or None,
        "narrator": None,
        "series_title": series_title,
        "series_volume": series_volume,
        "publisher": info.get("publisher"),
        "language": info.get("language"),
        "runtime_minutes": None,
        "isbn": isbn,
        "cover_url": (images.get("thumbnail") or images.get("smallThumbnail") or "").replace("http://", "https://") or None,
        "date": _normalize_date(info.get("publishedDate")),
        "genres": ", ".join(info.get("categories", []) or []) or None,
        "description": _strip_html(info.get("description")),
        "url": info.get("infoLink"),
    }


# ---------------------------------------------------------------------
# Open Library
# ---------------------------------------------------------------------

def search_open_library(title: str, author: str = "", limit: int = 12) -> List[Dict[str, Any]]:
    """Structured search using Open Library's separate title=/author=
    query fields instead of one blended string -- same rationale as
    search_google_books(): a blended "title author" string is matched as
    general free text and can rank an unrelated same-titled book above
    the one actually meant."""
    params = {"limit": limit, "fields": "key,title,author_name,first_publish_year,cover_i"}
    if title:
        params["title"] = title
    if author:
        params["author"] = author
    if not title and not author:
        return []
    data = _get("https://openlibrary.org/search.json", params)
    out = []
    for doc in data.get("docs", []):
        cover = doc.get("cover_i")
        year = doc.get("first_publish_year")
        out.append({
            "source": "openlibrary",
            "external_id": doc.get("key"),  # e.g. "/works/OL5685119W"
            "title": doc.get("title") or "Untitled",
            "author": ", ".join(doc.get("author_name", [])[:1]) or None,
            "date": _year_to_date(year),
            "publisher": None,
            "cover_url": f"https://covers.openlibrary.org/b/id/{cover}-M.jpg" if cover else None,
            "url": f"https://openlibrary.org{doc.get('key', '')}" if doc.get("key") else None,
        })
    return out


def _search_open_library(query: str, limit: int = 12) -> List[Dict[str, Any]]:
    """Unstructured fallback (single blended query string) -- kept for
    search_books()'s combined search; prefer search_open_library() for
    anything driven by separate title/author fields."""
    params = {"q": query, "limit": limit,
              "fields": "key,title,author_name,first_publish_year,cover_i"}
    data = _get("https://openlibrary.org/search.json", params)
    out = []
    for doc in data.get("docs", []):
        cover = doc.get("cover_i")
        year = doc.get("first_publish_year")
        out.append({
            "source": "openlibrary",
            "external_id": doc.get("key"),  # e.g. "/works/OL5685119W"
            "title": doc.get("title") or "Untitled",
            "author": ", ".join(doc.get("author_name", [])[:1]) or None,
            "date": _year_to_date(year),
            "publisher": None,
            "cover_url": f"https://covers.openlibrary.org/b/id/{cover}-M.jpg" if cover else None,
            "url": f"https://openlibrary.org{doc.get('key', '')}" if doc.get("key") else None,
        })
    return out


def get_open_library_detail(work_key: str) -> Dict[str, Any]:
    """Full detail for one Open Library work: description from the work
    record, plus series name/number/ISBN/cover/language scavenged from
    whichever edition has the most complete data."""
    try:
        work = _get(f"https://openlibrary.org{work_key}.json")
    except ExternalSearchError:
        work = {}
    description = work.get("description")
    if isinstance(description, dict):
        description = description.get("value")

    series_title = series_volume = isbn = language = cover_url = pub_date = publisher = None
    try:
        editions = _get(f"https://openlibrary.org{work_key}/editions.json", {"limit": 20})
    except ExternalSearchError:
        editions = {"entries": []}
    for ed in editions.get("entries", []):
        if series_title is None:
            m = _SERIES_TITLE_RE.search((ed.get("title", "") or "")[:_MAX_SERIES_TEXT_CHARS])
            if m:
                series_title, series_volume = m.group(1).strip(), m.group(2)
            else:
                for s in ed.get("series", []) or []:
                    m2 = _SERIES_FIELD_RE.match((s or "")[:_MAX_SERIES_TEXT_CHARS])
                    if m2:
                        series_title, series_volume = m2.group(1).strip(), m2.group(2)
                        break
        if isbn is None:
            isbns = ed.get("isbn_13") or ed.get("isbn_10") or []
            if isbns:
                isbn = isbns[0]
        if language is None:
            langs = ed.get("languages") or []
            if langs:
                language = (langs[0].get("key", "") or "").rsplit("/", 1)[-1]
        if cover_url is None and ed.get("covers"):
            cover_url = f"https://covers.openlibrary.org/b/id/{ed['covers'][0]}-M.jpg"
        if pub_date is None and ed.get("publish_date"):
            pub_date = _parse_loose_date(ed["publish_date"])
        if publisher is None and ed.get("publishers"):
            publisher = ed["publishers"][0]

    author_name = None
    for a in work.get("authors", []) or []:
        a_key = (a.get("author") or {}).get("key")
        if not a_key:
            continue
        try:
            a_data = _get(f"https://openlibrary.org{a_key}.json")
            author_name = a_data.get("name")
            break
        except ExternalSearchError:
            continue

    return {
        "source": "openlibrary",
        "external_id": work_key,
        "title": (work.get("title") or "Untitled"),
        "subtitle": work.get("subtitle"),
        "author": author_name,
        "narrator": None,
        "series_title": series_title,
        "series_volume": series_volume,
        "publisher": publisher,
        "language": language,
        "runtime_minutes": None,
        "isbn": isbn,
        "cover_url": cover_url,
        "date": pub_date,
        "genres": ", ".join((work.get("subjects") or [])[:5]) or None,
        "description": _strip_html(description),
        "url": f"https://openlibrary.org{work_key}",
    }


# ---------------------------------------------------------------------
# Hardcover (default provider)
# ---------------------------------------------------------------------
# GraphQL API at api.hardcover.app/v1/graphql. Requires a personal
# bearer token (HARDCOVER_API_TOKEN) -- there's no anonymous/keyless
# access. Search goes through Hardcover's `search` field, which is a
# thin wrapper over their Typesense index and returns a `results` JSON
# blob (shape: a raw hit list, or {"hits":[{"document": {...}}]} --
# handled defensively below since it isn't pinned down in their docs).
# Full single-book detail (cover, ISBN, series position, publisher,
# language, description) comes from a follow-up structured query against
# the `books_by_pk` table, which is normal GraphQL with normal typed
# errors -- those are surfaced verbatim so a field-name mismatch (the
# API is explicitly beta and "heavily in flux") shows up as Hardcover's
# own precise error message rather than silently-wrong data.

_HARDCOVER_GRAPHQL_URL = "https://api.hardcover.app/v1/graphql"

_HARDCOVER_SEARCH_QUERY = """
query BookSearch($query: String!, $perPage: Int!) {
  search(query: $query, query_type: "Book", per_page: $perPage, page: 1) {
    results
  }
}
"""

_HARDCOVER_BOOK_BY_ID_QUERY = """
query BookById($id: Int!) {
  books_by_pk(id: $id) {
    id slug title subtitle description release_date
    image { url }
    cached_tags
    contributions { author { name } }
    editions(limit: 5, order_by: {users_count: desc}) {
      isbn_13 isbn_10 edition_format
      publisher { name }
      language { language }
    }
    book_series {
      position
      series { name }
    }
  }
}
"""

_HARDCOVER_BOOK_BY_SLUG_QUERY = """
query BookBySlug($slug: String!) {
  books(where: {slug: {_eq: $slug}}, limit: 1) {
    id slug title subtitle description release_date
    image { url }
    cached_tags
    contributions { author { name } }
    editions(limit: 5, order_by: {users_count: desc}) {
      isbn_13 isbn_10 edition_format
      publisher { name }
      language { language }
    }
    book_series {
      position
      series { name }
    }
  }
}
"""


def _hardcover_graphql(query: str, variables: Optional[dict] = None) -> Dict[str, Any]:
    if not HARDCOVER_API_TOKEN:
        raise ExternalSearchError(
            "Hardcover isn't configured -- add hardcover_token to config.ini (see "
            "`python BookTrackerApp.py paths`) or set HARDCOVER_API_TOKEN in the environment "
            "(get a free token at https://hardcover.app/account/api). Never put the token "
            "directly in a source file; it can delete your Hardcover account if leaked."
        )
    token = HARDCOVER_API_TOKEN
    if not token.lower().startswith("bearer "):
        token = f"Bearer {token}"
    try:
        resp = requests.post(
            _HARDCOVER_GRAPHQL_URL,
            json={"query": query, "variables": variables or {}},
            timeout=REQUEST_TIMEOUT,
            headers={
                "Authorization": token,
                "Content-Type": "application/json",
                # Hardcover's docs recommend identifying scripts with a UA.
                "User-Agent": USER_AGENT,
            },
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        # Full detail (which for some requests/urllib3 error types can
        # include request internals) goes to the server log only.
        print(f"[external_search] Hardcover request failed: {e}", file=sys.stderr)
        raise ExternalSearchError(
            f"Hardcover request failed ({type(e).__name__}). "
            "Hardcover may be temporarily unavailable -- try again in a moment."
        ) from e
    payload = resp.json()
    if payload.get("errors"):
        # Hardcover's own GraphQL error messages are safe to surface --
        # they're curated API-schema errors (e.g. "field 'foo' not found
        # on type 'books'"), not exception/stack-trace text, and the
        # README specifically documents seeing these as expected
        # behavior when Hardcover's schema drifts.
        msg = payload["errors"][0].get("message", "unknown error")
        raise ExternalSearchError(f"Hardcover API error: {msg}")
    return payload.get("data") or {}


def _parse_hardcover_search_results(raw: Any) -> List[Dict[str, Any]]:
    """Defensive parsing of the `search.results` JSON blob -- Hardcover's
    docs describe the field ("Result objects returned from Typesense")
    without pinning down the exact wrapper shape, so this accepts either
    a bare list of documents or a Typesense-style {"hits": [{"document":
    {...}}]} envelope, and tolerates `results` arriving as a JSON string
    instead of already-parsed JSON."""
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return []
    if isinstance(raw, list):
        return [d for d in raw if isinstance(d, dict)]
    if isinstance(raw, dict):
        hits = raw.get("hits")
        if isinstance(hits, list):
            out = []
            for h in hits:
                if isinstance(h, dict):
                    out.append(h.get("document", h))
            return out
        docs = raw.get("results") or raw.get("documents")
        if isinstance(docs, list):
            return [d for d in docs if isinstance(d, dict)]
    return []


def search_hardcover(title: str, author: str = "", limit: int = 12) -> List[Dict[str, Any]]:
    query = f"{title} {author}".strip() if author else title
    data = _hardcover_graphql(_HARDCOVER_SEARCH_QUERY, {"query": query, "perPage": limit})
    docs = _parse_hardcover_search_results((data.get("search") or {}).get("results"))
    out = []
    for doc in docs:
        author_names = doc.get("author_names") or []
        out.append({
            "source": "hardcover",
            "external_id": str(doc.get("id") or doc.get("slug") or ""),
            "title": doc.get("title") or "Untitled",
            "author": ", ".join(author_names) if author_names else None,
            "date": _year_to_date(doc.get("release_year")),
            "publisher": None,
            "cover_url": None,  # not in the search index -- filled in on hydrate
            "url": f"https://hardcover.app/books/{doc['slug']}" if doc.get("slug") else None,
        })
    return out


def get_hardcover_book_detail(external_id: str) -> Dict[str, Any]:
    """Full detail by numeric book id (preferred) or slug fallback."""
    try:
        book_id = int(external_id)
        data = _hardcover_graphql(_HARDCOVER_BOOK_BY_ID_QUERY, {"id": book_id})
        book = data.get("books_by_pk")
    except (TypeError, ValueError):
        data = _hardcover_graphql(_HARDCOVER_BOOK_BY_SLUG_QUERY, {"slug": external_id})
        books = data.get("books") or []
        book = books[0] if books else None

    if not book:
        raise ExternalSearchError(f"Hardcover: book {external_id!r} not found")

    authors = ", ".join(
        c["author"]["name"] for c in (book.get("contributions") or []) if c.get("author") and c["author"].get("name")
    ) or None

    isbn = publisher = language = None
    for ed in book.get("editions") or []:
        if isbn is None and (ed.get("isbn_13") or ed.get("isbn_10")):
            isbn = ed.get("isbn_13") or ed.get("isbn_10")
        if publisher is None and (ed.get("publisher") or {}).get("name"):
            publisher = ed["publisher"]["name"]
        if language is None and (ed.get("language") or {}).get("language"):
            language = ed["language"]["language"]

    series_title = series_volume = None
    book_series = book.get("book_series") or []
    if book_series:
        s = book_series[0]
        series_title = (s.get("series") or {}).get("name")
        pos = s.get("position")
        series_volume = str(pos) if pos is not None else None

    genres = None
    tags = book.get("cached_tags")
    if isinstance(tags, dict):
        genre_list = tags.get("Genre") or []
        genres = ", ".join(t.get("tag") for t in genre_list[:5] if isinstance(t, dict) and t.get("tag")) or None

    return {
        "source": "hardcover",
        "external_id": str(book.get("id")),
        "title": book.get("title") or "Untitled",
        "subtitle": book.get("subtitle"),
        "author": authors,
        "narrator": None,
        "series_title": series_title,
        "series_volume": series_volume,
        "publisher": publisher,
        "language": language,
        "runtime_minutes": None,
        "isbn": isbn,
        "cover_url": (book.get("image") or {}).get("url"),
        "date": _normalize_date(book.get("release_date")),
        "genres": genres,
        "description": _strip_html(book.get("description")),
        "url": f"https://hardcover.app/books/{book.get('slug')}" if book.get("slug") else None,
        "source_label": "hardcover",
    }


def search_books(query: str) -> List[Dict[str, Any]]:
    """Combined ebook/print search across Google Books and Open Library.
    One source failing doesn't sink the other."""
    results: List[Dict[str, Any]] = []
    for fn in (_search_google_books, _search_open_library):
        try:
            results.extend(fn(query))
        except ExternalSearchError:
            continue
    return results


def get_book_detail(source: str, external_id: str) -> Dict[str, Any]:
    if source == "hardcover":
        return get_hardcover_book_detail(external_id)
    if source == "openlibrary":
        return get_open_library_detail(external_id)
    if source == "googlebooks":
        return get_google_book_detail(external_id)
    raise ExternalSearchError(f"unknown book source: {source!r}")


# ---------------------------------------------------------------------
# Audible + Audnexus (audiobooks)
# ---------------------------------------------------------------------
# api.audible.com is Audible's own unauthenticated, undocumented but
# widely relied-upon (e.g. by Audiobookshelf's "Audible" provider)
# product-search endpoint -- used here for the search list. api.audnex.us
# is a community aggregator over the same underlying catalog, used here
# for the rich single-book detail fetch. Both are US-region by default.

_AUDIBLE_BASE = "https://api.audible.com/1.0/catalog/products"
_AUDIBLE_RESPONSE_GROUPS = "contributors,product_desc,product_extended_attrs,series,media"


def search_audiobooks(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    data = _get(_AUDIBLE_BASE, {
        "keywords": query, "num_results": limit,
        "products_sort_by": "Relevance",
        "response_groups": _AUDIBLE_RESPONSE_GROUPS,
    })
    out = []
    for p in data.get("products", []) or []:
        authors = ", ".join(a.get("name", "") for a in (p.get("authors") or []))
        images = p.get("product_images") or {}
        out.append({
            "source": "audible",
            "external_id": p.get("asin"),
            "title": p.get("title") or "Untitled",
            "author": authors or None,
            "date": _normalize_date(p.get("release_date")),
            "publisher": p.get("publisher_name"),
            "cover_url": images.get("500") or images.get("1024") or next(iter(images.values()), None),
            "url": f"https://www.audible.com/pd/{p.get('asin')}" if p.get("asin") else None,
        })
    return out


def get_audnexus_book(asin: str) -> Dict[str, Any]:
    """Rich single-audiobook detail by ASIN: narrator, runtime, genres,
    summary, and an *exact* series name + position (Audnexus/Audible
    tag series membership directly, unlike the Open Library heuristic
    used for ebook/print above)."""
    data = _get(f"https://api.audnex.us/books/{asin.strip().upper()}")
    authors = ", ".join(a.get("name", "") for a in (data.get("authors") or []))
    narrators = ", ".join(n.get("name", "") for n in (data.get("narrators") or []))
    genres = ", ".join(g.get("name", "") for g in (data.get("genres") or []))
    series = data.get("seriesPrimary") or {}
    return {
        "source": "audible",
        "external_id": data.get("asin") or asin,
        "title": data.get("title") or "Untitled",
        "subtitle": data.get("subtitle"),
        "author": authors or None,
        "narrator": narrators or None,
        "series_title": series.get("name"),
        "series_volume": series.get("position"),
        "publisher": data.get("publisherName"),
        "language": data.get("language"),
        "runtime_minutes": data.get("runtimeLengthMin"),
        "isbn": data.get("isbn"),
        "cover_url": data.get("image"),
        "date": _normalize_date(data.get("releaseDate")),
        "genres": genres or None,
        "description": _strip_html(data.get("summary")),
        "url": f"https://www.audible.com/pd/{data.get('asin') or asin}",
    }


def get_audiobook_detail(source: str, external_id: str) -> Dict[str, Any]:
    return get_audnexus_book(external_id)


# ---------------------------------------------------------------------
# Amazon (URL paste only) + generic product-URL parsing
# ---------------------------------------------------------------------

_URL_PATTERNS = [
    ("amazon", re.compile(r"amazon\.[a-z.]+/(?:[^/]+/)?(?:dp|gp/product)/([A-Z0-9]{10})", re.IGNORECASE)),
    ("audible", re.compile(r"audible\.[a-z.]+/pd/(?:[^/?]+/)?([A-Z0-9]{10})", re.IGNORECASE)),
    ("hardcover", re.compile(r"hardcover\.app/books/([a-z0-9-]+)", re.IGNORECASE)),
    ("googlebooks", re.compile(r"books\.google\.[a-z.]+/books.*[?&]id=([A-Za-z0-9_-]+)", re.IGNORECASE)),
    ("openlibrary", re.compile(r"openlibrary\.org(/works/OL\w+W)", re.IGNORECASE)),
]

# Only "amazon" ever triggers a live request to the *pasted* URL itself
# (fetch_amazon_product below) -- every other source just extracts an ID
# and looks it up against that source's own hardcoded API base URL, so
# the pasted URL's host doesn't matter for them. For amazon specifically,
# the pattern above is a substring search (re.search), not anchored to
# the actual host -- on its own that would let someone paste a URL like
# "http://internal-host/whatever?x=amazon.com/dp/B000000000" and have it
# treated as a legitimate Amazon link, at which point the raw pasted URL
# (not a reconstructed amazon.com one) gets fetched with requests.get.
# That's a server-side request forgery hole: the server can be made to
# issue a request to *any* host the caller names, including internal-
# only addresses. _is_amazon_url below closes that by checking the
# request's actual parsed host, not just whether "amazon.<tld>" appears
# somewhere in the string.
_AMAZON_HOST_RE = re.compile(r"^([a-z0-9-]+\.)*amazon\.[a-z]{2,3}(\.[a-z]{2,3})?$", re.IGNORECASE)


# Amazon storefronts "Fetch from URL" may contact. Outbound requests take
# their host from this constant tuple only (see _amazon_storefront).
_AMAZON_STOREFRONTS = (
    "amazon.com", "amazon.ca", "amazon.com.mx", "amazon.com.br", "amazon.co.uk",
    "amazon.ie", "amazon.de", "amazon.fr", "amazon.it", "amazon.es", "amazon.nl",
    "amazon.se", "amazon.pl", "amazon.com.be", "amazon.com.tr", "amazon.ae",
    "amazon.sa", "amazon.eg", "amazon.in", "amazon.co.jp", "amazon.sg",
    "amazon.com.au",
)


# Amazon product IDs: a Kindle/audio ASIN (B0...) or an ISBN-10 for print.
_AMAZON_ID_RE = re.compile(r"^[A-Z0-9]{10}$", re.IGNORECASE)


def _amazon_storefront(host: str) -> Optional[str]:
    """The matching constant from _AMAZON_STOREFRONTS for host (itself or
    any subdomain of it), or None."""
    host = (host or "").lower().rstrip(".")
    for store in _AMAZON_STOREFRONTS:
        if host == store or host.endswith("." + store):
            return store
    return None


def _is_amazon_url(url: str) -> bool:
    """True only if url is an http(s) URL whose actual host is
    amazon.<tld> (or a subdomain of it) -- not merely a URL that
    contains that text somewhere in its path or query string."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname or ""
    return bool(_AMAZON_HOST_RE.match(host))


def parse_product_url(url: str) -> Dict[str, Optional[str]]:
    """Recognize a product URL and pull out (kind, source, external_id)
    without making any network request yet. kind is 'book' or
    'audiobook'; source distinguishes which API external_id belongs to."""
    url = (url or "").strip()
    for name, pattern in _URL_PATTERNS:
        if name == "amazon" and not _is_amazon_url(url):
            # Don't even extract an ID for a string that merely contains
            # "amazon.com/dp/..." somewhere but isn't actually hosted on
            # Amazon -- see _is_amazon_url for why.
            continue
        m = pattern.search(url)
        if not m:
            continue
        ext_id = m.group(1)
        if name == "amazon":
            return {"kind": "book", "source": "amazon", "external_id": ext_id}
        if name == "audible":
            return {"kind": "audiobook", "source": "audible", "external_id": ext_id}
        if name == "hardcover":
            return {"kind": "book", "source": "hardcover", "external_id": ext_id}
        if name == "googlebooks":
            return {"kind": "book", "source": "googlebooks", "external_id": ext_id}
        if name == "openlibrary":
            return {"kind": "book", "source": "openlibrary", "external_id": ext_id}
    if looks_like_asin(url):
        return {"kind": "audiobook", "source": "audible", "external_id": url.strip().upper()}
    return {"kind": None, "source": None, "external_id": None}


_OG_TAG_RE = re.compile(
    r'<meta[^>]+property=["\'](og:title|og:image|books:author|book:author)["\'][^>]+content=["\']([^"\']+)["\']', re.IGNORECASE)
_META_NAME_RE = re.compile(
    r'<meta[^>]+name=["\'](author|book:author)["\'][^>]+content=["\']([^"\']+)["\']', re.IGNORECASE)
_TITLE_TAG_RE = re.compile(r"<title>([^<]+)</title>", re.IGNORECASE)
_PRODUCT_TITLE_RE = re.compile(r"""id=["']productTitle["'][^>]*>([^<]+?)<""", re.IGNORECASE)
_BYLINE_RE = re.compile(r"""id=["']bylineInfo["'][^>]*>(.*?)</div>""", re.IGNORECASE | re.DOTALL)
_BYLINE_LINK_RE = re.compile(r'>\s*([^<]{2,80}?)\s*</a>', re.IGNORECASE)
# data-a-dynamic-image holds a JSON object (double-quoted keys), so it's
# wrapped in single quotes on some Amazon page templates and in double
# quotes with the internal quotes &quot;-escaped on others -- try both.
_DYNAMIC_IMAGE_SQ_RE = re.compile(r"data-a-dynamic-image='([^']+)'", re.IGNORECASE)
_DYNAMIC_IMAGE_DQ_RE = re.compile(r'data-a-dynamic-image="([^"]+)"', re.IGNORECASE)
_LANDING_IMG_SRC_RE = re.compile(r"""id=["'](?:landingImage|imgBlkFront)["'][^>]+src=["']([^"']+)["']""", re.IGNORECASE)
_SERIES_LINK_RE = re.compile(r"""id=["']seriesTitleLink["'][^>]*>([^<]+?)<""", re.IGNORECASE)
_SERIES_BOOK_OF_N_RE = re.compile(r"Book\s+(\d+(?:\.\d+)?)\s+of\s+\d+\s*:?\s*(.+)", re.IGNORECASE)
# "Publisher : Simon & Schuster (April 1, 2020)" / classic detail-bullet
# and the newer detailBullets_feature_div table, both label: value pairs.
# Both patterns previously had \s* immediately bordering the lazy
# content groups on both sides -- since \s* and a lazy "not this
# delimiter" group can match the same whitespace characters, that's
# ambiguous in the way that causes worst-case matching time to grow
# with input length. Dropping those (both groups already get
# .strip()'d by the caller below, so nothing is lost) removes most of
# it, but [\s:]* directly after the label group is the same shape all
# over again (both it and the group can match plain whitespace) --
# bounding it to a small fixed max closes that off too, since a
# label's trailing ": " separator is never more than a couple of
# characters in real markup.
_DETAIL_BULLET_RE = re.compile(
    r'<span class="a-text-bold">([^:<]+?)[\s:]{0,5}</span>\s*<span[^>]*>([^<]+?)</span>', re.IGNORECASE)
_DETAIL_TABLE_RE = re.compile(
    r'<th[^>]*>([^<]+?)</th>\s*<td[^>]*>([^<]+?)</td>', re.IGNORECASE)
_ISBN13_RE = re.compile(r"\b97[89][\d-]{10,17}\b")
_BOT_CHECK_MARKERS = (
    "Enter the characters you see below", "api-services-support@amazon.com",
    "Robot Check", "Sorry, we just need to make sure you're not a robot",
    "To discuss automated access to Amazon data",
)
# Common Amazon title-page suffixes/prefixes that aren't part of the
# actual book title.
_AMAZON_TITLE_SUFFIX_RE = re.compile(
    r"\s*[-:(]\s*(Kindle Edition|Kindle eBook|Kindle|Audible Audio Edition|Audiobook|"
    # Amazon.com.* was previously unbounded (.*), which sits directly
    # against the \s*$ that follows it -- since '.' also matches
    # whitespace, that pair of adjacent quantifiers is exactly the
    # ambiguous shape that makes worst-case matching time scale with
    # input length. Capping it at a fixed max length removes that: the
    # trailing junk this branch matches ("Amazon.com: Books" and
    # similar) is never long, so nothing legitimate is lost.
    r"Paperback|Hardcover|Mass Market Paperback|Amazon\.com.{0,60})?\s*$", re.IGNORECASE)
_AMAZON_TITLE_PREFIX_RE = re.compile(r"^Amazon\.[a-z.]+\s*:\s*", re.IGNORECASE)

# Titles are always short in practice; bounding defensively here (same
# rationale as _MAX_SERIES_TEXT_CHARS above) keeps worst-case regex
# cost constant even if a page ever hands back something pathological.
_MAX_TITLE_CHARS = 500


def _clean_amazon_title(title: Optional[str]) -> Optional[str]:
    if not title:
        return None
    title = _html.unescape(title).strip()[:_MAX_TITLE_CHARS]
    title = _AMAZON_TITLE_PREFIX_RE.sub("", title).strip()
    # Repeated pass: Amazon sometimes stacks more than one suffix, e.g.
    # "Foo - Kindle Edition: Amazon.com: Books".
    for _ in range(3):
        new = _AMAZON_TITLE_SUFFIX_RE.sub("", title).strip()
        if new == title:
            break
        title = new
    return title or None


def _parse_amazon_detail_bullets(html_text: str) -> Dict[str, Optional[str]]:
    """Amazon's 'Product details' section, in either of its two common
    markups (a bullet list of bold labels, or a two-column table)."""
    pairs: Dict[str, str] = {}
    for label, value in _DETAIL_BULLET_RE.findall(html_text):
        clean_value = re.sub(r"^[:\s]+", "", _html.unescape(value)).strip()
        pairs.setdefault(_html.unescape(label).strip().lower(), clean_value)
    for label, value in _DETAIL_TABLE_RE.findall(html_text):
        clean_value = re.sub(r"^[:\s]+", "", _html.unescape(value)).strip()
        pairs.setdefault(_html.unescape(label).strip().lower(), clean_value)

    publisher = None
    language = None
    isbn = None
    date = None
    for key, value in pairs.items():
        if "publisher" in key and publisher is None:
            # "Simon & Schuster (April 1, 2020)" -> just the name.
            publisher = re.sub(r"\s*\([^)]*\)\s*$", "", value).strip() or None
        elif "language" in key and language is None:
            language = value
        elif ("isbn-13" in key or "isbn13" in key) and isbn is None:
            isbn = re.sub(r"[^0-9Xx-]", "", value) or None
        elif "isbn" in key and isbn is None:
            isbn = re.sub(r"[^0-9Xx-]", "", value) or None
        elif ("publication date" in key or "release date" in key or key == "pub date") and date is None:
            date = _parse_loose_date(value)
    if isbn is None:
        m = _ISBN13_RE.search(html_text)
        if m:
            isbn = m.group(0)
    if date is None and publisher:
        # Fall back to a date hiding inside the publisher bullet itself,
        # e.g. "Publisher : Ace (June 28, 2005)".
        date = _parse_loose_date(pairs.get("publisher", ""))
    return {"publisher": publisher, "language": language, "isbn": isbn, "date": date}


def fetch_amazon_product(url: str, asin: str) -> Dict[str, Any]:
    """Best-effort scrape of a public Amazon product page. Amazon
    actively blocks a lot of non-browser traffic and its markup varies
    by product type (ebook/print/audiobook page templates differ) and
    changes over time, so this tries several independent extraction
    strategies per field and takes whichever succeeds first -- but it
    can still legitimately come back partial or empty. Callers should
    keep the ASIN/URL either way and let the user fill in the rest."""
    result = {
        "source": "amazon", "external_id": asin, "title": None, "author": None,
        "publisher": None, "language": None, "isbn": None, "date": None, "series_title": None,
        "series_volume": None, "cover_url": None, "url": url, "warning": None,
    }
    if not _is_amazon_url(url):
        # Defense in depth: parse_product_url already checks this before
        # ever calling here, but this function makes a live outbound
        # request with a caller-supplied URL, so it re-checks on its own
        # rather than trusting callers not to regress that check later.
        result["warning"] = "That doesn't look like an Amazon product URL; fill in details manually."
        return result
    try:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        # The request URL is never the pasted URL itself: it's rebuilt as
        # https://www.<storefront>/dp/<ASIN>, where <storefront> is taken
        # from the constant _AMAZON_STOREFRONTS table and the ASIN has
        # been validated as 10 alphanumerics. Redirects are followed by
        # hand and rebuilt the same way, so no hop can reach a host
        # outside that table (e.g. an internal address).
        store = _amazon_storefront(urlparse(url).hostname or "")
        if store is None or not _AMAZON_ID_RE.match(asin or ""):
            result["warning"] = "Unsupported Amazon store or product ID; fill in details manually."
            return result
        next_url = f"https://www.{store}/dp/{asin.upper()}"
        for _hop in range(5):
            resp = requests.get(next_url, timeout=REQUEST_TIMEOUT, headers=headers,
                                allow_redirects=False)
            if resp.is_redirect or resp.is_permanent_redirect:
                loc = urlparse(urljoin(next_url, resp.headers.get("Location", "")))
                hop_store = _amazon_storefront(loc.hostname or "")
                if hop_store is None or loc.scheme not in ("http", "https"):
                    result["warning"] = "Amazon redirected somewhere unexpected; fill in details manually."
                    return result
                next_url = f"https://www.{hop_store}{loc.path or '/'}" + (f"?{loc.query}" if loc.query else "")
                continue
            break
        else:
            result["warning"] = "Too many redirects from Amazon; fill in details manually."
            return result
        resp.raise_for_status()
        html_text = resp.text[:MAX_SCRAPED_HTML_CHARS]
        # Normalize non-breaking-space entities to regular spaces before
        # any regex runs -- Amazon's label:value bullets/table cells
        # commonly separate label from value with "&nbsp;:&nbsp;" rather
        # than a literal space, which \s* alone won't match.
        html_text = re.sub(r"&nbsp;|&#160;|&#xa0;", " ", html_text, flags=re.IGNORECASE)
    except requests.RequestException:
        result["warning"] = "Couldn't fetch the Amazon page; fill in details manually."
        return result

    if any(marker in html_text for marker in _BOT_CHECK_MARKERS):
        result["warning"] = ("Amazon showed a bot-check page instead of the product page -- "
                              "this happens sporadically with automated requests. Try again in "
                              "a moment, or fill in details manually.")
        return result

    og = {}
    for prop, content in _OG_TAG_RE.findall(html_text):
        og.setdefault(prop, _html.unescape(content))
    for name, content in _META_NAME_RE.findall(html_text):
        og.setdefault(name, _html.unescape(content))

    title = None
    m = _PRODUCT_TITLE_RE.search(html_text)
    if m:
        title = m.group(1)
    if not title:
        title = og.get("og:title")
    if not title:
        m = _TITLE_TAG_RE.search(html_text)
        if m:
            title = m.group(1)
    title = _clean_amazon_title(title)

    author = og.get("books:author") or og.get("book:author") or og.get("author")
    if not author:
        m = _BYLINE_RE.search(html_text)
        if m:
            byline_html = m.group(1)
            # Cut off at the "Format:" row if present -- everything after
            # that is edition/format links, not author names.
            fmt_cut = re.search(r'a-color-secondary["\']?\s*>\s*Format', byline_html, re.IGNORECASE)
            if fmt_cut:
                byline_html = byline_html[:fmt_cut.start()]
            names = _BYLINE_LINK_RE.findall(byline_html)
            names = [_html.unescape(n).strip() for n in names if _html.unescape(n).strip()]
            if names:
                author = ", ".join(dict.fromkeys(names))  # de-dupe, keep order

    cover_url = None
    m = _DYNAMIC_IMAGE_SQ_RE.search(html_text) or _DYNAMIC_IMAGE_DQ_RE.search(html_text)
    if m:
        try:
            import json as _json
            urls = list(_json.loads(_html.unescape(m.group(1))).keys())
            if urls:
                cover_url = urls[0]
        except (ValueError, TypeError):
            pass
    if not cover_url:
        m = _LANDING_IMG_SRC_RE.search(html_text)
        if m:
            cover_url = m.group(1)
    if not cover_url:
        cover_url = og.get("og:image")

    series_title = series_volume = None
    m = _SERIES_LINK_RE.search(html_text)
    if m:
        raw = _html.unescape(m.group(1)).strip()
        m2 = _SERIES_BOOK_OF_N_RE.match(raw)
        if m2:
            series_volume, series_title = m2.group(1), m2.group(2).strip()
        else:
            series_title, series_volume = _extract_series_from_text(raw)
    if not series_title:
        series_title, series_volume = _extract_series_from_text(title)

    bullets = _parse_amazon_detail_bullets(html_text)

    result.update({
        "title": title,
        "author": author,
        "publisher": bullets["publisher"],
        "language": bullets["language"],
        "isbn": bullets["isbn"],
        "date": bullets["date"],
        "series_title": series_title,
        "series_volume": series_volume,
        "cover_url": cover_url,
    })
    if not title:
        result["warning"] = "Couldn't find the product title -- Amazon may have blocked this request or changed its page layout. Fill in details manually."
    elif not author and not bullets["publisher"]:
        result["warning"] = "Only got partial data from this Amazon page (title/cover) -- fill in the rest manually."
    return result


_ENRICHABLE_FIELDS = ("publisher", "date", "isbn", "language", "genres",
                       "description", "series_title", "series_volume", "cover_url")


def _enrich_missing_fields(detail: Dict[str, Any]) -> Dict[str, Any]:
    """Amazon's page scrape often can't get everything (blocked field,
    changed markup, a field Amazon just doesn't show on that page type).
    Since we usually do have a title (and often an author) at this point,
    use those to look the book up on Google Books, then Open Library if
    still missing anything, and fill in only the fields the scrape didn't
    already get -- never overwrite something Amazon's own page gave us.
    Best-effort and silent: a failure here just means the Amazon-only
    result stands, not a hard error."""
    title = (detail.get("title") or "").strip()
    if not title:
        return detail
    author = (detail.get("author") or "").strip()
    missing = [f for f in _ENRICHABLE_FIELDS if not detail.get(f)]
    if not missing:
        return detail

    filled_from = None
    try:
        candidates = search_google_books(title, author, limit=3)
        if candidates:
            gb = get_google_book_detail(candidates[0]["external_id"])
            for f in missing:
                if gb.get(f):
                    detail[f] = gb[f]
            if not detail.get("author") and gb.get("author"):
                detail["author"] = gb["author"]
            filled_from = "googlebooks"
    except ExternalSearchError:
        pass

    missing = [f for f in _ENRICHABLE_FIELDS if not detail.get(f)]
    if missing:
        try:
            candidates = search_open_library(title, author, limit=3)
            if candidates:
                ol = get_open_library_detail(candidates[0]["external_id"])
                for f in missing:
                    if ol.get(f):
                        detail[f] = ol[f]
                if not detail.get("author") and ol.get("author"):
                    detail["author"] = ol["author"]
                filled_from = f"{filled_from}+openlibrary" if filled_from else "openlibrary"
        except ExternalSearchError:
            pass

    if filled_from:
        detail["source_label"] = f"amazon+{filled_from}"
    return detail


def fetch_by_url(url: str) -> Dict[str, Any]:
    """Dispatch a pasted product URL to the right source and return a
    hydrated detail dict, same shape as get_book_detail/get_audiobook_detail."""
    parsed = parse_product_url(url)
    if not parsed["kind"]:
        raise ExternalSearchError(
            "Couldn't recognize that URL. Supported: amazon.com/dp/ or /gp/product/, "
            "audible.com/pd/, hardcover.app/books/, books.google.com/books?id=, "
            "openlibrary.org/works/, or a bare ASIN."
        )
    if parsed["source"] == "amazon":
        detail = fetch_amazon_product(url, parsed["external_id"])
        detail = _enrich_missing_fields(detail)
        detail["kind"] = "book"
        return detail
    if parsed["source"] == "audible":
        detail = get_audnexus_book(parsed["external_id"])
        detail["kind"] = "audiobook"
        return detail
    detail = get_book_detail(parsed["source"], parsed["external_id"])
    detail["kind"] = "book"
    return detail
