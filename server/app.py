"""nGIS backend: serves the static frontend and a JSON API backed by SQLite.

Only the Python standard library is used.

    python3 server/app.py [--host 127.0.0.1] [--port 8000]
"""
import argparse
import base64
import binascii
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

import cad
import gpx
import db
import i18n
from i18n import _

PUBLIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'public'))
SESSION_COOKIE = 'ngis_session'
SESSION_TTL = timedelta(days=14)
MAX_BODY = 64 * 1024 * 1024  # GeoJSON files can be large
SOCKET_TIMEOUT = 30            # seconds; stops clients from holding a thread open forever

# Field length limits
MAX_EMAIL = 254
MAX_PASSWORD = 1024
MAX_DISPLAY_NAME = 100
MAX_URL = 2048
MAX_TITLE = 255
MIN_PASSWORD = 10              # passwords chosen by users

# Brute-force protection
LOGIN_MAX_FAILURES = 10            # per email + IP
LOGIN_IP_MAX_FAILURES = 50         # per IP, across all emails
PASSWORD_MAX_FAILURES = 10         # wrong "current password" per user
FAILURE_WINDOW = 15 * 60           # seconds

def _env_header_value(name, default=''):
    # Environment values end up in a header: no CR/LF.
    return os.environ.get(name, default).replace('\r', '').replace('\n', '').strip()


# Reverse proxies (e.g. nginx on 127.0.0.1) whose X-Forwarded-For header is trusted.
# Comma-separated IP addresses; empty = use the TCP peer address only.
TRUSTED_PROXIES = {ip.strip() for ip in os.environ.get('NGIS_TRUSTED_PROXIES', '').split(',') if ip.strip()}

# Who may embed the site in a frame (CSP source list). Default: nobody (clickjacking protection).
FRAME_ANCESTORS = _env_header_value('NGIS_FRAME_ANCESTORS', "'none'").replace(';', '')


def build_content_security_policy():
    override = _env_header_value('NGIS_CSP')
    if override:
        return override
    directives = [
        "default-src 'self'",
        # All scripts, styles and fonts are served locally (public/libs).
        # Handlebars compiles templates at runtime with Function(), hence 'unsafe-eval'.
        # No 'unsafe-inline': injected markup cannot run scripts.
        "script-src 'self' 'unsafe-eval'",
        "style-src 'self'",
        "font-src 'self'",
        # Map tiles (OpenStreetMap, Esri), user photo URLs, Bootstrap's data: icons.
        "img-src 'self' data: blob: https:",
        "connect-src 'self'",
        "worker-src 'self' blob:",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        'frame-ancestors ' + FRAME_ANCESTORS,
    ]
    report_uri = _env_header_value('NGIS_CSP_REPORT_URI').replace(';', '')
    if report_uri:
        directives.append('report-uri ' + report_uri)
    return '; '.join(directives)


CONTENT_SECURITY_POLICY = build_content_security_policy()

PROJECT_NAME_RE = re.compile(r'[a-zA-Z0-9-]{3,20}')
PROJECT_YEAR_RE = re.compile(r'(19|20)[0-9]{2}')
EMAIL_RE = re.compile(r'[^@\s]+@[^@\s]+\.[^@\s]+')
HTTP_URL_RE = re.compile(r'https?://[^\s"\'<>`\\]+', re.IGNORECASE)
SESSION_TOKEN_RE = re.compile(r'[A-Za-z0-9_-]{1,128}')
GEOJSON_TYPES = {'FeatureCollection', 'Feature', 'Point', 'MultiPoint', 'LineString', 'MultiLineString',
                 'Polygon', 'MultiPolygon', 'GeometryCollection'}

# Verified against when the email is unknown, so both cases take the same time.
DUMMY_PASSWORD_HASH = db.hash_password(secrets.token_urlsafe(16))


