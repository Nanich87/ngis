"""nGIS backend: serves the static frontend and a JSON API backed by SQLite.

Only the Python standard library is used.

    python3 server/app.py [--host 127.0.0.1] [--port 8000]
"""
import argparse
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

import db

PUBLIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'public'))
SESSION_COOKIE = 'ngis_session'
SESSION_TTL = timedelta(days=14)
MAX_BODY = 64 * 1024 * 1024  # GeoJSON files can be large

PROJECT_NAME_RE = re.compile(r'^[a-zA-Z0-9-]{3,20}$')
PROJECT_YEAR_RE = re.compile(r'^(19|20)[0-9]{2}$')
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


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
            raise ApiError(HTTPStatus.UNAUTHORIZED, 'Не сте влезли в системата!')
        return self.user

    def require_read(self):
        user = self.require_user()
        if not (user['can_read'] or user['is_admin']):
            raise ApiError(HTTPStatus.FORBIDDEN, 'Нямате права за четене!')
        return user

    def require_write(self):
        user = self.require_user()
        if not (user['can_write'] or user['is_admin']):
            raise ApiError(HTTPStatus.FORBIDDEN, 'Нямате права за запис!')
        return user

    def require_admin(self):
        user = self.require_user()
        if not user['is_admin']:
            raise ApiError(HTTPStatus.FORBIDDEN, 'Нямате администраторски права!')
        return user

    def field(self, name, required=True):
        value = self.body.get(name) if isinstance(self.body, dict) else None
        if required and (not isinstance(value, str) or value == ''):
            raise ApiError(HTTPStatus.BAD_REQUEST, 'Липсва поле: ' + name)
        return value


# --------------------------------------------------------------------------- auth

def start_session(req, user_id):
    token = secrets.token_urlsafe(32)
    req.conn.execute('DELETE FROM sessions WHERE expires_at <= ?', (now_utc().isoformat(),))
    req.conn.execute('INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)',
                     (token, user_id, (now_utc() + SESSION_TTL).isoformat()))
    req.new_cookie = (token, int(SESSION_TTL.total_seconds()))


@route('POST', '/api/auth/signup')
def signup(req):
    email = req.field('email').strip()
    password = req.field('password')
    if not EMAIL_RE.match(email):
        raise ApiError(HTTPStatus.BAD_REQUEST, 'Невалиден Email адрес!')
    if len(password) < 6:
        raise ApiError(HTTPStatus.BAD_REQUEST, 'Паролата трябва да е поне 6 символа!')
    try:
        req.conn.execute('INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)',
                         (db.new_id(), email, db.hash_password(password)))
    except sqlite3.IntegrityError:
        raise ApiError(HTTPStatus.CONFLICT, 'Вече съществува потребител с този Email адрес!')
    return HTTPStatus.CREATED, {'ok': True}


@route('POST', '/api/auth/login')
def login(req):
    email = req.field('email').strip()
    password = req.field('password')
    row = req.conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    if row is None or not db.verify_password(password, row['password_hash']):
        raise ApiError(HTTPStatus.UNAUTHORIZED, 'Грешен Email адрес или парола!')
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
    display_name = req.field('displayName', required=False)
    photo_url = req.field('photoURL', required=False)
    req.conn.execute('UPDATE users SET display_name = ?, photo_url = ? WHERE id = ?',
                     (display_name or None, photo_url or None, user['id']))
    row = req.conn.execute('SELECT * FROM users WHERE id = ?', (user['id'],)).fetchone()
    return HTTPStatus.OK, user_to_json(row)


# --------------------------------------------------------------------------- admin

@route('POST', '/api/admin/users/:uid/rights')
def change_rights(req):
    req.require_admin()
    rights = req.field('rights')
    grant = bool(req.body.get('grant'))
    columns = {'read': ['can_read'], 'write': ['can_write'], 'both': ['can_read', 'can_write']}
    if rights not in columns:
        raise ApiError(HTTPStatus.BAD_REQUEST, 'Невалиден вид права!')
    uid = req.params['uid']
    # Accept either a UID or an email address in the admin form.
    row = req.conn.execute('SELECT id FROM users WHERE id = ? OR email = ?', (uid, uid)).fetchone()
    if row is None:
        raise ApiError(HTTPStatus.NOT_FOUND, 'Няма такъв потребител!')
    sets = ', '.join('{} = ?'.format(c) for c in columns[rights])
    req.conn.execute('UPDATE users SET {} WHERE id = ?'.format(sets),
                     [1 if grant else 0] * len(columns[rights]) + [row['id']])
    return HTTPStatus.OK, {'ok': True}


