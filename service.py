"""
Start Book Tracker automatically at login, on any supported OS.

    python app.py install-service [--lan] [--port N]
    python app.py uninstall-service

  Linux with systemd (Debian, Ubuntu, MX, RHEL/Rocky/Alma, Fedora, ...)
      -> a systemd *user* unit: ~/.config/systemd/user/booktracker.service
  Linux without systemd (e.g. MX Linux booted with SysVinit)
      -> an XDG autostart entry: ~/.config/autostart/booktracker.desktop
  macOS
      -> a launchd agent: ~/Library/LaunchAgents/local.booktracker.plist
  Windows
      -> a shortcut in your Startup folder that runs pythonw (no console
         window, no admin rights needed)

All of them run `app.py serve` with the Python that ran this command
(normally the project's venv), so nothing depends on your shell setup.
Periodic LNRelease syncing happens inside the server itself now, so no
separate timer/cron job is installed anywhere.
"""
from __future__ import annotations

import os
import plistlib
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import config

APP_PY = config.APP_DIR / "app.py"
SERVICE_NAME = "booktracker"
MAC_LABEL = "local.booktracker"
WIN_SHORTCUT_NAME = "Book Tracker.lnk"

# Units from older releases (incl. the pre-rename LNRelease ones) that
# install/uninstall should clean up.
_LEGACY_UNITS = [
    "booktracker-sync.timer", "booktracker-sync.service",
    "lnrelease.service", "lnrelease-sync.timer", "lnrelease-sync.service",
]


def _serve_args(lan: bool, port: Optional[int], log_file: Optional[Path] = None) -> List[str]:
    args = [str(APP_PY), "serve"]
    if lan:
        args.append("--lan")
    if port:
        args += ["--port", str(port)]
    if log_file:
        args += ["--log-file", str(log_file)]
    return args


def _run(cmd: List[str], check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, universal_newlines=True)


def _print_url(lan: bool, port: Optional[int]) -> None:
    port = port or config.get_int("server", "port", 7077)
    print(f"\nBook Tracker should now be at: http://127.0.0.1:{port}")
    if lan:
        print("It is also reachable from other devices on your network (no login -- "
              "trusted networks only).")


# ---------------------------------------------------------------------------
# Token migration: older installs kept HARDCOVER_API_TOKEN in the unit file.
# ---------------------------------------------------------------------------

def _migrate_token_from_unit(unit_path: Path) -> None:
    if not unit_path.exists() or config.secret("api", "hardcover_token"):
        return
    m = re.search(r"^Environment=\"?HARDCOVER_API_TOKEN=([^\"\s]+)",
                  unit_path.read_text(encoding="utf-8", errors="replace"), re.MULTILINE)
    if m:
        path = config.init_config(hardcover_token=m.group(1))
        print(f"Moved your Hardcover token out of the old unit file into {path} (private, 0600).")


# ---------------------------------------------------------------------------
# Linux
# ---------------------------------------------------------------------------

def _systemd_user_available() -> bool:
    if not shutil.which("systemctl"):
        return False
    return _run(["systemctl", "--user", "show-environment"]).returncode == 0


def _systemd_quote(arg: str) -> str:
    return '"' + arg.replace("\\", "\\\\").replace('"', '\\"') + '"' if re.search(r'[\s"\\]', arg) else arg


def _unit_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "systemd" / "user"


