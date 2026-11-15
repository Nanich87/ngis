"""End-to-end XSS test: renders every page in headless Firefox with hostile data.

Every payload, if it ever executes, calls back to a small HTTP "collector" run by the test.
Skipped when Firefox is not installed.

    python3 -m unittest tests/test_security_browser.py -v
"""
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

from support import ServerTestCase, free_port

FIREFOX = shutil.which('firefox')
PAGE_WAIT_SECONDS = 6


class Collector:
    """Records /hit requests and serves a page that embeds the app and waits for it."""

    def __init__(self):
        self.hits = []
        collector = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                url = urlparse(self.path)
                q = parse_qs(url.query)
                if url.path == '/hit':
                    collector.hits.append(q.get('where', ['?'])[0])
                    self._send(b'', 'image/gif')
                elif url.path == '/slow':
                    time.sleep(float(q.get('s', ['5'])[0]))
                    self._send(b'', 'image/gif')
                elif url.path == '/page':
                    page = ('<html><body style="margin:0"><iframe src="{u}" style="border:0;width:1280px;height:800px"></iframe>'
                            '<img src="/hit?where=control">'
                            '<img src="/slow?s={s}"></body></html>').format(u=q['u'][0].replace('"', ''), s=PAGE_WAIT_SECONDS)
                    self._send(page.encode(), 'text/html')
                else:
                    self.send_error(404)

            def _send(self, body, ctype):
                self.send_response(200)
                self.send_header('Content-Type', ctype)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.port = free_port()
        self.server = ThreadingHTTPServer(('127.0.0.1', self.port), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@unittest.skipUnless(FIREFOX, 'Firefox is not installed')
class StoredXssBrowserTests(ServerTestCase):

    @classmethod
    def setUpClass(cls):
        # The pages are rendered inside a frame served by the collector, so allow only that origin
        # (the default 'none' would block the frame and every test would pass without rendering).
        cls.collector = Collector()
        cls.server_env = {'NGIS_FRAME_ANCESTORS': 'http://127.0.0.1:{}'.format(cls.collector.port)}
        super().setUpClass()
        cls.profile = tempfile.mkdtemp(prefix='ngis-ff-')
        cls._seed_hostile_data()
        cls._prepare_firefox_profile()

    @classmethod
    def tearDownClass(cls):
        cls.collector.close()
        shutil.rmtree(cls.profile, ignore_errors=True)
        super().tearDownClass()

    @classmethod
    def beacon(cls, where):
        return 'http://127.0.0.1:{}/hit?where={}'.format(cls.collector.port, where)

    @classmethod
    def payloads(cls, where):
        """Several vectors; any of them executing reports `where`."""
        b = cls.beacon(where)
        return ('<img src=x onerror="fetch(\'{b}-img\')">'
                '"><svg onload="fetch(\'{b}-svg\')">'
                '\'><script>fetch(\'{b}-script\')</script>'
                '</textarea><img src=x onerror="fetch(\'{b}-ta\')">').format(b=b)

    @classmethod
    def _seed_hostile_data(cls):
        p = cls.payloads
        feature_props = {
            'name': p('feature-name'),
            'type': p('feature-type'),
            'text': p('feature-text'),
            p('feature-key'): 'value',
            'intersection_number': p('feature-number'),
            'railroad_station': p('feature-station'),
        }
        geojson = json.dumps({
            'type': 'FeatureCollection',
            # An unsupported CRS name makes the map show a toast and the file page show an alert.
            'crs': {'type': 'name', 'properties': {'name': p('crs-name')}},
            'features': [{'type': 'Feature', 'properties': feature_props,
                          'geometry': {'type': 'Point', 'coordinates': [2600000, 5260000]}}]
        })
        expires = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

        conn = sqlite3.connect(cls.db_path)
        # Written straight to the database: imported or legacy data is not filtered by the API.
        conn.execute('INSERT INTO projects (id, name, year) VALUES (?, ?, ?)', ('p-xss', p('project-name'), p('project-year')))
        conn.execute('INSERT INTO layers (id, project_id, title, content) VALUES (?, ?, ?, ?)',
                     ('l-xss', 'p-xss', p('layer-title'), geojson))
        # A legitimate photo URL pointing at the collector proves that the profile page really rendered.
        conn.execute('UPDATE users SET display_name = ?, photo_url = ? WHERE id = ?',
                     (p('display-name'), cls.beacon('rendered-avatar'), 'u-admin'))
        conn.execute('UPDATE users SET display_name = ? WHERE id = ?', (p('other-display-name'), 'u-reader'))
        conn.execute('INSERT INTO users (id, email, display_name) VALUES (?, ?, ?)',
                     (p('user-id'), p('user-email') + '@x.bg', p('imported-name')))
        conn.execute('INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)', ('xss-session-token', 'u-admin', expires))
        conn.commit()
        conn.close()

    @classmethod
    def _prepare_firefox_profile(cls):
        # First run creates cookies.sqlite; then the admin session cookie is inserted.
        subprocess.run([FIREFOX, '--headless', '-no-remote', '-profile', cls.profile, '--screenshot',
                        os.path.join(cls.profile, 'init.png'), 'about:blank'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
        conn = sqlite3.connect(os.path.join(cls.profile, 'cookies.sqlite'))
        columns = {r[1] for r in conn.execute('PRAGMA table_info(moz_cookies)')}
        now_us = int(time.time() * 1e6)
        row = {
            'name': 'ngis_session', 'value': 'xss-session-token', 'host': '127.0.0.1', 'path': '/',
            # Milliseconds in current Firefox; still far in the future for versions that use seconds.
            'expiry': int((time.time() + 86400) * 1000),
            'lastAccessed': now_us, 'creationTime': now_us, 'isSecure': 0, 'isHttpOnly': 1,
            'sameSite': 1, 'schemeMap': 1, 'updateTime': now_us,
        }
        row = {k: v for k, v in row.items() if k in columns}
        conn.execute('INSERT INTO moz_cookies ({}) VALUES ({})'.format(', '.join(row), ', '.join('?' * len(row))),
                     list(row.values()))
        conn.commit()
        conn.close()

    def render(self, route):
        app_url = 'http://127.0.0.1:{}/#/{}'.format(self.port, route)
        page = 'http://127.0.0.1:{}/page?u={}'.format(self.collector.port, quote(app_url, safe=''))
        self.collector.hits.clear()
        subprocess.run([FIREFOX, '--headless', '-no-remote', '-profile', self.profile, '--window-size', '1280,800',
                        '--screenshot', os.path.join(self.profile, 'shot.png'), page],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
        return list(self.collector.hits)

    def assertNoXss(self, route):
        hits = self.render(route)
        self.assertIn('control', hits, 'collector not reachable from the browser; test inconclusive')
        executed = sorted(set(h for h in hits if h not in ('control', 'rendered-avatar')))
        self.assertEqual(executed, [], 'payloads executed on #/{}: {}'.format(route, executed))
        return hits

    def test_map_page(self):
        self.assertNoXss('map/p-xss')

    def test_projects_page(self):
        self.assertNoXss('projects')

    def test_project_page(self):
        self.assertNoXss('project/view/x/p-xss')

    def test_file_page(self):
        self.assertNoXss('project/edit/x/p-xss/layer/l-xss')

    def test_admin_users_page(self):
        self.assertNoXss('admin')

    def test_profile_page(self):
        hits = self.assertNoXss('user')
        self.assertIn('rendered-avatar', hits, 'the app did not render inside the frame; test inconclusive')

    def test_hostile_route_parameters(self):
        b = self.beacon('route-param')
        self.assertNoXss('project/edit/' + quote('<img src=x onerror="fetch(\'{}\')">'.format(b), safe='') + '/p-xss/layer/l-xss')


if __name__ == '__main__':
    unittest.main()