# --------------------------------------------------------------------------- projects

def get_project_or_404(req, pid):
    row = req.conn.execute('SELECT * FROM projects WHERE id = ?', (pid,)).fetchone()
    if row is None:
        raise ApiError(HTTPStatus.NOT_FOUND, 'Няма такъв обект!')
    return row


@route('GET', '/api/projects')
def list_projects(req):
    req.require_read()
    rows = req.conn.execute('SELECT id, name, year FROM projects ORDER BY created_at, id').fetchall()
    return HTTPStatus.OK, [dict(r) for r in rows]


@route('POST', '/api/projects')
def create_project(req):
    req.require_admin()
    name = req.field('name').strip()
    year = req.field('year').strip()
    if not PROJECT_NAME_RE.match(name):
        raise ApiError(HTTPStatus.BAD_REQUEST, 'Невалидно име на обект!')
    if not PROJECT_YEAR_RE.match(year):
        raise ApiError(HTTPStatus.BAD_REQUEST, 'Невалидна година!')
    pid = db.new_id()
    req.conn.execute('INSERT INTO projects (id, name, year) VALUES (?, ?, ?)', (pid, name, year))
    return HTTPStatus.CREATED, {'id': pid, 'name': name, 'year': year}


@route('GET', '/api/projects/:pid')
def get_project(req):
    req.require_read()
    project = get_project_or_404(req, req.params['pid'])
    layers = req.conn.execute('SELECT id, title FROM layers WHERE project_id = ? ORDER BY created_at, id',
                              (project['id'],)).fetchall()
    result = dict(project)
    result['data'] = {l['id']: l['title'] for l in layers}
    return HTTPStatus.OK, result


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
    title = req.field('title').strip()
    content = req.field('content')
    try:
        json.loads(content)
    except ValueError:
        raise ApiError(HTTPStatus.BAD_REQUEST, 'Файлът не е валиден GeoJSON!')
    lid = db.new_id()
    req.conn.execute('INSERT INTO layers (id, project_id, title, content) VALUES (?, ?, ?, ?)',
                     (lid, req.params['pid'], title, content))
    return HTTPStatus.CREATED, {'id': lid, 'title': title}


def get_layer_or_404(req):
    row = req.conn.execute('SELECT id, title, content FROM layers WHERE id = ? AND project_id = ?',
                           (req.params['lid'], req.params['pid'])).fetchone()
    if row is None:
        raise ApiError(HTTPStatus.NOT_FOUND, 'Няма такъв файл!')
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
        cookie = SimpleCookie(self.headers.get('Cookie', ''))
        morsel = cookie.get(SESSION_COOKIE)
        return morsel.value if morsel else None

    def do_GET(self):
        if self.path.startswith('/api/'):
            return self.handle_api('GET')
        # SPA fallback (same as the old firebase.json rewrite).
        path = self.translate_path(self.path)
        if not os.path.exists(path):
            self.path = '/index.html'
        return super().do_GET()

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
            self.send_json(e.status, {'error': e.message})
        except Exception:
            if conn is not None:
                conn.rollback()
            self.log_error('Unhandled error on %s %s', method, path)
            import traceback
            traceback.print_exc()
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {'error': 'Вътрешна грешка на сървъра!'})
        finally:
            if conn is not None:
                conn.close()

    def read_json_body(self, method):
        if method in ('GET', 'DELETE'):
            return {}
        # Requiring application/json forces a CORS preflight for cross-site requests (CSRF guard).
        if not self.headers.get('Content-Type', '').startswith('application/json'):
            raise ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, 'Очаква се application/json')
        length = int(self.headers.get('Content-Length') or 0)
        if length > MAX_BODY:
            raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, 'Файлът е твърде голям!')
        raw = self.rfile.read(length) if length else b''
        try:
            data = json.loads(raw.decode('utf-8')) if raw else {}
        except ValueError:
            raise ApiError(HTTPStatus.BAD_REQUEST, 'Невалиден JSON')
        if not isinstance(data, dict):
            raise ApiError(HTTPStatus.BAD_REQUEST, 'Невалиден JSON')
        return data

    def send_json(self, status, payload, cookie=None):
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
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
