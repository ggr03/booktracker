# Book Tracker

A small local web app (not a static HTML generator) backed by SQLite. It
tracks two kinds of things in one place:

- **Light novel release schedules**, synced from
  [LNRelease](https://github.com/LNRelease/lnrelease.github.io)'s
  `books.csv` feed.
- **Anything else you've read or are reading** — audiobooks, ebooks, or
  print books from any publisher — added yourself via the **➕ Add Book**
  page, which searches Google Books, Audible, and Audnexus, or accepts a
  pasted product URL (Amazon, Audible, Google Books, or Open Library).

Everything you star — synced or manually added — lives together on the
**★ My Starred** page, grouped by series, with a reading-status tracker
(To-Read / Reading / Read / Dropped).

Separately, the **📚 My Books** page lets you import a Goodreads CSV
export as a completely separate list. Only Title, Author, Publisher,
Year Published, and Date Read are imported; rows with a Date Read are
grouped under **Book Read**, rows without under **Unsorted**, and each
row's Date Read is editable inline. My Books data never mixes with
★ My Starred or the LNRelease year pages.

Book Tracker was previously called **LNRelease**; if you're upgrading an
existing install, see [Upgrading from LNRelease](#upgrading-from-lnrelease)
below — your data carries over automatically.

## Versioning

`YYYY.MM.DD-NN` — the release date, plus a two-digit counter that only
increments if more than one release ships the same day. The current
version lives in one place, `version.py`, so bumping it for a new release
is a one-line change and every page picks it up automatically (see the
small `v2026.11.24-01`-style tag in the header on every page).

### Changelog

- **2026.11.24-01** — Cross-platform release: Debian/Ubuntu/MX,
  RHEL/Rocky/Alma/Fedora, macOS, and Windows.
  - **Minimum Python is now 3.11** (was 3.9; 3.9 and 3.10 no longer get
    security fixes). Tested on 3.11 through 3.14.
  - New `python app.py install-service` sets up autostart for each OS
    (systemd user unit, XDG autostart when systemd isn't running,
    a macOS launchd agent, or a Windows Startup shortcut). `install.sh`
    (Linux/macOS) and `install.ps1` (Windows) wrap it.
  - The daily LNRelease sync now runs inside the server, so the separate
    `booktracker-sync.timer` is gone (the installer removes the old one).
  - API tokens move to a private `config.ini` in your per-user config
    folder; they're never kept in the app folder or a unit file again.
    Reinstalling moves an existing token out of the old unit
    automatically.
  - New installs keep the database in the per-user data folder; existing
    installs keep using `booktracker.db` next to `app.py`.
  - Security: the server listens on `127.0.0.1` unless you pass `--lan`;
    cross-site POSTs (CSRF) and unknown `Host` names (DNS rebinding) are
    rejected; Amazon URL fetches re-check every redirect.
  - Served by Waitress instead of Flask's development server. The DB
    schema check runs once per process instead of on every request.
  - New `paths` and `init-config` commands, plus a cross-platform smoke
    test suite and a CI run on Ubuntu, Rocky Linux, macOS, and Windows.
- **2026.08.11-01** — Added **📚 My Books**, a new page (linked from every
  header, next to ★ My Starred) for importing a Goodreads-format CSV
  export. Only five fields are kept — Title, Author, Publisher,
  Year Published, Date Read — and every other Goodreads column is
  ignored. Rows with a Date Read land under **Book Read**; rows
  without one land under **Unsorted**. Each row's Date Read is
  editable inline (native `<input type="date">`), and setting/clearing
  it immediately moves the book between the two groups. A search box
  filters across both groups by title/author/publisher. This data
  lives in its own `imported_books` SQLite table, fully separate from
  LNRelease-synced and manually-added books (duplicates between My
  Books and My Starred are expected and allowed). Re-importing the
  same CSV is idempotent: duplicate rows are silently skipped.
  Security-wise: the import endpoint is capped at a 20 MB / 50,000-row
  CSV with a 25 MB global request-body cap, all rendering goes through
  the same `escapeHtml`/`_safe_json_for_script` escaping as the rest
  of the app, upload/import errors return fixed human-written messages
  (never raw exception text), and the CSV parser uses only bounded
  regexes.
- **2026.08.10-01** — Security pass ahead of making this repo public:
  fixed an SSRF hole in the Amazon-URL-fetch feature (strict hostname
  validation, not just a substring check), 12 ReDoS-shaped regexes
  (ambiguous adjacent quantifiers replaced with negated character
  classes, plus defensive input-length caps), stack-trace/URL exposure
  in external-search error responses (curated messages only, full
  detail logged server-side), and a stored-XSS gap where book metadata
  (title, author, etc.) could break out of a `<script>` tag or inject
  raw HTML via unescaped client-side rendering — both now escaped and
  verified against real exploit payloads. New [Security](#security)
  section documents all of this in one place.
- **2026.08.09-02** — Added an Author column to the expanded accordion
  table (★ My Starred, and the year page's status-filter view), between
  Title and Publisher: Date - Vol - Title - Author - Publisher - Format
  - Status.
- **2026.08.09-01** — Three ★ My Starred / edit-popup improvements:
  - A volume's title now always shows in the accordion, even when it's
    identical to the series name above it (common for light novels,
    which often don't give each volume its own title) — a blank cell
    read as missing data; a repeated title reads as confirmed data.
  - A manually-added book with no series set no longer shows a stray
    volume number (it isn't really "volume 1 of 1", it's just a book).
    Manually-added *series* are unaffected — their volume numbers still
    show as before.
  - The Edit Book popup can now be dragged by its header to move it out
    of the way, so you can see what's behind it. Position resets to
    centered every time you reopen it, and dragging is clamped so the
    dialog can't be pulled fully off-screen.
- **2026.08.08-01** — Two editing enhancements:
  - The click-to-edit popup now has a re-search bar at the top (Hardcover /
    Open Library / Audible) so you can refresh or correct a manually-added
    book's metadata without deleting and re-adding it. Picking a result
    fills in the same field grid below; nothing is saved until you click
    Save.
  - Search results that match a book you added yourself are now
    click-to-edit everywhere: the cross-year search on the year page, a
    new "🔍 Search your library" box on the Add page, and each book's
    title in the ★ My Starred accordion. All three mark manually-added
    matches with a "✎ edit" hint so it's clear before you click.
- **2026.08.07-02** — Added Hardcover as a search provider (GraphQL,
  `api.hardcover.app`) and made it the default. Requires a personal
  `HARDCOVER_API_TOKEN` (free, see [Setting up
  Hardcover](#setting-up-hardcover)) — the token is never committed to
  this repo or sent to the browser, only used server-side. Also added
  Hardcover URL recognition (`hardcover.app/books/...`) to "Fetch from
  URL", and a config-status check so the Add page shows a clear hint
  instead of an error if the token isn't set yet.
- **2026.08.07-01** — Fixed three more issues: (1) Google Books 429
  (rate-limit) errors now get a couple of short-backoff retries and a
  clear message pointing at `GOOGLE_BOOKS_API_KEY`; added Open Library as
  a full structured-search provider option too, as another working
  source if Google Books is rate-limited. (2) Amazon URL fetch was
  silently missing Publisher/Publication date because Amazon's
  label:value markup separates them with `&nbsp;` entities, not literal
  spaces, which the parser's whitespace matching didn't account for --
  fixed, plus added a Google Books/Open Library enrichment fallback that
  fills in whatever the Amazon scrape still couldn't get (never
  overwriting fields Amazon's page did provide). (3) The ★ My Starred
  accordion was only showing series name + volume number for each row,
  not each book's own title -- added a Title column so e.g. individual
  Codex Alera volumes ("Furies of Calderon", "Academ's Fury", ...) show
  their own names, not just "Codex Alera" repeated with a volume number.
- **2026.08.06-01** — Fixed three Add-a-Book bugs: (1) the Provider
  dropdown now actually restricts search to that source — selecting
  "Google Books" no longer silently blends in unrelated Open Library
  results, which was causing wrong-author mismatches; Google Books
  search also now uses structured `intitle:`/`inauthor:` queries instead
  of one blended string. (2) Series/volume detection recognizes several
  more common phrasings ("Book 2 of X", "X #2", "X, Book 2", plus
  checking the title as well as the subtitle). (3) Amazon URL fetch now
  tries several independent extraction strategies per field (product
  title element, byline links, the dynamic-image cover data, the
  product-details table/bullets, and a series link) instead of relying
  on Open Graph tags alone, and explicitly detects & reports Amazon's
  bot-check page instead of returning silently-empty fields.
- **2026.08.05-01** — Renamed from LNRelease to Book Tracker; added the
  Add-a-Book page, click-to-edit, and series grouping by slug.


## Requirements

- **Python 3.11 or newer** (tested up to 3.14), on Windows, macOS, or
  Linux. The app is pure Python (Flask + Waitress + SQLite), with nothing
  platform-specific. 3.11 is the oldest Python release that still gets
  security fixes.
- The packages listed in `requirements.txt` (Flask, requests, Waitress) — installed
  with `pip` in the setup steps below.
- **A free Hardcover API token, if you want search to work out of the
  box.** Hardcover is the default (and richest) search provider on the
  ➕ Add Book page, and it **requires a personal API token** — the app
  will not fetch Hardcover results without one. See [Getting a
  Hardcover API token](#getting-a-hardcover-api-token) just below.
  You can skip this and the app still runs fine — Google Books, Open
  Library, and Audible/Audnexus search all work with **no key at
  all** — you'll just see a "Hardcover isn't configured" hint instead
  of Hardcover results until you add one.
- *(Optional)* A free Google Books API key — only needed if you search
  Google Books enough to hit its unauthenticated rate limit. See
  [Getting a Google Books API key](#getting-a-google-books-api-key-optional)
  below.

No API key is ever required just to browse and star LNRelease release
data (the `sync` / calendar / ★ My Starred pages) or to use 📚 My Books —
keys only matter for the ➕ Add Book search.

### Getting a Hardcover API token

1. Create a free account and go to
   [hardcover.app/account/api](https://hardcover.app/account/api).
2. Copy your token (it's a long `Bearer eyJ...` string).
3. Set it as the `HARDCOVER_API_TOKEN` environment variable before you
   start the server — see the platform-specific commands under
   [Setup](#setup) below, or the full details (including the security
   note about what this token can do) under [Setting up
   Hardcover](#setting-up-hardcover) further down.

**Never commit this token to git, paste it into a `.py` file, or share
it in a screenshot** — treat it like a password. It only ever needs to
live in an environment variable on your own machine.

### Getting a Google Books API key (optional)

1. Create a project in the [Google Cloud
   Console](https://console.cloud.google.com/), enable the "Books API",
   then create an API key under **APIs & Services → Credentials**.
2. Set it as the `GOOGLE_BOOKS_API_KEY` environment variable, the same
   way as `HARDCOVER_API_TOKEN` above.

Most people will never need this — it's just a fallback for Google's
unauthenticated rate limit.

## Setup

Get the code (`git clone https://github.com/ggr03/booktracker`, or
download and extract the ZIP), open a terminal in the `booktracker` folder, and run the installer
for your OS. Each installer does the same five things: finds Python 3.11+,
creates `venv/`, installs dependencies, creates a private `config.ini`,
runs the first sync, and sets the app to start automatically when you
log in.

Afterwards, open **http://127.0.0.1:7077**.

### Debian, Ubuntu, MX Linux, Mint

```bash
sudo apt install python3 python3-venv
./install.sh
```

On MX Linux this works with either init system: systemd boots get a
systemd user service, and SysVinit boots get a desktop autostart entry.

### RHEL, Rocky, AlmaLinux, CentOS Stream, Fedora

```bash
sudo dnf install python3.12 python3.12-pip   # RHEL/Rocky/Alma 8 and 9
sudo dnf install python3 python3-pip         # RHEL 10 and Fedora
./install.sh
```

The default `python3` on RHEL 8 and 9 (3.6 and 3.9) is too old. The
extra `python3.12` package installs alongside it without replacing it,
and the installer finds it automatically. If you use `--lan`, the
installer prints the `firewall-cmd` command that opens the port.

### macOS

```bash
brew install python
./install.sh
```

You can use the installer from python.org instead of Homebrew. The
`python3` that comes with Xcode Command Line Tools is 3.9, which is too
old. The app runs as a launchd agent. Logs are in
`~/Library/Logs/Book Tracker/`.

### Windows 10 / 11

Install Python 3.11+ from python.org (tick **Add python.exe to PATH**), or
run `winget install Python.Python.3.14`. Then, in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

The server runs in the background with no console window, from a
shortcut in your Startup folder. No admin rights are needed. Logs are in
`%LOCALAPPDATA%\BookTracker\logs\`.

### Network access (optional)

By default only this computer can open the app. Add `--lan` to the
installer to serve it on your network too. Read
[Network access](#network-access) first, because the app has no login.

### Running it by hand, without autostart

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt        # Windows: venv\Scripts\pip
venv/bin/python app.py serve                     # Windows: venv\Scripts\python app.py serve
```

### Uninstalling

Run `./uninstall.sh` on Linux or macOS, or `.\uninstall.ps1` on Windows.
This removes only the autostart entry. Your database, `config.ini`, and
the app folder stay where they are.

## Where your files live

Run `python app.py paths` to print the exact locations on your machine.

| | Linux | macOS | Windows |
|---|---|---|---|
| `config.ini` | `~/.config/booktracker/` | `~/Library/Application Support/Book Tracker/` | `%APPDATA%\BookTracker\` |
| Database | `~/.local/share/booktracker/` | `~/Library/Application Support/Book Tracker/` | `%LOCALAPPDATA%\BookTracker\` |

If `booktracker.db` (or an old `lnrelease.db`) already sits next to
`app.py`, it keeps being used in place. To move it into the standard
folder, stop the app, move the file there, and start the app again.
You can also point anywhere you like with `--db`, `BOOKTRACKER_DB`, or
`[database] path` in `config.ini`.

## Configuration reference

All settings are in `config.ini`. An environment variable with the same
meaning overrides the file.

| Setting | Env var | Default |
|---|---|---|
| `[api] hardcover_token` | `HARDCOVER_API_TOKEN` | *(empty)* |
| `[api] google_books_key` | `GOOGLE_BOOKS_API_KEY` | *(empty)* |
| `[server] host` | `BOOKTRACKER_HOST` | `127.0.0.1` |
| `[server] port` | `BOOKTRACKER_PORT` | `7077` |
| `[server] allowed_hosts` | `BOOKTRACKER_ALLOWED_HOSTS` | *(empty)* |
| `[sync] auto_sync` | `BOOKTRACKER_AUTO_SYNC` | `true` |
| `[sync] interval_hours` | `BOOKTRACKER_SYNC_HOURS` | `24` |
| `[database] path` | `BOOKTRACKER_DB` | see above |

## Usage

If you used the installer, the server is already running and you don't
need any of this. To run things by hand, use the venv's Python
(`venv/bin/python` on Linux/macOS, `venv\Scripts\python` on Windows):

```
# 1. Pull the latest release data from LNRelease's books.csv into the DB.
#    Safe to re-run any time -- only new/changed rows are written.
python app.py sync

# 2. Start the local server.
python app.py serve
# -> http://127.0.0.1:7077  (add --lan to also serve on your network)

# Show where the DB, config.ini and logs live on this OS:
python app.py paths

# Print the version and exit:
python app.py --version
```

Open that URL in a browser. It redirects to the most recent year with data.

While the server is running it re-syncs LNRelease data on its own once a
day (`[sync]` in `config.ini`; turn it off with `--no-auto-sync`). Running
`python app.py sync` by hand also works any time. Syncing is cheap and
safe to repeat: a sync with nothing new writes zero rows. Books you added
yourself on the Add Book page are never touched, because sync only
writes LNRelease rows.

## Adding a book yourself

The **➕ Add Book** page (its own page, not a popup — linked from every
other page's header) has two ways to find something:

**Search.** Pick a provider, type a title/author (or an ASIN), hit
Search, then click a result to pull its full details into the form below:

| Provider | What it searches | Notes |
|---|---|---|
| Hardcover *(default)* | Title/author keyword search, GraphQL | **Requires a free personal API token.** Get one at [hardcover.app/account/api](https://hardcover.app/account/api), then set `HARDCOVER_API_TOKEN` in the environment before starting the server — see [Setting up Hardcover](#setting-up-hardcover) below. Without it, this provider returns a clear "not configured" message rather than failing silently. |
| Google Books | Title/author keyword search | No API key needed for light use; set `GOOGLE_BOOKS_API_KEY` in the environment if you hit Google's unauthenticated rate limit. |
| Open Library | Title/author keyword search | No API key needed. |
| Audible | Title/author keyword search | Unauthenticated public catalog-search endpoint — the same one tools like Audiobookshelf use. |
| Audnexus | **ASIN only**, no keyword search | Audnexus's public API doesn't support title search — type or paste an exact ASIN and it returns the full rich record directly (narrator, runtime, genres, summary, exact series + position). |
| Amazon | **Not searchable** | Amazon has no public product-catalog API. Use "Fetch from URL" instead. |

### Setting up Hardcover

Hardcover is the default search provider — it's the richest source here
(ratings-informed matching, exact series + position, genres, description,
cover, all in one request) and it's what most people will want most of the
time. It needs a personal API token, which is **not** included in this
repo and should never be committed to one:

1. Go to [hardcover.app/account/api](https://hardcover.app/account/api)
   and copy your token (it's a long `Bearer eyJ...` string).
2. Put it in your private `config.ini` (`python app.py paths` shows
   where it is, and `python app.py init-config` creates it). Don't paste
   it into any `.py` file:
   ```ini
   [api]
   hardcover_token = eyJhbGciOi...   # with or without the "Bearer " prefix
   ```
   The `HARDCOVER_API_TOKEN` environment variable also works and
   overrides the file. On Linux and macOS, `config.ini` is created
   readable only by your account (mode 600). Older installs that kept the
   token in `booktracker.service` have it moved here automatically when
   you re-run the installer.
3. Restart the app. The Add page will stop showing the "Hardcover isn't
   configured" hint once it picks up the token.

A few things worth knowing, straight from Hardcover's own docs:
- **This token can delete your Hardcover account if someone else gets
  it.** Treat it like a password — environment variable or a secrets
  manager, never a source file, a commit, or a screenshot you share.
- It expires automatically after 1 year (and all tokens reset annually
  on January 1st regardless).
- Hardcover's API is explicitly beta ("heavily in flux") and rate-limited
  to 60 requests/minute — if a query breaks because a field got renamed
  upstream, the error you'll see is Hardcover's own GraphQL error message
  (e.g. `field 'foo' not found on type 'books'`), not a silent wrong
  answer, so it should be obvious when that's happened.
- Every Hardcover call in this app happens server-side (Flask calling
  out via `requests`) — the token is never sent to, or exposed in, the
  browser. That's a hard requirement of Hardcover's API, not just good
  practice: their docs are explicit that browser-side calls aren't
  supported.

**Fetch from URL.** Paste a product page URL and hit "Fetch from URL":

- `amazon.com/dp/…` or `amazon.com/gp/product/…` — best-effort scrape of
  the public page (title, author, publisher, language, ISBN, cover, and
  series name/number where Amazon's own "Book N of M: Series" link is
  present). Amazon actively blocks a lot of
  non-browser traffic, so this can come back partial or empty; when it
  does, the ASIN is still captured and you fill in the rest by hand.
- `audible.com/pd/…` (or a bare ASIN) — full rich detail via Audnexus.
- `books.google.com/books?id=…` — full Google Books detail.
- `openlibrary.org/works/OL…W` — full Open Library detail.

Either way you land on an editable **Details** form (same fields as the
click-to-edit modal, see below) — fix anything the lookup got wrong,
toggle which format(s) you're tracking (Ebook / Print / Audiobook, any
combination), and hit **+ Add to My Starred**.

### How series grouping works

There's no separate "series" table — grouping is just a `slug`, exactly
like an LNRelease series. When you add a book, the slug is built from its
**Series** field + **Author** (normalized and hashed together, prefixed
`manual-` so it can never collide with an LNRelease slug). Add "The Ruins
of Gorlan" and later "The Burning Bridge" with the same Series
("Ranger's Apprentice") and Author ("John Flanagan"), and they land under
the same slug automatically — which is what makes them show up as one
grouped entry on ★ My Starred instead of four separate single-book
entries.

The **Series** field is usually prefilled for you (Audnexus/Audible tag
series membership exactly; Google Books and Open Library are filled in on
a best-effort basis from subtitle/edition text and can be wrong or
missing) — but it's a plain editable text field, so if a lookup gets it
wrong, or a source doesn't provide it at all, just type the series name
yourself before hitting Add. Keep it consistent across a series' volumes
and grouping just works.

### Editing or removing a book you added

Click any book — a row in ★ My Starred, a row on the year page, or an
item in the "Your Book Tracker items" list at the bottom of the Add page
— to open the same Details form pre-filled with its current metadata.
Save applies your changes immediately; Remove deletes it entirely (only
works on books *you* added — unstar an LNRelease title instead of trying
to delete it, since that data comes from the synced feed).

### Filtering by status

The year page's "All statuses" dropdown filters *every* tracked book —
LNRelease-synced or manually added — down to whichever reading status you
pick (To-Read / Reading / Read / Dropped), replacing the calendar table
with the same accordion view used on ★ My Starred.

Amazon and Goodreads' catalog data aren't both used the same way: Amazon
has no public API at all (Product Advertising API requires an active
affiliate account with sales volume, so it's URL-fetch-only here), and
Goodreads closed its public API to new registrations in December 2020, so
it isn't used at all.

All of this runs against free, rate-limited public endpoints with no
uptime guarantee — an empty search or a missing field is usually the API
having a bad day, not a bug to chase. That's exactly why every fetched
result lands in an editable form instead of being trusted blindly.

## How each enhancement works

**1. Multi-year, no wasted writes.** All years live in one SQLite DB
(`booktracker.db`). `sync` diffs incoming CSV rows against what's already
stored and only INSERTs new rows / UPDATEs changed ones — unchanged rows
are skipped entirely. Pages are rendered on request from the DB
(`GET /year/<year>`), and the year dropdown just lists `SELECT DISTINCT
year`. Nothing is regenerated or rewritten unless the underlying data
actually changed.

**2. Search.** The search box calls `GET /api/search?q=...`, which runs a
`LIKE` query against the `title` column across *all* years in one shot and
returns matches (with their year) so you can jump straight to the right
year page from a search hit, even for a title released in a year you
aren't currently viewing.

**3. Star a book or series, persists across syncs.** Stars are keyed by
`slug` in a separate `stars` table — *not* a column on each release row.
Whether a release shows as starred is computed with a `LEFT JOIN` against
`stars` at read time. That means: starring one volume stars the slug,
which covers every volume of that series past *and future* — a new volume
added by a later `sync`, or a new manually-added volume with a matching
Series+Author, is automatically starred and grouped with no extra
bookkeeping.

**4. Reading status (To-Read / Reading / Read / Dropped).** The ★ My
Starred page is a collapsible accordion — one row per series, expand to
see its volumes — with its own search box, and a status picker at both
the series level and each individual volume. The status you pick has
specific propagation rules:

- Setting a **series's** status applies it to every volume in that
  series.
- Marking a **volume** `Dropped` also marks every later volume of that
  series `Dropped` (so does a brand-new volume synced/added in
  afterward — the drop carries forward to it too, not just the volumes
  that existed at the time).
- Marking a **volume** `To-Read` also marks every later volume `To-Read`.
- `Reading` and `Read` only ever apply to the single volume you set them
  on — they describe where you are, not a blanket statement about
  volumes you haven't touched yet.
- Starring a series seeds every one of its current volumes as `To-Read`
  by default, since that's the whole reason you'd star something.

## Does moving to a DB make it faster?

Not for the part you actually watch render — one year's table (~1-2k rows)
was already just a JS array getting filtered/sorted in memory, and that
was instant before and still is. Where the DB actually pays off is
everything that used to require re-fetching/re-parsing the whole page or
regenerating a whole file: cross-year search, diff-only re-syncing, and
star/status persistence that survives regeneration entirely. So: yes,
worth it — but the win is on the read/write/maintenance side, not raw
page-rendering speed.

## Web server

`python app.py serve` runs the Flask app on
[Waitress](https://docs.pylonsproject.org/projects/waitress/), a
production-grade WSGI server and one of the servers Flask's own
deployment docs recommend. Waitress was chosen because it's the one
option that runs the same way on every platform this app supports:

| Server | Linux / macOS | Windows | Notes |
|---|---|---|---|
| **Waitress** (used) | ✅ | ✅ | Pure Python, no extra dependencies, runs Flask directly |
| Gunicorn | ✅ | ❌ | Needs Unix `fork()`, so it won't start on Windows |
| Uvicorn | ✅ | ⚠️ | An ASGI server for async frameworks. Flask needs an adapter and gains nothing |

Flask's built-in development server is only used with `serve --debug`,
which turns on auto-reload and verbose logs. Werkzeug's interactive
debugger is never enabled.

If you ever expose the app beyond your home network, put it behind a
reverse proxy that adds a login (for example Caddy or nginx with basic
auth), or reach it over a VPN such as Tailscale. The app itself has no
login.

## Network access

By default the server only listens on `127.0.0.1`, so only the computer
running it can open the app. To use it from your phone or another PC,
use `--lan` (`./install.sh --lan`, `.\install.ps1 -Lan`, or
`python app.py serve --lan`), or set `host = 0.0.0.0` in `config.ini`.
On startup it prints both URLs:

```
Local:   http://127.0.0.1:7077
Network: http://192.168.1.23:7077
```

**The app has no login**, so anyone on that network can edit your data.
Only turn this on for a network you trust. Open the app by IP address,
or list host names such as `mybox.lan` under `allowed_hosts` in
`config.ini`. Unknown host names are refused, as a defence against DNS
rebinding.

If another device can't reach it, open the port in your firewall:

| OS | Command |
|---|---|
| Debian / Ubuntu / MX (ufw) | `sudo ufw allow 7077/tcp` |
| RHEL / Rocky / Alma / Fedora (firewalld) | `sudo firewall-cmd --permanent --add-port=7077/tcp && sudo firewall-cmd --reload` |
| Windows | Allow Python on **Private** networks when Windows Firewall asks |
| macOS | Allow incoming connections for Python when asked |

## Upgrading from LNRelease

If you're running this on a machine that already has an LNRelease
install, three things carry over automatically the first time you start
the new version, no manual steps needed:

- **Database**: if `booktracker.db` doesn't exist yet but `lnrelease.db`
  does, it's renamed (not copied) on first startup — your stars, statuses,
  and every synced release come along as-is.
- **Schema**: new columns (subtitle, narrator, series title, runtime,
  ISBN, cover URL, genres, description, language, and a couple of
  internal bookkeeping fields) are added via `ALTER TABLE` automatically;
  existing rows just get `NULL` for the new fields until you edit them.
- **systemd units**: re-running `install.sh` replaces the old units. It
  removes `booktracker-sync.service` / `.timer` (syncing now happens
  inside the server) and the old `lnrelease.*` names, and moves a
  `HARDCOVER_API_TOKEN` from the old unit into `config.ini`.
- **Database location**: an existing `booktracker.db` next to `app.py`
  keeps being used in place. New installs use the per-user data folder
  (see [Where your files live](#where-your-files-live)).

**One behaviour change in 2026.11.24-01:** the server used to listen on
the network (`0.0.0.0`) by default. It now listens on this computer only.
Re-install with `--lan` if you open it from other devices.

The one thing that *doesn't* carry over automatically is the port, if you
had anything (a firewall rule, a bookmark, a reverse-proxy config)
pointing at the old default of `7000` — the new default is `7077`.

## Project structure

```
booktracker/
├── app.py                    Flask routes + CLI entry point
│                             (sync | serve [--lan] | paths | init-config |
│                             install-service | uninstall-service | --version),
│                             request guard (CSRF / Host checks), built-in
│                             periodic sync
├── config.py                 Per-OS file locations (config, data, logs, DB)
│                             and config.ini / environment-variable settings
├── service.py                Per-OS autostart: systemd user unit, XDG
│                             autostart, macOS launchd agent, Windows Startup
│                             shortcut
├── db.py                     SQLite schema, CSV sync/diff logic,
│                             search/star/status queries, manual add/edit/
│                             remove, and the imported_books (My Books) table
├── external_search.py        Hardcover / Google Books / Open Library /
│                             Audible / Audnexus lookups and Amazon URL
│                             scraping for the Add page
├── template.py               Server-rendered HTML/CSS/JS for every page
├── version.py                App name + version string
├── requirements.txt          Flask, requests, waitress
├── install.sh / uninstall.sh Linux + macOS installer wrappers
├── install.ps1 / uninstall.ps1  Windows installer wrappers
├── tests/test_smoke.py       Cross-platform smoke tests (stdlib unittest)
├── .github/workflows/ci.yml  CI: Ubuntu, Debian, Rocky 9, macOS, Windows
├── static/                   App icon + favicons
├── .gitignore
└── README.md
```

Not shown above: `booktracker.db`, the SQLite database itself (see
[Where your files live](#where-your-files-live)), `config.ini`, and
`venv/`, the virtual environment — both are created the first time you
run the app and are excluded from git via `.gitignore`, since they're
local, machine-specific, and (in the DB's case) contain your personal
reading data rather than project source.

## Security

**Static analysis (e.g. GitHub's CodeQL default setup).** As of this
version, the following categories have been addressed:

- **SSRF** — the "paste an Amazon URL" feature makes a live outbound
  request to whatever URL you give it, which is inherently an SSRF
  shape. `_is_amazon_url()` in `external_search.py` validates the
  request's *actual parsed hostname* (via `urllib.parse`) against a
  strict `amazon.<tld>` pattern before any request is made — not just
  whether the string "amazon.com" appears somewhere in it — closing off
  tricks like `http://internal-host/?x=amazon.com/dp/...` being treated
  as a legitimate Amazon link.
- **ReDoS** — several regexes used adjacent ambiguous quantifiers (e.g.
  `\s*` next to a lazy `.*?` that could match the same characters),
  which can blow up matching time on adversarial input. Rewritten to use
  negated character classes instead of `.*?` wherever the delimiter is
  known, plus defensive length caps (`_MAX_SERIES_TEXT_CHARS`,
  `_MAX_TITLE_CHARS`, `MAX_SCRAPED_HTML_CHARS`) so worst-case regex cost
  stays bounded regardless of what an external API or scraped page
  hands back.
- **Stack-trace / internal-detail exposure** — error responses from the
  external-search endpoints return curated, human-written messages (the
  same ones documented throughout this README, e.g. "Hardcover isn't
  configured..."), never a raw caught exception or a URL that might
  carry a credential in its query string. Full exception detail is
  logged server-side only (stderr / `app.logger`), not sent to the
  browser.
- **Stored XSS via JSON-in-`<script>`** — book metadata (title, author,
  publisher, etc.) is user-controlled — either typed directly, or
  returned by an external API/scraped page you don't control — and gets
  embedded into every page twice: once server-side into a `<script>`
  tag as JSON, and again client-side into HTML via JavaScript template
  literals. Both paths are now escaped: `_safe_json_for_script()` in
  `template.py` prevents a title containing literal `</script>` from
  closing the tag early, and every place client-side JS builds HTML
  from book data now runs it through `escapeHtml()`/`escapeAttr()`
  first. Both fixes were verified against actual exploit payloads run
  through the real code (see the version's changelog entry below), not
  just reviewed by eye.
- **CSRF and DNS rebinding (2026.11.24-01).** The app has no login, so
  every POST must come from the app's own pages. A cross-site `Origin`
  or `Sec-Fetch-Site` header gets a 403. Requests whose `Host` is an
  unknown domain name are also refused. IP addresses, `localhost`, this
  machine's host name, and `allowed_hosts` are accepted.
- **Bind address.** The server listens on `127.0.0.1` unless you choose
  `--lan`.
- **SSRF via redirects.** "Fetch from URL" no longer follows redirects
  automatically. Each hop is re-checked against the Amazon host
  allowlist.
- **Secrets** live only in `config.ini` (mode 600) or the environment,
  never in the app folder or a service file.

## Development

```bash
venv/bin/python -m unittest discover -s tests -v
```

CI (`.github/workflows/ci.yml`) runs the tests on Ubuntu, Debian, Rocky
Linux 9, macOS, and Windows, on Python 3.11 (the minimum) and 3.14.
