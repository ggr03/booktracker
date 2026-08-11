"""
Single source of truth for the app's version string.

Versioning scheme: ISO-date-and-counter, `YYYY.MM.DD-NN`.
- YYYY.MM.DD is the release date.
- NN is a two-digit counter, starting at 01, that increments if more than
  one release goes out on the same date. It resets to 01 on a new date.

This exists specifically so version numbers stay sortable and dateable
across branches/forks without needing semver bookkeeping -- bump this
one line and every page/service picks it up automatically.
"""
APP_NAME = "Book Tracker"
VERSION = "2026.08.10-01"