def _install_linux(lan: bool, port: Optional[int]) -> None:
    if _systemd_user_available():
        unit_dir = _unit_dir()
        unit_dir.mkdir(parents=True, exist_ok=True)
        unit = unit_dir / f"{SERVICE_NAME}.service"
        _migrate_token_from_unit(unit)
        for old in _LEGACY_UNITS:
            _run(["systemctl", "--user", "disable", "--now", old])
            (unit_dir / old).unlink(missing_ok=True)
        exec_start = " ".join(_systemd_quote(a) for a in [sys.executable] + _serve_args(lan, port))
        unit.write_text(
            "[Unit]\n"
            "Description=Book Tracker local web app\n"
            "After=network-online.target\n\n"
            "[Service]\n"
            "Type=simple\n"
            f"WorkingDirectory={_systemd_quote(str(config.APP_DIR))}\n"
            f"ExecStart={exec_start}\n"
            "Restart=on-failure\n"
            "RestartSec=5\n\n"
            "[Install]\n"
            "WantedBy=default.target\n",
            encoding="utf-8",
        )
        os.chmod(str(unit), 0o600)
        _run(["systemctl", "--user", "daemon-reload"], check=True)
        _run(["systemctl", "--user", "enable", f"{SERVICE_NAME}.service"], check=True)
        _run(["systemctl", "--user", "restart", f"{SERVICE_NAME}.service"], check=True)
        print(f"Installed systemd user service: {unit}")
        print("  status:  systemctl --user status booktracker")
        print("  logs:    journalctl --user -u booktracker -f")
        print("To keep it running after you log out:  sudo loginctl enable-linger $USER")
    else:
        autostart = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "autostart"
        autostart.mkdir(parents=True, exist_ok=True)
        log_file = config.log_dir() / "server.log"
        argv = [sys.executable] + _serve_args(lan, port, log_file)
        desktop = autostart / f"{SERVICE_NAME}.desktop"
        desktop.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Book Tracker\n"
            "Comment=Book Tracker local web app\n"
            f"Exec={' '.join(_desktop_quote(a) for a in argv)}\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n",
            encoding="utf-8",
        )
        print("systemd user services aren't available (e.g. a SysVinit boot), so an")
        print(f"autostart entry was added instead: {desktop}")
        print("It starts when you log in to your desktop. Starting it now ...")
        subprocess.Popen(argv, cwd=str(config.APP_DIR), start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        print(f"  log: {log_file}")
    if lan and shutil.which("firewall-cmd"):
        p = port or config.get_int("server", "port", 7077)
        print("\nfirewalld detected (RHEL/Fedora family). To allow other devices in:")
        print(f"  sudo firewall-cmd --permanent --add-port={p}/tcp && sudo firewall-cmd --reload")
    elif lan and shutil.which("ufw"):
        p = port or config.get_int("server", "port", 7077)
        print(f"\nIf ufw is enabled, allow other devices in with:  sudo ufw allow {p}/tcp")


def _desktop_quote(arg: str) -> str:
    if re.search(r'[\s"\'\\$`]', arg):
        return '"' + re.sub(r'(["`$\\])', r"\\\1", arg) + '"'
    return arg


def _uninstall_linux() -> None:
    unit_dir = _unit_dir()
    if shutil.which("systemctl"):
        for name in [f"{SERVICE_NAME}.service"] + _LEGACY_UNITS:
            _run(["systemctl", "--user", "disable", "--now", name])
            (unit_dir / name).unlink(missing_ok=True)
        _run(["systemctl", "--user", "daemon-reload"])
    autostart = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "autostart"
    (autostart / f"{SERVICE_NAME}.desktop").unlink(missing_ok=True)
    if shutil.which("pkill"):
        _run(["pkill", "-f", f"{APP_PY} serve"])
    print("Removed Book Tracker autostart (systemd unit / autostart entry).")


# ---------------------------------------------------------------------------
# macOS
# ---------------------------------------------------------------------------

def _plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{MAC_LABEL}.plist"


def _install_macos(lan: bool, port: Optional[int]) -> None:
    plist = _plist_path()
    plist.parent.mkdir(parents=True, exist_ok=True)
    logs = config.log_dir()
    logs.mkdir(parents=True, exist_ok=True)
    uid = os.getuid()
    _run(["launchctl", "bootout", f"gui/{uid}", str(plist)])
    with open(plist, "wb") as fh:
        plistlib.dump({
            "Label": MAC_LABEL,
            "ProgramArguments": [sys.executable] + _serve_args(lan, port),
            "WorkingDirectory": str(config.APP_DIR),
            "RunAtLoad": True,
            "KeepAlive": {"SuccessfulExit": False},
            "StandardOutPath": str(logs / "server.log"),
            "StandardErrorPath": str(logs / "server.log"),
        }, fh)
    r = _run(["launchctl", "bootstrap", f"gui/{uid}", str(plist)])
    if r.returncode != 0:   # older macOS
        _run(["launchctl", "load", "-w", str(plist)])
    print(f"Installed launchd agent: {plist}")
    print(f"  logs:    {logs / 'server.log'}")
    print(f"  restart: launchctl kickstart -k gui/{uid}/{MAC_LABEL}")


def _uninstall_macos() -> None:
    plist = _plist_path()
    _run(["launchctl", "bootout", f"gui/{os.getuid()}", str(plist)])
    _run(["launchctl", "unload", "-w", str(plist)])
    plist.unlink(missing_ok=True)
    print("Removed Book Tracker launchd agent.")


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------

def _startup_dir() -> Path:
    return (Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
            / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup")


def _pythonw() -> str:
    exe = Path(sys.executable)
    candidate = exe.with_name("pythonw.exe")
    return str(candidate if candidate.exists() else exe)


def _win_quote(arg: str) -> str:
    return f'"{arg}"' if (" " in arg or "\t" in arg) else arg


def _ps_literal(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def _stop_windows_server() -> None:
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "
          + _ps_literal(f"*{APP_PY}*serve*")
          + " } | Invoke-CimMethod -MethodName Terminate | Out-Null")
    _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps])


