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
        self.csp_reports = []
        collector = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get('Content-Length') or 0))
                if urlparse(self.path).path == '/csp':
                    try:
                        collector.csp_reports.append(json.loads(body.decode('utf-8')).get('csp-report', {}))
                    except ValueError:
                        collector.csp_reports.append({'raw': body[:200]})
                self._send(b'', 'text/plain')

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
        # A permissive CSP so that this class tests output escaping on its own; the real policy
        # would block the payloads anyway and hide escaping bugs (see CspBrowserTests).
        cls.server_env = {'NGIS_CSP': "default-src * data: blob: 'unsafe-inline' 'unsafe-eval'; "
                                      'frame-ancestors http://127.0.0.1:{}'.format(cls.collector.port)}
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
        prepare_firefox_profile(cls.profile, 'xss-session-token')

    def render(self, route):
        self.collector.hits.clear()
        render(self.profile, self.port, self.collector, route)
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


def prepare_firefox_profile(profile, token):
    """Creates a Firefox profile with a session cookie for 127.0.0.1."""
    # First run creates cookies.sqlite; then the session cookie is inserted.
    subprocess.run([FIREFOX, '--headless', '-no-remote', '-profile', profile, '--screenshot',
                    os.path.join(profile, 'init.png'), 'about:blank'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
    conn = sqlite3.connect(os.path.join(profile, 'cookies.sqlite'))
    columns = {r[1] for r in conn.execute('PRAGMA table_info(moz_cookies)')}
    now_us = int(time.time() * 1e6)
    row = {
        'name': 'ngis_session', 'value': token, 'host': '127.0.0.1', 'path': '/',
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


def render(profile, port, collector, route):
    """Opens #/route of the app inside the collector's waiting page in headless Firefox."""
    app_url = 'http://127.0.0.1:{}/#/{}'.format(port, route)
    page = 'http://127.0.0.1:{}/page?u={}'.format(collector.port, quote(app_url, safe=''))
    subprocess.run([FIREFOX, '--headless', '-no-remote', '-profile', profile, '--window-size', '1280,800',
                    '--screenshot', os.path.join(profile, 'shot.png'), page],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)


@unittest.skipUnless(FIREFOX, 'Firefox is not installed')
class CspBrowserTests(ServerTestCase):
    """Every page must work under the real Content-Security-Policy without a single violation."""

    @classmethod
    def setUpClass(cls):
        cls.collector = Collector()
        cls.server_env = {
            'NGIS_FRAME_ANCESTORS': 'http://127.0.0.1:{}'.format(cls.collector.port),
            'NGIS_CSP_REPORT_URI': 'http://127.0.0.1:{}/csp'.format(cls.collector.port),
        }
        super().setUpClass()
        cls.profile = tempfile.mkdtemp(prefix='ngis-ff-')
        expires = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        conn = sqlite3.connect(cls.db_path)
        conn.execute('INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)', ('csp-session-token', 'u-admin', expires))
        conn.commit()
        conn.close()
        prepare_firefox_profile(cls.profile, 'csp-session-token')

    @classmethod
    def tearDownClass(cls):
        cls.collector.close()
        shutil.rmtree(cls.profile, ignore_errors=True)
        super().tearDownClass()

    def set_photo(self, url):
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE users SET photo_url = ? WHERE id = 'u-admin'", (url,))
        conn.commit()
        conn.close()

    def render_page(self, route, expected_requests):
        """Renders a page; returns CSP reports. `expected_requests` must show up in the server log."""
        self.collector.hits.clear()
        self.collector.csp_reports.clear()
        with open(self.server_log_path) as f:
            f.seek(0, 2)
            render(self.profile, self.port, self.collector, route)
            time.sleep(0.5)
            log = f.read()
        self.assertIn('control', self.collector.hits, 'collector not reachable; test inconclusive')
        for request in expected_requests:
            self.assertIn(request, log, 'page #/{} did not load {}; test inconclusive'.format(route, request))
        return [{k: r.get(k) for k in ('violated-directive', 'blocked-uri', 'source-file', 'line-number')}
                for r in self.collector.csp_reports]

    def assertNoViolations(self, route, expected_requests):
        reports = self.render_page(route, expected_requests)
        self.assertEqual(reports, [], 'CSP violations on #/{}'.format(route))

    def test_reporting_works(self):
        """Positive control: a plain-http photo URL is blocked by img-src and must be reported."""
        self.set_photo('http://127.0.0.1:{}/hit?where=insecure-photo'.format(self.collector.port))
        try:
            reports = self.render_page('user', ['GET /api/me'])
        finally:
            self.set_photo(None)
        self.assertNotIn('insecure-photo', self.collector.hits, 'img-src did not block a plain-http image')
        self.assertTrue(any((r.get('violated-directive') or '').startswith('img-src') for r in reports), reports)

    def test_map_page(self):
        self.assertNoViolations('map/p-alpha', ['GET /api/projects HTTP', 'GET /api/projects/p-alpha/layers HTTP'])

    def test_projects_page(self):
        # Also proves the self-hosted Roboto font (Cyrillic subset) is actually loaded.
        self.assertNoViolations('projects', ['GET /api/projects HTTP', 'GET /views/projects.handlebars',
                                             'GET /libs/roboto-5.3.0/files/roboto-cyrillic-400-normal.woff2',
                                             'GET /libs/openlayers-10.11.0/ol.js', 'GET /libs/bootstrap-5.3.3/bootstrap.bundle.min.js'])

    def test_project_page(self):
        self.assertNoViolations('project/view/alpha/p-alpha', ['GET /api/projects/p-alpha HTTP', 'GET /views/view-project.handlebars'])

    def test_file_page(self):
        self.assertNoViolations('project/edit/alpha/p-alpha/layer/l-alpha',
                                ['GET /api/projects/p-alpha/layers/l-alpha', 'GET /views/edit-project.handlebars'])

    def test_admin_page(self):
        self.assertNoViolations('admin', ['GET /api/admin/users', 'GET /views/admin.handlebars'])

    def test_profile_page(self):
        self.assertNoViolations('user', ['GET /api/me', 'GET /views/user.handlebars'])


if __name__ == '__main__':
    unittest.main()
