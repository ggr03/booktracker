#!/usr/bin/env bash
# Installs Book Tracker as a systemd --user service on MX Linux (or any
# systemd-based distro). Run this from wherever install.sh ended up --
# it locates app.py itself, so it works whether the unit files are in a
# systemd/ subfolder or sitting flat alongside app.py.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/app.py" ]; then
    APP_DIR="$SCRIPT_DIR"       # flat layout: install.sh next to app.py
else
    APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"   # nested layout: install.sh in systemd/
fi
UNIT_SRC_DIR="$SCRIPT_DIR"      # unit files always live next to install.sh
UNIT_DIR="$HOME/.config/systemd/user"

if [ ! -f "$APP_DIR/app.py" ]; then
    echo "ERROR: couldn't find app.py (looked in $APP_DIR). Run this script from" >&2
    echo "inside the app folder, or from its systemd/ subfolder." >&2
    exit 1
fi

echo "App directory: $APP_DIR"

# 1. Virtualenv + dependencies (the unit files call venv/bin/python directly,
#    so the service doesn't depend on your shell's active environment).
if [ ! -d "$APP_DIR/venv" ]; then
    echo "Creating virtualenv..."
    python3 -m venv "$APP_DIR/venv"
fi
"$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

# 2. First sync, so the server has data to serve on first start.
if [ ! -f "$APP_DIR/booktracker.db" ] && [ ! -f "$APP_DIR/lnrelease.db" ]; then
    echo "Running initial sync..."
    "$APP_DIR/venv/bin/python" "$APP_DIR/app.py" sync
fi

# 3. Install the unit files, with the *actual* app location substituted in
#    (so this works no matter where you extracted/cloned this folder to).
mkdir -p "$UNIT_DIR"
for unit in booktracker.service booktracker-sync.service booktracker-sync.timer; do
    sed "s#%h/booktracker_app#$APP_DIR#g" "$UNIT_SRC_DIR/$unit" > "$UNIT_DIR/$unit"
done
echo "Installed unit files to $UNIT_DIR (pointing at $APP_DIR)"

# 4. Reload, enable, start.
systemctl --user daemon-reload
systemctl --user enable --now booktracker.service
systemctl --user enable --now booktracker-sync.timer

echo
echo "Done. Status:"
systemctl --user status booktracker.service --no-pager || true
echo
echo "The web app should be at: http://127.0.0.1:7077"
echo
echo "IMPORTANT: user services normally stop when you log out. To keep it"
echo "running in the background (e.g. across SSH sessions, or so it survives"
echo "you logging out of the desktop), enable lingering once:"
echo
echo "    sudo loginctl enable-linger \$USER"
echo
echo "Useful commands:"
echo "  systemctl --user status booktracker.service"
echo "  systemctl --user restart booktracker.service"
echo "  journalctl --user -u booktracker.service -f"
echo "  systemctl --user list-timers booktracker-sync.timer"
