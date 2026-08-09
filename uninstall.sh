#!/usr/bin/env bash
set -euo pipefail

UNIT_DIR="$HOME/.config/systemd/user"

systemctl --user disable --now booktracker.service 2>/dev/null || true
systemctl --user disable --now booktracker-sync.timer 2>/dev/null || true
# Old unit names, in case this is upgrading a pre-rename LNRelease install.
systemctl --user disable --now lnrelease.service 2>/dev/null || true
systemctl --user disable --now lnrelease-sync.timer 2>/dev/null || true

rm -f "$UNIT_DIR/booktracker.service" "$UNIT_DIR/booktracker-sync.service" "$UNIT_DIR/booktracker-sync.timer"
rm -f "$UNIT_DIR/lnrelease.service" "$UNIT_DIR/lnrelease-sync.service" "$UNIT_DIR/lnrelease-sync.timer"
systemctl --user daemon-reload

echo "Removed Book Tracker systemd user units."
echo "(App files, venv, and the database were left untouched.)"
