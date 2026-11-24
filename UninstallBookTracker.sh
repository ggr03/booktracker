#!/usr/bin/env bash
# Removes Book Tracker's autostart entry (systemd user unit, XDG autostart,
# or macOS launchd agent), including units from older releases.
# App files, venv, config.ini and the database are left untouched.
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$APP_DIR/venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
"$PY" "$APP_DIR/BookTrackerApp.py" uninstall-service
