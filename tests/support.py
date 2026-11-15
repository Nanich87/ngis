"""Shared helpers for the nGIS test suite.

Each test class gets its own server process on a free port with a fresh temporary
database, so tests never touch data/ngis.db.
"""
import http.client
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SERVER_DIR = os.path.join(ROOT, 'server')
sys.path.insert(0, SERVER_DIR)

import db  # noqa: E402  (server/db.py)

PASSWORD = 'correct-horse-1'

# email -> (id, is_admin, can_read, can_write, has_password)
USERS = {
    'admin@test.bg': ('u-admin', 1, 1, 1, True),
    'writer@test.bg': ('u-writer', 0, 1, 1, True),
    'reader@test.bg': ('u-reader', 0, 1, 0, True),
    'nobody@test.bg': ('u-nobody', 0, 0, 0, True),
    'imported@test.bg': ('u-imported', 0, 1, 0, False),
}

SAMPLE_GEOJSON = json.dumps({
    'type': 'FeatureCollection',
    'features': [{'type': 'Feature', 'properties': {'name': 'Точка'},
                  'geometry': {'type': 'Point', 'coordinates': [23.32, 42.69]}}]
})


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def seed(path):
    conn = db.init_db(path)
    password_hash = db.hash_password(PASSWORD)
    for email, (uid, is_admin, can_read, can_write, has_password) in USERS.items():
        conn.execute('INSERT INTO users (id, email, password_hash, is_admin, can_read, can_write) '
                     'VALUES (?, ?, ?, ?, ?, ?)',
                     (uid, email, password_hash if has_password else None, is_admin, can_read, can_write))
    conn.execute("INSERT INTO projects (id, name, year) VALUES ('p-alpha', 'Alpha', '2020'), ('p-beta', 'Beta', '2021')")
    conn.execute("INSERT INTO layers (id, project_id, title, content) VALUES (?, 'p-alpha', 'alpha.geojson', ?)",
                 ('l-alpha', SAMPLE_GEOJSON))
    conn.execute("INSERT INTO layers (id, project_id, title, content) VALUES (?, 'p-beta', 'beta.geojson', ?)",
                 ('l-beta', SAMPLE_GEOJSON))
    conn.commit()
    conn.close()


class Response:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = headers
        self.body = body

    @property
    def text(self):
        return self.body.decode('utf-8', 'replace')

    @property
    def json(self):
        return json.loads(self.body.decode('utf-8'))

    def header(self, name):
        for key, value in self.headers:
            if key.lower() == name.lower():
                return value
        return None

    def headers_all(self, name):
        return [v for k, v in self.headers if k.lower() == name.lower()]


class Client:
    """Minimal HTTP client that keeps the session cookie."""

    def __init__(self, port, token=None):
        self.port = port
        self.token = token

    def request(self, method, path, body=None, headers=None, raw_body=None, timeout=10):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=timeout)
        headers = dict(headers or {})
        if self.token is not None and 'Cookie' not in headers:
            headers['Cookie'] = 'ngis_session=' + self.token
        data = raw_body
        if body is not None:
            data = json.dumps(body).encode('utf-8')
            headers.setdefault('Content-Type', 'application/json')
        conn.request(method, path, body=data, headers=headers)
        r = conn.getresponse()
        resp = Response(r.status, r.getheaders(), r.read())
        conn.close()
        for value in resp.headers_all('Set-Cookie'):
            if value.startswith('ngis_session='):
                self.token = value.split(';', 1)[0].split('=', 1)[1] or None
        return resp

    def get(self, path, **kw):
        return self.request('GET', path, **kw)

    def post(self, path, body=None, **kw):
        return self.request('POST', path, body=body if body is not None else {}, **kw)

    def patch(self, path, body=None, **kw):
        return self.request('PATCH', path, body=body if body is not None else {}, **kw)

    def delete(self, path, **kw):
        return self.request('DELETE', path, **kw)

    def login(self, email, password=PASSWORD):
        r = self.post('/api/auth/login', {'email': email, 'password': password})
        if r.status != 200:
            raise AssertionError('login failed for {}: {} {}'.format(email, r.status, r.text))
        return self


def raw_request(port, data, timeout=5):
    """Send raw bytes; returns (status_line, full_response_text) or (None, '') on timeout."""
    with socket.create_connection(('127.0.0.1', port), timeout=timeout) as s:
        s.sendall(data)
        chunks = []
        try:
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
        except socket.timeout:
            if not chunks:
                return None, ''
        text = b''.join(chunks).decode('utf-8', 'replace')
        return text.split('\r\n', 1)[0], text


class ServerTestCase(unittest.TestCase):
    """Starts one server per test class."""

    # Extra environment variables for the server process.
    server_env = {}

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.TemporaryDirectory()
        cls.db_path = os.path.join(cls.tmpdir.name, 'test.db')
        seed(cls.db_path)
        cls.port = free_port()
        env = dict(os.environ, NGIS_DB=cls.db_path, PYTHONDONTWRITEBYTECODE='1', **cls.server_env)
        cls.server_log = open(os.path.join(cls.tmpdir.name, 'server.log'), 'w')
        cls.proc = subprocess.Popen([sys.executable, os.path.join(SERVER_DIR, 'app.py'), '--port', str(cls.port)],
                                    env=env, stdout=cls.server_log, stderr=subprocess.STDOUT)
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                socket.create_connection(('127.0.0.1', cls.port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.05)
        else:
            raise RuntimeError('server did not start')

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(5)
        cls.server_log.close()
        cls.tmpdir.cleanup()

    def client(self, email=None):
        c = Client(self.port)
        return c.login(email) if email else c

    def db(self):
        return db.connect(self.db_path)

    def assertNotServerError(self, resp, msg=None):
        self.assertLess(resp.status, 500, msg or 'server error: {} {}'.format(resp.status, resp.text[:200]))
