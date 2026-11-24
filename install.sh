#!/usr/bin/env bash
# Book Tracker installer for Linux (Debian/Ubuntu/MX, RHEL/Rocky/Alma/Fedora,
# and most others) and macOS. Windows users: run install.ps1 instead.
#
#   ./install.sh          # only this computer can open the app
#   ./install.sh --lan    # also reachable from other devices on your network
#
# Creates ./venv, installs dependencies, creates a private config.ini,
# runs the first sync, then registers autostart via
# `python app.py install-service` (systemd user unit, XDG autostart, or a
# macOS launchd agent -- see service.py).
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

if [ ! -f app.py ]; then
    echo "ERROR: app.py not found next to install.sh ($APP_DIR)." >&2
    exit 1
fi

# 1. Find a Python >= 3.11 (the oldest release still getting security fixes).
PY=""
for cand in python3.14 python3.13 python3.12 python3.11 python3; do
    if command -v "$cand" >/dev/null 2>&1 &&
       "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
        PY="$cand"; break
    fi
done
if [ -z "$PY" ]; then
    echo "ERROR: Python 3.11 or newer is required. Install it with:" >&2
    if   command -v apt-get >/dev/null 2>&1; then
        echo "  sudo apt install python3 python3-venv   (Debian 12+, Ubuntu 24.04+, MX 23+)" >&2
    elif command -v dnf     >/dev/null 2>&1; then
        echo "  sudo dnf install python3.12 python3.12-pip   (RHEL/Rocky/Alma 8 and 9)" >&2
        echo "  sudo dnf install python3                     (RHEL 10, Fedora)" >&2
    elif [ "$(uname)" = "Darwin" ]; then
        echo "  brew install python   (or the installer from https://www.python.org/downloads/macos/)" >&2
        echo "  Note: the python3 from Xcode Command Line Tools is 3.9 and too old." >&2
    fi
    exit 1
fi
echo "Using $($PY --version) ($PY)"

# 2. Virtualenv. Debian-family distros ship venv without ensurepip unless
#    python3-venv is installed, so check for that explicitly.
if [ ! -x venv/bin/python ]; then
    if ! "$PY" -c 'import ensurepip, venv' >/dev/null 2>&1; then
        echo "ERROR: Python's venv module isn't available." >&2
        if command -v apt-get >/dev/null 2>&1; then
            ver="$("$PY" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
            echo "  sudo apt install python3-venv   (or python${ver}-venv)" >&2
        elif command -v dnf >/dev/null 2>&1; then
            echo "  sudo dnf install python3-pip" >&2
        fi
        exit 1
    fi
    echo "Creating virtualenv ..."
    "$PY" -m venv venv
fi
venv/bin/python -m pip install --quiet --upgrade pip
venv/bin/python -m pip install --quiet -r requirements.txt

# 3. Private config file (API tokens live here, never in this folder).
venv/bin/python app.py init-config

# 4. First sync (skipped if a DB already has data -- sync is diff-only anyway).
venv/bin/python app.py sync || echo "WARNING: initial sync failed; the server will retry automatically."

# 5. Autostart.
venv/bin/python app.py install-service "$@"

echo
venv/bin/python app.py paths