def _install_windows(lan: bool, port: Optional[int]) -> None:
    log_file = config.log_dir() / "server.log"
    pythonw = _pythonw()
    args = _serve_args(lan, port, log_file)
    lnk = _startup_dir() / WIN_SHORTCUT_NAME
    ps = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut(" + _ps_literal(str(lnk)) + ");"
        "$s.TargetPath = " + _ps_literal(pythonw) + ";"
        "$s.Arguments = " + _ps_literal(" ".join(_win_quote(a) for a in args)) + ";"
        "$s.WorkingDirectory = " + _ps_literal(str(config.APP_DIR)) + ";"
        "$s.WindowStyle = 7;"
        "$s.Description = 'Book Tracker local web app';"
        "$s.Save()"
    )
    r = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps])
    if r.returncode != 0:
        print(r.stdout)
        raise SystemExit("Could not create the Startup shortcut (see message above).")
    _stop_windows_server()
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([pythonw] + args, cwd=str(config.APP_DIR), creationflags=flags,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Added to Startup: {lnk}")
    print(f"  log: {log_file}")
    if lan:
        print("Windows Firewall may ask whether to allow Python on private networks -- "
              "allow it for LAN access.")


def _uninstall_windows() -> None:
    (_startup_dir() / WIN_SHORTCUT_NAME).unlink(missing_ok=True)
    _stop_windows_server()
    print("Removed Book Tracker from Startup and stopped the running server.")


# ---------------------------------------------------------------------------

def install(lan: bool = False, port: Optional[int] = None) -> None:
    if not config.config_file().exists():
        config.init_config()
        print(f"Created {config.config_file()} -- add your Hardcover token there.")
    if config.IS_WINDOWS:
        _install_windows(lan, port)
    elif config.IS_MACOS:
        _install_macos(lan, port)
    else:
        _install_linux(lan, port)
    _print_url(lan, port)


def uninstall() -> None:
    if config.IS_WINDOWS:
        _uninstall_windows()
    elif config.IS_MACOS:
        _uninstall_macos()
    else:
        _uninstall_linux()
    print("(App files, venv, config.ini and the database were left untouched.)")