class ApiError(Exception):
    """message: an i18n Message, translated when sent. field: the request field the error is about."""

    def __init__(self, status, message, headers=None, field=None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.headers = headers or {}
        self.field = field


class FailureLimiter:
    """Counts failures per key in a sliding window (in memory, per process)."""

    def __init__(self, max_failures, window):
        self.max_failures = max_failures
        self.window = window
        self.failures = {}
        self.lock = threading.Lock()

    def _prune(self, key, now):
        queue = self.failures.get(key)
        while queue and queue[0] <= now - self.window:
            queue.popleft()
        if queue is not None and not queue:
            del self.failures[key]
        return self.failures.get(key)

    def retry_after(self, key):
        """Seconds until the key may try again, or 0 if it is not blocked."""
        now = time.monotonic()
        with self.lock:
            queue = self._prune(key, now)
            if queue is None or len(queue) < self.max_failures:
                return 0
            return int(queue[0] + self.window - now) + 1

    def fail(self, key):
        now = time.monotonic()
        with self.lock:
            if len(self.failures) > 100000:  # bound memory under attack
                for k in list(self.failures):
                    self._prune(k, now)
            self.failures.setdefault(key, deque()).append(now)

    def reset(self, key):
        with self.lock:
            self.failures.pop(key, None)


login_limiter = FailureLimiter(LOGIN_MAX_FAILURES, FAILURE_WINDOW)
login_ip_limiter = FailureLimiter(LOGIN_IP_MAX_FAILURES, FAILURE_WINDOW)
password_limiter = FailureLimiter(PASSWORD_MAX_FAILURES, FAILURE_WINDOW)


def check_limit(limiter, key):
    seconds = limiter.retry_after(key)
    if seconds:
        minutes = max(1, (seconds + 59) // 60)
        raise ApiError(HTTPStatus.TOO_MANY_REQUESTS,
                       _('Твърде много неуспешни опити. Опитайте отново след {minutes} мин.', minutes=minutes),
                       {'Retry-After': str(seconds)})


def now_utc():
    return datetime.now(timezone.utc)


def user_to_json(row):
    return {
        'uid': row['id'],
        'email': row['email'],
        'displayName': row['display_name'],
        'photoURL': row['photo_url'],
        'isAdmin': bool(row['is_admin']),
        'canRead': bool(row['can_read']),
        'canWrite': bool(row['can_write']),
    }


# --------------------------------------------------------------------------- routing

ROUTES = []


def route(method, pattern):
    regex = re.compile('^' + re.sub(r':(\w+)', r'(?P<\1>[^/]+)', pattern) + '$')

    def decorator(fn):
        ROUTES.append((method, regex, fn))
        return fn
    return decorator


class Request:
    def __init__(self, handler, conn, params, body):
        self.handler = handler
        self.conn = conn
        self.params = params
        self.body = body
        self.new_cookie = None
        self._user = False

    @property
    def lang(self):
        return self.handler.lang

    @property
    def user(self):
        if self._user is False:
            self._user = None
            token = self.handler.session_token()
            if token:
                row = self.conn.execute(
                    'SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id '
                    'WHERE s.token = ? AND s.expires_at > ?',
                    (token, now_utc().isoformat())).fetchone()
                self._user = row
        return self._user

    def require_user(self):
        if self.user is None:
            raise ApiError(HTTPStatus.UNAUTHORIZED, _('Не сте влезли в системата!'))
        return self.user

    def require_read(self):
        user = self.require_user()
        if not (user['can_read'] or user['is_admin']):
            raise ApiError(HTTPStatus.FORBIDDEN, _('Нямате права за четене!'))
        return user

    def require_write(self):
        user = self.require_user()
        if not (user['can_write'] or user['is_admin']):
            raise ApiError(HTTPStatus.FORBIDDEN, _('Нямате права за запис!'))
        return user

    def require_admin(self):
        user = self.require_user()
        if not user['is_admin']:
            raise ApiError(HTTPStatus.FORBIDDEN, _('Нямате администраторски права!'))
        return user

    def field(self, name, required=True, max_length=None):
        value = self.body.get(name) if isinstance(self.body, dict) else None
        if value is None and not required:
            return None
        if not isinstance(value, str):
            raise ApiError(HTTPStatus.BAD_REQUEST, _('Липсва поле: {name}', name=name) if value is None
                           else _('Невалидна стойност: {name}', name=name))
        if required and value == '':
            raise ApiError(HTTPStatus.BAD_REQUEST, _('Липсва поле: {name}', name=name))
        if max_length is not None and len(value) > max_length:
            raise ApiError(HTTPStatus.BAD_REQUEST, _('Твърде дълга стойност: {name}', name=name))
        return value

    @property
    def client_ip(self):
        return self.handler.client_ip()


# --------------------------------------------------------------------------- auth

def start_session(req, user_id):
    token = secrets.token_urlsafe(32)
    req.conn.execute('DELETE FROM sessions WHERE expires_at <= ?', (now_utc().isoformat(),))
    req.conn.execute('INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)',
                     (token, user_id, (now_utc() + SESSION_TTL).isoformat()))
    req.new_cookie = (token, int(SESSION_TTL.total_seconds()))


@route('POST', '/api/auth/login')
def login(req):
    email = req.field('email', max_length=MAX_EMAIL).strip()
    password = req.field('password', max_length=MAX_PASSWORD)
    key = (req.client_ip, email.lower())
    check_limit(login_ip_limiter, req.client_ip)
    check_limit(login_limiter, key)
    row = req.conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    # Always run the hash so unknown emails take as long as wrong passwords.
    stored = row['password_hash'] if row is not None and row['password_hash'] else DUMMY_PASSWORD_HASH
    valid = db.verify_password(password, stored) and row is not None and row['password_hash'] is not None
    if not valid:
        login_limiter.fail(key)
        login_ip_limiter.fail(req.client_ip)
        raise ApiError(HTTPStatus.UNAUTHORIZED, _('Грешен Email адрес или парола!'))
    login_limiter.reset(key)
    start_session(req, row['id'])
    return HTTPStatus.OK, user_to_json(row)


@route('POST', '/api/auth/logout')
def logout(req):
    token = req.handler.session_token()
    if token:
        req.conn.execute('DELETE FROM sessions WHERE token = ?', (token,))
    req.new_cookie = ('', 0)
    return HTTPStatus.OK, {'ok': True}


@route('GET', '/api/me')
def me(req):
    return HTTPStatus.OK, user_to_json(req.require_user())


@route('PATCH', '/api/me')
def update_me(req):
    user = req.require_user()
    display_name = (req.field('displayName', required=False, max_length=MAX_DISPLAY_NAME) or '').strip()
    photo_url = (req.field('photoURL', required=False, max_length=MAX_URL) or '').strip()
    if photo_url and not HTTP_URL_RE.fullmatch(photo_url):
        raise ApiError(HTTPStatus.BAD_REQUEST, _('Адресът на снимката трябва да започва с http:// или https://'))
    req.conn.execute('UPDATE users SET display_name = ?, photo_url = ? WHERE id = ?',
                     (display_name or None, photo_url or None, user['id']))
    row = req.conn.execute('SELECT * FROM users WHERE id = ?', (user['id'],)).fetchone()
    return HTTPStatus.OK, user_to_json(row)


@route('POST', '/api/me/password')
def change_password(req):
    user = req.require_user()
    current = req.field('currentPassword', max_length=MAX_PASSWORD)
    new = req.field('newPassword', max_length=MAX_PASSWORD)
    check_limit(password_limiter, user['id'])
    if not db.verify_password(current, user['password_hash']):
        password_limiter.fail(user['id'])
        raise ApiError(HTTPStatus.BAD_REQUEST, _('Текущата парола е грешна!'), field='currentPassword')
    password_limiter.reset(user['id'])
    if len(new) < MIN_PASSWORD:
        raise ApiError(HTTPStatus.BAD_REQUEST, _('Новата парола трябва да е поне {min} символа!', min=MIN_PASSWORD))
    if new == current:
        raise ApiError(HTTPStatus.BAD_REQUEST, _('Новата парола съвпада с текущата!'))
    req.conn.execute('UPDATE users SET password_hash = ? WHERE id = ?', (db.hash_password(new), user['id']))
    # Sign out every other session of this user; keep the current one.
    req.conn.execute('DELETE FROM sessions WHERE user_id = ? AND token != ?',
                     (user['id'], req.handler.session_token()))
    return HTTPStatus.OK, {'ok': True}


# --------------------------------------------------------------------------- admin

@route('GET', '/api/admin/users')
def list_users(req):
    req.require_admin()
    rows = req.conn.execute('SELECT * FROM users ORDER BY created_at, email').fetchall()
    result = []
    for row in rows:
        user = user_to_json(row)
        user['createdAt'] = row['created_at']
        user['hasPassword'] = row['password_hash'] is not None
        result.append(user)
    return HTTPStatus.OK, result


def generate_password():
    # 16 URL-safe characters (~96 bits); shown once to the admin, who passes it on.
    return secrets.token_urlsafe(12)


def get_user_or_404(req, uid):
    row = req.conn.execute('SELECT * FROM users WHERE id = ?', (uid,)).fetchone()
    if row is None:
        raise ApiError(HTTPStatus.NOT_FOUND, _('Няма такъв потребител!'))
    return row


def bool_field(req, name):
    value = req.body.get(name, False)
    if not isinstance(value, bool):
        raise ApiError(HTTPStatus.BAD_REQUEST, _('Правата трябва да са true или false!'))
    return value


@route('POST', '/api/admin/users')
def create_user(req):
    """Accounts are created by admins only (there is no public sign-up)."""
    req.require_admin()
    email = req.field('email', max_length=MAX_EMAIL).strip()
    display_name = (req.field('displayName', required=False, max_length=MAX_DISPLAY_NAME) or '').strip()
    if not EMAIL_RE.fullmatch(email):
        raise ApiError(HTTPStatus.BAD_REQUEST, _('Невалиден Email адрес!'))
    can_read, can_write, is_admin = bool_field(req, 'canRead'), bool_field(req, 'canWrite'), bool_field(req, 'isAdmin')
    password = generate_password()
    uid = db.new_id()
    try:
        req.conn.execute('INSERT INTO users (id, email, password_hash, display_name, is_admin, can_read, can_write) '
                         'VALUES (?, ?, ?, ?, ?, ?, ?)',
                         (uid, email, db.hash_password(password), display_name or None,
                          int(is_admin), int(can_read or is_admin), int(can_write or is_admin)))
    except sqlite3.IntegrityError:
        raise ApiError(HTTPStatus.CONFLICT, _('Вече съществува потребител с този Email адрес!'))
    user = user_to_json(get_user_or_404(req, uid))
    return HTTPStatus.CREATED, {'user': user, 'password': password}


@route('POST', '/api/admin/users/:uid/password')
def reset_user_password(req):
    """Sets a new random password (forgotten passwords, imported users) and signs the user out."""
    req.require_admin()
    row = get_user_or_404(req, req.params['uid'])
    password = generate_password()
    req.conn.execute('UPDATE users SET password_hash = ? WHERE id = ?', (db.hash_password(password), row['id']))
    req.conn.execute('DELETE FROM sessions WHERE user_id = ?', (row['id'],))
    password_limiter.reset(row['id'])
    return HTTPStatus.OK, {'password': password}


@route('DELETE', '/api/admin/users/:uid')
def delete_user(req):
    admin = req.require_admin()
    row = get_user_or_404(req, req.params['uid'])
    if row['id'] == admin['id']:
        raise ApiError(HTTPStatus.BAD_REQUEST, _('Не можете да изтриете собствения си акаунт!'))
    req.conn.execute('DELETE FROM users WHERE id = ?', (row['id'],))  # sessions cascade
    return HTTPStatus.OK, {'ok': True}


@route('PATCH', '/api/admin/users/:uid')
def update_user_rights(req):
    admin = req.require_admin()
    row = req.conn.execute('SELECT * FROM users WHERE id = ?', (req.params['uid'],)).fetchone()
    if row is None:
        raise ApiError(HTTPStatus.NOT_FOUND, _('Няма такъв потребител!'))
    columns = {'canRead': 'can_read', 'canWrite': 'can_write', 'isAdmin': 'is_admin'}
    if any(key in req.body and not isinstance(req.body[key], bool) for key in columns):
        raise ApiError(HTTPStatus.BAD_REQUEST, _('Правата трябва да са true или false!'))
    changes = {col: 1 if req.body[key] else 0 for key, col in columns.items() if key in req.body}
    if not changes:
        raise ApiError(HTTPStatus.BAD_REQUEST, _('Няма промени!'))
    if row['id'] == admin['id'] and changes.get('is_admin') == 0:
        raise ApiError(HTTPStatus.BAD_REQUEST, _('Не можете да премахнете собствените си администраторски права!'))
    sets = ', '.join('{} = ?'.format(c) for c in changes)
    req.conn.execute('UPDATE users SET {} WHERE id = ?'.format(sets), list(changes.values()) + [row['id']])
    row = req.conn.execute('SELECT * FROM users WHERE id = ?', (row['id'],)).fetchone()
    return HTTPStatus.OK, user_to_json(row)


# --------------------------------------------------------------------------- projects

# Number of features in a FeatureCollection (NULL for anything else / invalid JSON).
FEATURE_COUNT_SQL = ("CASE WHEN json_valid(content) AND json_type(content, '$.features') = 'array' "
                     "THEN json_array_length(content, '$.features') END")


def get_project_or_404(req, pid):
    row = req.conn.execute('SELECT * FROM projects WHERE id = ?', (pid,)).fetchone()
    if row is None:
        raise ApiError(HTTPStatus.NOT_FOUND, _('Няма такъв обект!'))
    return row


@route('GET', '/api/projects')
def list_projects(req):
    req.require_read()
    rows = req.conn.execute(
        'SELECT p.id, p.name, p.year, p.created_at, '
        '(SELECT COUNT(*) FROM layers l WHERE l.project_id = p.id) AS layer_count '
        'FROM projects p ORDER BY p.created_at, p.id').fetchall()
    return HTTPStatus.OK, [dict(r) for r in rows]


@route('POST', '/api/projects')
def create_project(req):
    req.require_admin()
    name = req.field('name').strip()
    year = req.field('year').strip()
    if not PROJECT_NAME_RE.fullmatch(name):
        raise ApiError(HTTPStatus.BAD_REQUEST, _('Невалидно име на обект!'))
    if not PROJECT_YEAR_RE.fullmatch(year):
        raise ApiError(HTTPStatus.BAD_REQUEST, _('Невалидна година!'))
    pid = db.new_id()
    req.conn.execute('INSERT INTO projects (id, name, year) VALUES (?, ?, ?)', (pid, name, year))
    return HTTPStatus.CREATED, {'id': pid, 'name': name, 'year': year}


@route('GET', '/api/projects/:pid')
def get_project(req):
    req.require_read()
    project = get_project_or_404(req, req.params['pid'])
    result = dict(project)
    result['layers'] = [dict(l) for l in req.conn.execute(
        'SELECT id, title, created_at, length(CAST(content AS BLOB)) AS size, ' + FEATURE_COUNT_SQL + ' AS feature_count '
        'FROM layers WHERE project_id = ? ORDER BY created_at, id', (project['id'],)).fetchall()]
    return HTTPStatus.OK, result


@route('PATCH', '/api/projects/:pid')
def rename_project(req):
    req.require_admin()
    project = get_project_or_404(req, req.params['pid'])
    name = req.field('name').strip()
    if not PROJECT_NAME_RE.fullmatch(name):
        raise ApiError(HTTPStatus.BAD_REQUEST, _('Невалидно име на обект!'))
    req.conn.execute('UPDATE projects SET name = ? WHERE id = ?', (name, project['id']))
    return HTTPStatus.OK, {'id': project['id'], 'name': name, 'year': project['year']}


@route('DELETE', '/api/projects/:pid')
def delete_project(req):
    req.require_admin()
    get_project_or_404(req, req.params['pid'])
    req.conn.execute('DELETE FROM projects WHERE id = ?', (req.params['pid'],))  # layers cascade
    return HTTPStatus.OK, {'ok': True}


@route('GET', '/api/projects/:pid/layers')
def list_layers(req):
    req.require_read()
    get_project_or_404(req, req.params['pid'])
    rows = req.conn.execute('SELECT id, title, content FROM layers WHERE project_id = ? ORDER BY created_at, id',
                            (req.params['pid'],)).fetchall()
    return HTTPStatus.OK, [dict(r) for r in rows]


@route('POST', '/api/projects/:pid/layers')
def add_layer(req):
    req.require_write()
    get_project_or_404(req, req.params['pid'])
    title = req.field('title', max_length=MAX_TITLE).strip()
    content = req.field('content')
    if not title:
        raise ApiError(HTTPStatus.BAD_REQUEST, _('Липсва поле: {name}', name='title'))
    try:
        geojson = json.loads(content)
    except (ValueError, RecursionError):
        geojson = None
    if not isinstance(geojson, dict) or not isinstance(geojson.get('type'), str) or geojson['type'] not in GEOJSON_TYPES:
        raise ApiError(HTTPStatus.BAD_REQUEST, _('Файлът не е валиден GeoJSON!'))
    lid = db.new_id()
    req.conn.execute('INSERT INTO layers (id, project_id, title, content) VALUES (?, ?, ?, ?)',
                     (lid, req.params['pid'], title, content))
    return HTTPStatus.CREATED, {'id': lid, 'title': title}


def add_converted_layer(req, converter, error_class):
    """File in base64 ("data") -> converted to GeoJSON by converter(bytes) and stored as a layer."""
    req.require_write()
    get_project_or_404(req, req.params['pid'])
    title = req.field('title', max_length=MAX_TITLE).strip()
    if not title:
        raise ApiError(HTTPStatus.BAD_REQUEST, _('Липсва поле: {name}', name='title'))
    try:
        data = base64.b64decode(req.field('data'), validate=True)
    except (binascii.Error, ValueError):
        raise ApiError(HTTPStatus.BAD_REQUEST, _('Невалидна стойност: {name}', name='data'))
    try:
        geojson, info = converter(data)
    except error_class as e:
        raise ApiError(HTTPStatus.BAD_REQUEST, e.args[0])
    lid = db.new_id()
    req.conn.execute('INSERT INTO layers (id, project_id, title, content) VALUES (?, ?, ?, ?)',
                     (lid, req.params['pid'], title, json.dumps(geojson, ensure_ascii=False, separators=(',', ':'))))
    info = dict(info, warnings=[i18n.translate(w, req.lang) for w in info['warnings']])
    if 'encoding' in info:
        info['encoding'] = i18n.translate(info['encoding'], req.lang)
    return HTTPStatus.CREATED, dict(info, id=lid, title=title)


@route('POST', '/api/projects/:pid/layers/cad')
def add_cad_layer(req):
    """CAD file -> GeoJSON layer in BGS2005."""
    return add_converted_layer(req, cad.convert, cad.CadError)


@route('POST', '/api/projects/:pid/layers/gpx')
def add_gpx_layer(req):
    """GPX file -> GeoJSON layer in WGS84."""
    return add_converted_layer(req, gpx.convert, gpx.GpxError)


def get_layer_or_404(req):
    row = req.conn.execute('SELECT id, title, content, created_at FROM layers WHERE id = ? AND project_id = ?',
                           (req.params['lid'], req.params['pid'])).fetchone()
    if row is None:
        raise ApiError(HTTPStatus.NOT_FOUND, _('Няма такъв файл!'))
    return row


@route('GET', '/api/projects/:pid/layers/:lid')
def get_layer(req):
    req.require_read()
    return HTTPStatus.OK, dict(get_layer_or_404(req))


@route('DELETE', '/api/projects/:pid/layers/:lid')
def delete_layer(req):
    req.require_write()
    get_layer_or_404(req)
    req.conn.execute('DELETE FROM layers WHERE id = ?', (req.params['lid'],))
    return HTTPStatus.OK, {'ok': True}


# --------------------------------------------------------------------------- HTTP handler

class Handler(SimpleHTTPRequestHandler):
    timeout = SOCKET_TIMEOUT

    def version_string(self):
        # Do not advertise Python / http.server versions.
        return 'nGIS'

    # Always declare UTF-8 for text assets so Cyrillic is decoded correctly.
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        '.html': 'text/html; charset=utf-8',
        '.handlebars': 'text/html; charset=utf-8',
        '.js': 'application/javascript; charset=utf-8',
        '.css': 'text/css; charset=utf-8',
        '.json': 'application/json; charset=utf-8',
        '.svg': 'image/svg+xml',
        '.woff': 'font/woff',
        '.woff2': 'font/woff2',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    def session_token(self):
        try:
            cookie = SimpleCookie(self.headers.get('Cookie', ''))
        except Exception:
            return None
        morsel = cookie.get(SESSION_COOKIE)
        # Tokens we issue are URL-safe base64; anything else cannot be a session.
        if morsel is None or not SESSION_TOKEN_RE.fullmatch(morsel.value):
            return None
        return morsel.value

    def client_ip(self):
        """The real client address: behind a trusted proxy, the last untrusted hop in X-Forwarded-For."""
        peer = self.client_address[0]
        if peer not in TRUSTED_PROXIES:
            return peer
        headers = getattr(self, 'headers', None)  # missing when the request line itself was malformed
        hops = [h.strip() for h in ((headers and headers.get('X-Forwarded-For')) or '').split(',') if h.strip()]
        for hop in reversed(hops):
            if hop not in TRUSTED_PROXIES:
                return hop[:64]
        return peer

    def address_string(self):
        # Used in the access log.
        return self.client_ip()

    def list_directory(self, path):
        # No directory listings.
        self.send_error(HTTPStatus.NOT_FOUND)
        return None

    def do_GET(self):
        if self.path.startswith('/api/'):
            return self.handle_api('GET')
        # SPA fallback (same as the old firebase.json rewrite).
        path = self.translate_path(self.path)
        if not os.path.exists(path):
            self.path = '/index.html'
        return super().do_GET()

    def end_headers(self):
        # Static files: always revalidate (cheap 304 via Last-Modified) so updates show up immediately.
        if not self.path.startswith('/api/'):
            self.send_header('Cache-Control', 'no-cache')
        self.send_header('X-Content-Type-Options', 'nosniff')
        # Browsers that support CSP use frame-ancestors and ignore X-Frame-Options.
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', CONTENT_SECURITY_POLICY)
        self.send_header('Referrer-Policy', 'same-origin')
        super().end_headers()

    def do_HEAD(self):
        if self.path.startswith('/api/'):
            return self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)
        return super().do_HEAD()

    def do_POST(self):
        self.handle_api('POST')

    def do_PATCH(self):
        self.handle_api('PATCH')

    def do_DELETE(self):
        self.handle_api('DELETE')

    def handle_api(self, method):
        path = unquote(urlparse(self.path).path)
        conn = None
        try:
            if not path.startswith('/api/'):
                raise ApiError(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed')
            body = self.read_json_body(method)
            for m, regex, fn in ROUTES:
                match = regex.match(path)
                if match and m == method:
                    conn = db.connect()
                    req = Request(self, conn, match.groupdict(), body)
                    status, payload = fn(req)
                    conn.commit()
                    return self.send_json(status, payload, req.new_cookie)
            raise ApiError(HTTPStatus.NOT_FOUND, 'Not found')
        except ApiError as e:
            if conn is not None:
                conn.rollback()
            error = {'error': i18n.translate(e.message, self.lang)}
            if e.field:
                error['field'] = e.field
            self.send_json(e.status, error, headers=e.headers)
        except Exception:
            if conn is not None:
                conn.rollback()
            self.log_error('Unhandled error on %s %s', method, path)
            import traceback
            traceback.print_exc()
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {'error': i18n.translate(_('Вътрешна грешка на сървъра!'), self.lang)})
        finally:
            if conn is not None:
                conn.close()

    def read_json_body(self, method):
        if method in ('GET', 'DELETE'):
            return {}
        # Requiring application/json forces a CORS preflight for cross-site requests (CSRF guard).
        if not self.headers.get('Content-Type', '').startswith('application/json'):
            raise ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, _('Очаква се application/json'))
        header = (self.headers.get('Content-Length') or '0').strip()
        if not header.isdigit():
            self.close_connection = True  # the body length is unknown, so the stream cannot be reused
            raise ApiError(HTTPStatus.BAD_REQUEST, _('Невалиден Content-Length'))
        length = int(header)
        if length > MAX_BODY:
            self.close_connection = True
            raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, _('Файлът е твърде голям!'))
        raw = self.rfile.read(length) if length else b''
        try:
            data = json.loads(raw.decode('utf-8')) if raw else {}
        except (ValueError, RecursionError):
            raise ApiError(HTTPStatus.BAD_REQUEST, _('Невалиден JSON'))
        if not isinstance(data, dict):
            raise ApiError(HTTPStatus.BAD_REQUEST, _('Невалиден JSON'))
        return data

    @property
    def lang(self):
        """Language of the messages, from the Accept-Language header the frontend sends."""
        return i18n.from_header(self.headers.get('Accept-Language'))

    def send_json(self, status, payload, cookie=None, headers=None):
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        if cookie is not None:
            token, max_age = cookie
            self.send_header('Set-Cookie', '{}={}; Path=/; Max-Age={}; HttpOnly; SameSite=Lax{}'.format(
                SESSION_COOKIE, token, max_age, '; Secure' if os.environ.get('NGIS_SECURE_COOKIE') else ''))
        self.end_headers()
        self.wfile.write(data)


def main():
    parser = argparse.ArgumentParser(description='nGIS server')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()

    db.init_db().close()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print('nGIS listening on http://{}:{}  (db: {})'.format(args.host, args.port, os.path.abspath(db.DB_PATH)))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
