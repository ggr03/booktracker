"""
Cross-platform smoke tests. Pure stdlib unittest (no pytest needed):

    python -m unittest discover -s tests -v

Every test runs against a throwaway DB/config/data directory, never
your real one.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

_TMP = tempfile.TemporaryDirectory()
os.environ["BOOKTRACKER_CONFIG_DIR"] = os.path.join(_TMP.name, "config")
os.environ["BOOKTRACKER_DATA_DIR"] = os.path.join(_TMP.name, "data")
os.environ["BOOKTRACKER_DB"] = os.path.join(_TMP.name, "data", "test.db")
os.environ["BOOKTRACKER_LOG_DIR"] = os.path.join(_TMP.name, "Logs")
for _k in ("HARDCOVER_API_TOKEN", "GOOGLE_BOOKS_API_KEY", "BOOKTRACKER_HOST"):
    os.environ.pop(_k, None)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import BookTrackerCfg as config  # noqa: E402
import BookTrackerDB as db  # noqa: E402
import BookTrackerApp as app_module  # noqa: E402
import BookTrackerService as service  # noqa: E402
import BookTrackerLogs as logs  # noqa: E402


def _read_log(name):
    for h in logs.get(name).handlers:
        h.flush()
    path = logs.log_file(name)
    return path.read_text(encoding="utf-8") if path.exists() else ""

SAMPLE_CSV = """slug,url,publisher,title,volume,format,isbn,date
s1,https://example.com/a1,Yen Press,Test Series,1,Digital,111,2026-01-15
s1,https://example.com/a1p,Yen Press,Test Series,1,Paperback,112,2026-01-15
s1,https://example.com/a2,Yen Press,Test Series,2,Digital,113,2026-03-20
s2,https://example.com/b1,J-Novel Club,Other Series,1,Audiobook,114,2025-11-02
"""

GOODREADS_CSV = ("Book Id,Title,Author,Publisher,Year Published,Date Read\n"
                 "1,Some Book,Some Author,Some Pub,2020,2024/05/01\n"
                 "2,Unread Book,Another Author,Pub,2021,\n")

ORIGIN = "http://localhost"


class SmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app_module.DB_PATH = Path(os.environ["BOOKTRACKER_DB"])
        stats = db.sync_from_csv(SAMPLE_CSV, db_path=app_module.DB_PATH)
        assert stats["added"] == 3, stats
        app_module.app.config["TESTING"] = True
        cls.client = app_module.app.test_client()

    # --- paths / config -------------------------------------------------
    def test_paths_follow_overrides(self):
        self.assertEqual(config.config_dir(), Path(os.environ["BOOKTRACKER_CONFIG_DIR"]))
        self.assertEqual(config.data_dir(), Path(os.environ["BOOKTRACKER_DATA_DIR"]))
        self.assertEqual(db.DEFAULT_DB_PATH, Path(os.environ["BOOKTRACKER_DB"]))

    def test_init_config_and_secret(self):
        path = config.init_config(hardcover_token="Bearer abc123")
        self.assertTrue(path.exists())
        if not config.IS_WINDOWS:
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(config.secret("api", "hardcover_token"), "abc123")
        # Never overwrites a value that's already set.
        config.init_config(hardcover_token="other")
        self.assertEqual(config.secret("api", "hardcover_token"), "abc123")
        self.assertEqual(config.get("server", "host"), "127.0.0.1")

    # --- pages -----------------------------------------------------------
    def test_pages_render(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 302)
        for url in ("/year/2026", "/starred", "/add", "/my_books", "/api/years"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_search(self):
        r = self.client.get("/api/search?q=Test")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(any(row["title"] == "Test Series" for row in r.get_json()))

    # --- request guard ----------------------------------------------------
    def test_same_origin_post_allowed(self):
        r = self.client.post("/api/star", json={"slug": "s2"}, headers={"Origin": ORIGIN})
        self.assertEqual(r.status_code, 200)
        self.assertIn("starred", r.get_json())

    def test_post_without_origin_allowed(self):  # curl / scripts
        r = self.client.post("/api/star", json={"slug": "s2"})
        self.assertEqual(r.status_code, 200)

    def test_cross_origin_post_blocked(self):
        for headers in ({"Origin": "https://evil.example"},
                        {"Origin": "null"},
                        {"Sec-Fetch-Site": "cross-site"}):
            with self.subTest(headers=headers):
                r = self.client.post("/api/release/1/remove", headers=headers)
                self.assertEqual(r.status_code, 403)

    def test_unknown_host_blocked(self):
        r = self.client.get("/api/years", headers={"Host": "rebind.evil.example:7077"})
        self.assertEqual(r.status_code, 403)

    def test_ip_and_localhost_hosts_allowed(self):
        for host in ("127.0.0.1:7077", "192.168.1.50:7077", "[::1]:7077", "localhost:7077"):
            with self.subTest(host=host):
                r = self.client.get("/api/years", headers={"Host": host})
                self.assertEqual(r.status_code, 200)

    # --- My Books CSV import ---------------------------------------------
    def test_goodreads_import(self):
        import io
        data = {"file": (io.BytesIO(GOODREADS_CSV.encode("utf-8-sig")), "export.csv")}
        r = self.client.post("/api/import_books_csv", data=data,
                             content_type="multipart/form-data", headers={"Origin": ORIGIN})
        self.assertEqual(r.status_code, 200, r.data)
        books = self.client.get("/api/imported_books").get_json()
        self.assertTrue(any(b["title"] == "Some Book" for b in books))

    # --- Amazon fetch: request host always comes from the allowlist -------
    def test_amazon_fetch_uses_allowlisted_host(self):
        import BookTrackerSearch as es
        from unittest import mock
        seen = []

        class Resp:
            def __init__(self, status, location=None):
                self.status_code = status
                self.headers = {"Location": location} if location else {}
                self.is_redirect = status in (301, 302, 303, 307, 308)
                self.is_permanent_redirect = status in (301, 308)
                self.text = "<html></html>"

            def raise_for_status(self):
                pass

        def fake_get(url, **kw):
            seen.append(url)
            self.assertFalse(kw.get("allow_redirects", True))
            if len(seen) == 1:
                return Resp(302, "/Some-Title/dp/0316411876/ref=x")
            return Resp(200)

        with mock.patch.object(es.requests, "get", side_effect=fake_get):
            es.fetch_amazon_product("https://smile.amazon.co.uk/foo/dp/0316411876?tag=1", "0316411876")
        self.assertEqual(seen, ["https://www.amazon.co.uk/dp/0316411876",
                                "https://www.amazon.co.uk/Some-Title/dp/0316411876/ref=x"])

        def evil_redirect(url, **kw):
            return Resp(302, "http://169.254.169.254/latest/meta-data")

        with mock.patch.object(es.requests, "get", side_effect=evil_redirect) as g:
            r = es.fetch_amazon_product("https://www.amazon.com/dp/B000000000", "B000000000")
        self.assertEqual(g.call_count, 1)
        self.assertIn("unexpected", r["warning"])

        with mock.patch.object(es.requests, "get") as g:
            r = es.fetch_amazon_product("https://www.amazon.zz/dp/B000000000", "B000000000")
        g.assert_not_called()

    # --- activity logs ----------------------------------------------------
    def test_log_files_are_separate_and_camelcase(self):
        self.assertEqual(logs.log_dir(), Path(os.environ["BOOKTRACKER_LOG_DIR"]))
        for name in logs.ALL_LOGS:
            self.assertRegex(name, r"^[a-z]+(?:[A-Z][a-z]+)+$")
        self.assertEqual(len(set(logs.ALL_LOGS)), 6)

    def test_star_and_status_logged(self):
        self.client.post("/api/star", json={"slug": "s1"}, headers={"Origin": ORIGIN})
        text = _read_log(logs.STARRED_UPDATES)
        self.assertRegex(text, r"(UN)?STARRED \"Test Series\" \[s1\]")
        self.assertNotIn("Test Series", _read_log(logs.MANUAL_ADDITIONS))

    def test_manual_addition_logged(self):
        r = self.client.post("/api/external_add", headers={"Origin": ORIGIN}, json={
            "kind": "book", "formats": ["print"],
            "volume": {"title": "Logged Book\nFAKE LINE", "author": "A. Writer",
                       "source_label": "Open Library"}})
        self.assertEqual(r.status_code, 200, r.data)
        text = _read_log(logs.MANUAL_ADDITIONS)
        self.assertIn('ADDED "Logged Book\\nFAKE LINE" by "A. Writer"', text)
        self.assertNotIn("\nFAKE LINE", text)     # newline in user data can't forge a line

    def test_my_books_import_logged(self):
        import io
        data = {"file": (io.BytesIO(GOODREADS_CSV.encode("utf-8")), "logged.csv")}
        self.client.post("/api/import_books_csv", data=data,
                         content_type="multipart/form-data", headers={"Origin": ORIGIN})
        self.assertIn('IMPORT "logged.csv": 2 rows read', _read_log(logs.MY_BOOKS_IMPORTS))

    def test_unhandled_error_logged_with_traceback(self):
        logs.setup(app_module.app)
        app_module.app.config["TESTING"] = False
        app_module.app.config["PROPAGATE_EXCEPTIONS"] = False
        from unittest import mock
        try:
            with mock.patch.object(db, "get_years", side_effect=RuntimeError("boom-for-test")):
                r = self.client.get("/api/years")
        finally:
            app_module.app.config["TESTING"] = True
        self.assertEqual(r.status_code, 500)
        for h in __import__("logging").getLogger().handlers:
            h.flush()
        text = logs.log_file(logs.ERRORS).read_text(encoding="utf-8")
        self.assertIn("boom-for-test", text)
        self.assertIn("Traceback", text)

    # --- database file rename -------------------------------------------
    def test_legacy_db_renamed_with_sidecars(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            for name in ("booktracker.db", "booktracker.db-wal", "booktracker.db.last-sync"):
                (d / name).write_text(name)
            with mock.patch.object(config, "APP_DIR", d), \
                    mock.patch.object(config, "APP_DIR_DB", d / "BookTracker.db"):
                self.assertEqual(config.migrate_legacy_db(d / "BookTracker.db"),
                                 "booktracker.db -> BookTracker.db")
                self.assertEqual(sorted(p.name for p in d.iterdir()),
                                 ["BookTracker.db", "BookTracker.db-wal", "BookTracker.db.last-sync"])
                self.assertEqual((d / "BookTracker.db").read_text(), "booktracker.db")
                self.assertIsNone(config.migrate_legacy_db(d / "BookTracker.db"))  # idempotent

    @unittest.skipIf(sys.platform.startswith("win"), "POSIX signals")
    def test_startup_and_shutdown_logged(self):
        import signal
        import socket
        import subprocess
        import time
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, BOOKTRACKER_LOG_DIR=d)
            app_py = str(Path(__file__).resolve().parent.parent / "BookTrackerApp.py")
            proc = subprocess.Popen([sys.executable, app_py, "serve", "--port", str(port),
                                     "--no-auto-sync"], env=env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                deadline = time.time() + 20
                while time.time() < deadline:
                    try:
                        socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
                        break
                    except OSError:
                        time.sleep(0.2)
            finally:
                proc.send_signal(signal.SIGTERM)
                proc.wait(timeout=20)
            start = Path(d, "appStartup.log").read_text(encoding="utf-8")
            stop = Path(d, "appShutdown.log").read_text(encoding="utf-8")
        self.assertIn(f"listening on 127.0.0.1:{port}", start)
        self.assertIn("reason: received SIGTERM", stop)

    # --- service helpers ---------------------------------------------------
    def test_service_args(self):
        args = service._serve_args(True, 8080, Path("/tmp/x.log"))
        self.assertEqual(args[1:], ["serve", "--lan", "--port", "8080", "--log-file", str(Path("/tmp/x.log"))])
        self.assertEqual(service._systemd_quote("/a b/c"), '"/a b/c"')
        self.assertEqual(service._systemd_quote("/plain"), "/plain")
        self.assertEqual(service._win_quote(r"C:\Program Files\x"), r'"C:\Program Files\x"')
        self.assertEqual(service._ps_literal("it's"), "'it''s'")


if __name__ == "__main__":
    unittest.main()
