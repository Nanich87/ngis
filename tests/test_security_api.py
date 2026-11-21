"""Security tests for the nGIS HTTP API and static file server.

    python3 -m unittest discover -s tests -v
"""
import json
import statistics
import time
import unittest
from urllib.parse import quote

from support import PASSWORD, SAMPLE_GEOJSON, Client, ServerTestCase, raw_request

SQLI_PAYLOADS = [
    "' OR '1'='1",
    "' OR 1=1--",
    "\" OR \"\"=\"",
    "admin@test.bg'--",
    "admin@test.bg' /*",
    "'; DROP TABLE users;--",
    "1; DELETE FROM projects",
    "' UNION SELECT id, email, password_hash, 1, 1, 1, 1, 1, 1 FROM users--",
    "') OR ('a'='a",
    "%' OR '%'='",
    "\\'; SELECT sqlite_version();--",
    "1' AND (SELECT COUNT(*) FROM sqlite_master) > 0--",
    "x' || (SELECT password_hash FROM users LIMIT 1) || '",
    "\x00' OR 1=1--",
]

XSS_PAYLOADS = [
    '<script>alert(1)</script>',
    '"><img src=x onerror=alert(1)>',
    "'><svg onload=alert(1)>",
    '{{constructor.constructor("alert(1)")()}}',
    '</textarea><script>alert(1)</script>',
]

PROTECTED = [
    ('GET', '/api/me'),
    ('PATCH', '/api/me'),
    ('POST', '/api/me/password'),
    ('GET', '/api/projects'),
    ('POST', '/api/projects'),
    ('GET', '/api/projects/p-alpha'),
    ('PATCH', '/api/projects/p-alpha'),
    ('DELETE', '/api/projects/p-alpha'),
    ('GET', '/api/projects/p-alpha/layers'),
    ('POST', '/api/projects/p-alpha/layers'),
    ('GET', '/api/projects/p-alpha/layers/l-alpha'),
    ('DELETE', '/api/projects/p-alpha/layers/l-alpha'),
    ('GET', '/api/admin/users'),
    ('PATCH', '/api/admin/users/u-reader'),
    ('POST', '/api/admin/users'),
    ('POST', '/api/admin/users/u-reader/password'),
    ('DELETE', '/api/admin/users/u-reader'),
]


def send(client, method, path, body=None):
    if method in ('POST', 'PATCH'):
        return client.request(method, path, body=body if body is not None else {})
    return client.request(method, path)


# --------------------------------------------------------------------------- SQL injection

class SqlInjectionTests(ServerTestCase):

    def assertDatabaseIntact(self):
        conn = self.db()
        try:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue({'users', 'sessions', 'projects', 'layers'} <= tables, tables)
            self.assertEqual(conn.execute("SELECT is_admin FROM users WHERE id='u-admin'").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT is_admin FROM users WHERE id='u-reader'").fetchone()[0], 0)
            self.assertIsNotNone(conn.execute("SELECT 1 FROM projects WHERE id='p-alpha'").fetchone())
        finally:
            conn.close()

    def test_login_email_field(self):
        c = Client(self.port)
        for payload in SQLI_PAYLOADS:
            with self.subTest(payload=payload):
                r = c.post('/api/auth/login', {'email': payload, 'password': 'anything'})
                self.assertNotServerError(r)
                self.assertIn(r.status, (400, 401))
                self.assertIsNone(c.token)
        self.assertDatabaseIntact()

    def test_login_password_field(self):
        c = Client(self.port)
        for payload in SQLI_PAYLOADS:
            with self.subTest(payload=payload):
                # nobody@ is not used elsewhere in this class, so locking it out is harmless.
                r = c.post('/api/auth/login', {'email': 'nobody@test.bg', 'password': payload})
                self.assertNotServerError(r)
                self.assertIn(r.status, (401, 429))  # 429 once the brute-force limit kicks in
                self.assertIsNone(c.token)

    def test_admin_create_user_fields(self):
        admin = self.client('admin@test.bg')
        for i, payload in enumerate(SQLI_PAYLOADS):
            with self.subTest(payload=payload):
                r = admin.post('/api/admin/users', {'email': payload, 'displayName': 'x'})
                self.assertNotServerError(r)
                r = admin.post('/api/admin/users', {'email': 'sqli{}@test.bg'.format(i), 'displayName': payload[:100]})
                self.assertNotServerError(r)
                if r.status == 201:
                    self.assertEqual(r.json['user']['displayName'], payload[:100].strip())
        self.assertDatabaseIntact()

    def test_project_fields(self):
        admin = self.client('admin@test.bg')
        for payload in SQLI_PAYLOADS:
            with self.subTest(payload=payload):
                r = admin.post('/api/projects', {'name': payload, 'year': '2020'})
                self.assertNotServerError(r)
                self.assertEqual(r.status, 400)
                r = admin.post('/api/projects', {'name': 'Valid-name', 'year': payload})
                self.assertNotServerError(r)
                self.assertEqual(r.status, 400)
                r = admin.patch('/api/projects/p-alpha', {'name': payload})
                self.assertNotServerError(r)
                self.assertEqual(r.status, 400)
        self.assertDatabaseIntact()

    def test_values_are_stored_verbatim(self):
        """Payloads in free-text fields must round-trip unchanged (proves parameterized SQL)."""
        writer = self.client('writer@test.bg')
        for payload in SQLI_PAYLOADS:
            with self.subTest(payload=payload):
                r = writer.post('/api/projects/p-beta/layers', {'title': payload + '.geojson', 'content': SAMPLE_GEOJSON})
                self.assertNotServerError(r)
                if r.status == 201:
                    lid = r.json['id']
                    got = writer.get('/api/projects/p-beta/layers/' + lid).json
                    self.assertEqual(got['title'], (payload + '.geojson').strip())
                    writer.delete('/api/projects/p-beta/layers/' + lid)
                r = writer.patch('/api/me', {'displayName': payload, 'photoURL': ''})
                self.assertNotServerError(r)
                if r.status == 200:
                    self.assertEqual(writer.get('/api/me').json['displayName'], payload)
        self.assertDatabaseIntact()

    def test_path_parameters(self):
        admin = self.client('admin@test.bg')
        for payload in SQLI_PAYLOADS:
            p = quote(payload, safe='')
            for method, path in [('GET', '/api/projects/' + p),
                                 ('GET', '/api/projects/' + p + '/layers'),
                                 ('GET', '/api/projects/p-alpha/layers/' + p),
                                 ('GET', '/api/projects/' + p + '/layers/l-alpha'),
                                 ('DELETE', '/api/projects/' + p),
                                 ('DELETE', '/api/projects/p-alpha/layers/' + p),
                                 ('PATCH', '/api/admin/users/' + p)]:
                with self.subTest(method=method, path=path):
                    r = send(admin, method, path, {'canRead': True})
                    self.assertNotServerError(r)
                    self.assertIn(r.status, (400, 404))
        self.assertDatabaseIntact()

    def test_admin_patch_keys(self):
        admin = self.client('admin@test.bg')
        r = admin.patch('/api/admin/users/u-reader', {"is_admin = 1, can_write": True, "canRead; DROP TABLE users--": True})
        self.assertNotServerError(r)
        self.assertEqual(r.status, 400)
        self.assertDatabaseIntact()

    def test_session_cookie(self):
        for payload in SQLI_PAYLOADS:
            with self.subTest(payload=payload):
                c = Client(self.port, token=quote(payload, safe=''))
                r = c.get('/api/me')
                self.assertNotServerError(r)
                self.assertEqual(r.status, 401)
                r = c.get('/api/me', headers={'Cookie': 'ngis_session="' + payload.replace('"', '') + '"'})
                self.assertNotServerError(r)
                self.assertEqual(r.status, 401)


# --------------------------------------------------------------------------- authentication

class AuthenticationTests(ServerTestCase):

    def test_protected_endpoints_require_session(self):
        c = Client(self.port)
        for method, path in PROTECTED:
            with self.subTest(method=method, path=path):
                r = send(c, method, path)
                self.assertEqual(r.status, 401, r.text)

    def test_forged_tokens_rejected(self):
        for token in ['', 'x', 'A' * 43, 'null', 'undefined', '../../etc/passwd', 'a' * 5000]:
            with self.subTest(token=token[:20]):
                r = Client(self.port, token=token).get('/api/me')
                self.assertNotServerError(r)
                self.assertEqual(r.status, 401)

    def test_malformed_cookie_header(self):
        for cookie in ['ngis_session', '=;=;=', 'ngis_session=a; ngis_session=b', 'ngis_session="unterminated',
                       '\x00\x01', 'a' * 8000]:
            with self.subTest(cookie=cookie[:20]):
                r = Client(self.port).get('/api/me', headers={'Cookie': cookie})
                self.assertNotServerError(r)
                self.assertEqual(r.status, 401)

    def test_cookie_flags(self):
        c = Client(self.port)
        r = c.post('/api/auth/login', {'email': 'reader@test.bg', 'password': PASSWORD})
        cookie = r.header('Set-Cookie')
        self.assertIsNotNone(cookie)
        flags = [p.strip().lower() for p in cookie.split(';')]
        self.assertIn('httponly', flags)
        self.assertIn('samesite=lax', flags)
        self.assertIn('path=/', flags)
        self.assertGreaterEqual(len(c.token), 40, 'session token too short')

    def test_new_token_on_every_login(self):
        """No session fixation: a cookie set before login is never promoted to a session."""
        c = Client(self.port, token='attacker-chosen-token')
        c.login('reader@test.bg')
        self.assertNotEqual(c.token, 'attacker-chosen-token')
        self.assertEqual(Client(self.port, token='attacker-chosen-token').get('/api/me').status, 401)
        first = c.token
        c.login('reader@test.bg')
        self.assertNotEqual(c.token, first)

    def test_logout_invalidates_token_server_side(self):
        c = self.client('reader@test.bg')
        token = c.token
        self.assertEqual(c.post('/api/auth/logout').status, 200)
        self.assertEqual(Client(self.port, token=token).get('/api/me').status, 401)

    def test_imported_user_without_password_cannot_log_in(self):
        c = Client(self.port)
        for password in ['', ' ', 'null', 'None', 'undefined', PASSWORD]:
            with self.subTest(password=password):
                r = c.post('/api/auth/login', {'email': 'imported@test.bg', 'password': password})
                self.assertIn(r.status, (400, 401))
                self.assertIsNone(c.token)

    def test_login_error_does_not_reveal_which_part_is_wrong(self):
        c = Client(self.port)
        unknown = c.post('/api/auth/login', {'email': 'missing@test.bg', 'password': 'whatever1'})
        wrong = c.post('/api/auth/login', {'email': 'reader@test.bg', 'password': 'whatever1'})
        self.assertEqual(unknown.status, wrong.status)
        self.assertEqual(unknown.json, wrong.json)

    def test_login_timing_does_not_reveal_existing_emails(self):
        """Unknown emails must cost as much as a wrong password, or attackers can enumerate accounts."""
        c = Client(self.port)

        def timed(email):
            samples = []
            for _ in range(5):
                start = time.perf_counter()
                c.post('/api/auth/login', {'email': email, 'password': 'wrong-password'})
                samples.append(time.perf_counter() - start)
            return statistics.median(samples)

        unknown = timed('missing@test.bg')
        known = timed('writer@test.bg')
        self.assertGreater(unknown, known * 0.5,
                           'unknown email answered in {:.0f} ms vs {:.0f} ms for a known one'.format(unknown * 1000, known * 1000))

    def test_case_and_whitespace_in_email(self):
        c = Client(self.port)
        r = c.post('/api/auth/login', {'email': '  READER@test.bg ', 'password': PASSWORD})
        self.assertEqual(r.status, 200)
        r = self.client('admin@test.bg').post('/api/admin/users', {'email': 'Reader@Test.bg'})
        self.assertEqual(r.status, 409, 'duplicate account with different case')

    def test_password_change(self):
        a = self.client('writer@test.bg')
        b = self.client('writer@test.bg')
        r = a.post('/api/me/password', {'currentPassword': 'wrong', 'newPassword': 'brand-new-1'})
        self.assertEqual(r.status, 400)
        r = a.post('/api/me/password', {'currentPassword': PASSWORD, 'newPassword': 'short-123'})
        self.assertEqual(r.status, 400, 'passwords shorter than 10 characters must be rejected')
        r = a.post('/api/me/password', {'currentPassword': PASSWORD, 'newPassword': 'brand-new-1'})
        self.assertEqual(r.status, 200)
        self.assertEqual(a.get('/api/me').status, 200)
        self.assertEqual(b.get('/api/me').status, 401, 'other sessions must be signed out')
        r = a.post('/api/me/password', {'currentPassword': 'brand-new-1', 'newPassword': PASSWORD})
        self.assertEqual(r.status, 200)


class BruteForceTests(ServerTestCase):

    def test_login_attempts_are_rate_limited(self):
        c = Client(self.port)
        statuses = [c.post('/api/auth/login', {'email': 'admin@test.bg', 'password': 'guess-{}'.format(i)}).status
                    for i in range(30)]
        self.assertIn(429, statuses, 'no rate limiting after 30 wrong passwords: {}'.format(sorted(set(statuses))))
        self.assertLessEqual(statuses.index(429), 10, 'limit should start after at most 10 failures')
        r = c.post('/api/auth/login', {'email': 'admin@test.bg', 'password': PASSWORD})
        self.assertEqual(r.status, 429, 'a locked account must not accept even the right password')
        self.assertTrue((r.header('Retry-After') or '').isdigit())
        self.assertIsNone(c.token)
        # Other accounts from the same client are still usable.
        self.assertEqual(c.post('/api/auth/login', {'email': 'reader@test.bg', 'password': PASSWORD}).status, 200)

    def test_password_change_attempts_are_rate_limited(self):
        c = self.client('reader@test.bg')
        statuses = [c.post('/api/me/password', {'currentPassword': 'guess-{}'.format(i), 'newPassword': 'whatever-1'}).status
                    for i in range(30)]
        self.assertIn(429, statuses, 'current password can be brute-forced: {}'.format(sorted(set(statuses))))


# --------------------------------------------------------------------------- authorization

class AuthorizationTests(ServerTestCase):

    # endpoint -> minimum role: read < write < admin
    MATRIX = [
        ('GET', '/api/projects', 'read'),
        ('GET', '/api/projects/p-alpha', 'read'),
        ('GET', '/api/projects/p-alpha/layers', 'read'),
        ('GET', '/api/projects/p-alpha/layers/l-alpha', 'read'),
        ('POST', '/api/projects/p-beta/layers', 'write'),
        ('POST', '/api/projects', 'admin'),
        ('PATCH', '/api/projects/p-beta', 'admin'),
        ('GET', '/api/admin/users', 'admin'),
        ('PATCH', '/api/admin/users/u-nobody', 'admin'),
    ]
    LEVEL = {'nobody@test.bg': 0, 'reader@test.bg': 1, 'writer@test.bg': 2, 'admin@test.bg': 3}
    NEEDED = {'read': 1, 'write': 2, 'admin': 3}
    BODIES = {
        '/api/projects/p-beta/layers': {'title': 'authz.geojson', 'content': SAMPLE_GEOJSON},
        '/api/projects': {'name': 'Authz-test', 'year': '2024'},
        '/api/projects/p-beta': {'name': 'Authz-renamed'},
        '/api/admin/users/u-nobody': {'canRead': False},
    }

    def test_role_matrix(self):
        for email, level in self.LEVEL.items():
            c = self.client(email)
            for method, path, role in self.MATRIX:
                with self.subTest(user=email, method=method, path=path):
                    r = send(c, method, path, self.BODIES.get(path))
                    if level >= self.NEEDED[role]:
                        self.assertIn(r.status, (200, 201), r.text)
                    else:
                        self.assertEqual(r.status, 403, r.text)

    def test_rename_project(self):
        admin = self.client('admin@test.bg')
        r = admin.patch('/api/projects/p-alpha', {'name': '  Alpha-2  '})
        self.assertEqual(r.status, 200, r.text)
        self.assertEqual(r.json, {'id': 'p-alpha', 'name': 'Alpha-2', 'year': '2020'})
        project = admin.get('/api/projects/p-alpha').json
        self.assertEqual((project['name'], project['year']), ('Alpha-2', '2020'))
        self.assertEqual(len(project['layers']), 1)          # files stay with the project
        self.assertEqual(admin.patch('/api/projects/missing', {'name': 'Valid-name'}).status, 404)
        for body in ({}, {'name': ''}, {'name': 'ab'}, {'name': 'x' * 21}, {'name': 'с кирилица'}, {'name': 5}):
            with self.subTest(body=body):
                self.assertEqual(admin.patch('/api/projects/p-alpha', body).status, 400)
        self.assertEqual(admin.get('/api/projects/p-alpha').json['name'], 'Alpha-2')
        self.assertEqual(self.client('writer@test.bg').patch('/api/projects/p-alpha', {'name': 'Writer'}).status, 403)

    def test_destructive_endpoints_by_lower_roles(self):
        for email in ['nobody@test.bg', 'reader@test.bg']:
            c = self.client(email)
            with self.subTest(user=email):
                self.assertEqual(c.delete('/api/projects/p-alpha/layers/l-alpha').status, 403)
                self.assertEqual(c.delete('/api/projects/p-alpha').status, 403)
        self.assertEqual(self.client('writer@test.bg').delete('/api/projects/p-alpha').status, 403)
        conn = self.db()
        self.assertIsNotNone(conn.execute("SELECT 1 FROM layers WHERE id='l-alpha'").fetchone())
        self.assertIsNotNone(conn.execute("SELECT 1 FROM projects WHERE id='p-alpha'").fetchone())
        conn.close()

    def test_layer_must_belong_to_project_in_url(self):
        """IDOR: reaching a layer through another project's URL must fail."""
        writer = self.client('writer@test.bg')
        self.assertEqual(writer.get('/api/projects/p-beta/layers/l-alpha').status, 404)
        self.assertEqual(writer.delete('/api/projects/p-beta/layers/l-alpha').status, 404)
        self.assertEqual(writer.get('/api/projects/p-alpha/layers/l-alpha').status, 200)

    def test_user_cannot_escalate_through_profile(self):
        c = self.client('nobody@test.bg')
        r = c.patch('/api/me', {'displayName': 'x', 'isAdmin': True, 'is_admin': 1, 'canRead': True,
                                'can_write': 1, 'email': 'admin@test.bg', 'uid': 'u-admin'})
        self.assertNotServerError(r)
        me = c.get('/api/me').json
        self.assertFalse(me['isAdmin'] or me['canRead'] or me['canWrite'])
        self.assertEqual(me['email'], 'nobody@test.bg')
        self.assertEqual(me['uid'], 'u-nobody')

    def test_admin_cannot_remove_own_admin(self):
        admin = self.client('admin@test.bg')
        r = admin.patch('/api/admin/users/u-admin', {'isAdmin': False})
        self.assertEqual(r.status, 400)
        self.assertTrue(admin.get('/api/me').json['isAdmin'])

    def test_rights_require_real_booleans(self):
        """"false" as a string must not grant a right (type confusion)."""
        admin = self.client('admin@test.bg')
        for value in ['false', '0', 'no', [], {}]:
            with self.subTest(value=value):
                admin.patch('/api/admin/users/u-nobody', {'isAdmin': False})
                r = admin.patch('/api/admin/users/u-nobody', {'isAdmin': value})
                self.assertNotServerError(r)
                users = {u['uid']: u for u in admin.get('/api/admin/users').json}
                self.assertFalse(users['u-nobody']['isAdmin'], 'value {!r} granted admin'.format(value))

    def test_admin_user_list_has_no_password_hashes(self):
        body = self.client('admin@test.bg').get('/api/admin/users').text
        self.assertNotIn('pbkdf2', body)
        self.assertNotIn('password_hash', body)
        self.assertNotIn('pbkdf2', self.client('reader@test.bg').get('/api/me').text)


# --------------------------------------------------------------------------- user management

class UserManagementTests(ServerTestCase):

    def test_public_signup_is_disabled(self):
        r = Client(self.port).post('/api/auth/signup', {'email': 'new@test.bg', 'password': 'long-enough-1'})
        self.assertEqual(r.status, 404)
        conn = self.db()
        self.assertIsNone(conn.execute("SELECT 1 FROM users WHERE email='new@test.bg'").fetchone())
        conn.close()

    def test_only_admins_manage_users(self):
        for email in ['nobody@test.bg', 'reader@test.bg', 'writer@test.bg']:
            c = self.client(email)
            with self.subTest(user=email):
                self.assertEqual(c.post('/api/admin/users', {'email': 'x@test.bg'}).status, 403)
                self.assertEqual(c.post('/api/admin/users/u-nobody/password').status, 403)
                self.assertEqual(c.delete('/api/admin/users/u-nobody').status, 403)

    def test_create_user_with_generated_password(self):
        admin = self.client('admin@test.bg')
        r = admin.post('/api/admin/users', {'email': ' Created@Test.bg ', 'displayName': 'Нов', 'canRead': True})
        self.assertEqual(r.status, 201, r.text)
        password = r.json['password']
        self.assertGreaterEqual(len(password), 16)
        user = r.json['user']
        self.assertEqual((user['email'], user['canRead'], user['canWrite'], user['isAdmin']), ('Created@Test.bg', True, False, False))
        self.assertEqual(Client(self.port).post('/api/auth/login', {'email': 'created@test.bg', 'password': password}).status, 200)
        self.assertEqual(admin.post('/api/admin/users', {'email': 'created@test.bg'}).status, 409)
        self.assertEqual(admin.post('/api/admin/users', {'email': 'x2@test.bg', 'isAdmin': 'true'}).status, 400)
        # Admin implies read and write.
        r = admin.post('/api/admin/users', {'email': 'boss@test.bg', 'isAdmin': True})
        self.assertTrue(r.json['user']['canRead'] and r.json['user']['canWrite'])
        # Passwords are random per user.
        self.assertNotEqual(r.json['password'], password)

    def test_reset_password(self):
        admin = self.client('admin@test.bg')
        r = admin.post('/api/admin/users', {'email': 'reset@test.bg', 'canRead': True})
        uid, old = r.json['user']['uid'], r.json['password']
        session = Client(self.port).login('reset@test.bg', old)
        r = admin.post('/api/admin/users/{}/password'.format(uid))
        self.assertEqual(r.status, 200)
        new = r.json['password']
        self.assertNotEqual(new, old)
        self.assertEqual(session.get('/api/me').status, 401, 'the user must be signed out everywhere')
        self.assertEqual(Client(self.port).post('/api/auth/login', {'email': 'reset@test.bg', 'password': old}).status, 401)
        self.assertEqual(Client(self.port).post('/api/auth/login', {'email': 'reset@test.bg', 'password': new}).status, 200)
        # Imported users without a password get one the same way.
        r = admin.post('/api/admin/users/u-imported/password')
        self.assertEqual(Client(self.port).post('/api/auth/login', {'email': 'imported@test.bg', 'password': r.json['password']}).status, 200)
        self.assertEqual(admin.post('/api/admin/users/missing/password').status, 404)

    def test_delete_user(self):
        admin = self.client('admin@test.bg')
        r = admin.post('/api/admin/users', {'email': 'gone@test.bg', 'canRead': True})
        uid, password = r.json['user']['uid'], r.json['password']
        session = Client(self.port).login('gone@test.bg', password)
        self.assertEqual(admin.delete('/api/admin/users/' + uid).status, 200)
        self.assertEqual(session.get('/api/me').status, 401)
        self.assertEqual(Client(self.port).post('/api/auth/login', {'email': 'gone@test.bg', 'password': password}).status, 401)
        self.assertEqual(admin.delete('/api/admin/users/' + uid).status, 404)
        self.assertEqual(admin.delete('/api/admin/users/u-admin').status, 400, 'admins cannot delete themselves')
        conn = self.db()
        self.assertIsNone(conn.execute('SELECT 1 FROM sessions WHERE user_id = ?', (uid,)).fetchone())
        conn.close()


# --------------------------------------------------------------------------- reverse proxy

def login_from(port, email, password, forwarded_for):
    return Client(port).post('/api/auth/login', {'email': email, 'password': password},
                             headers={'X-Forwarded-For': forwarded_for})


class TrustedProxyTests(ServerTestCase):
    """Behind nginx (NGIS_TRUSTED_PROXIES=127.0.0.1) limits apply to the real client address."""
    server_env = {'NGIS_TRUSTED_PROXIES': '127.0.0.1'}

    def test_lockout_is_per_real_client(self):
        statuses = [login_from(self.port, 'admin@test.bg', 'wrong-{}'.format(i), '203.0.113.7').status for i in range(12)]
        self.assertIn(429, statuses)
        self.assertEqual(login_from(self.port, 'admin@test.bg', PASSWORD, '203.0.113.7').status, 429)
        # Another visitor behind the same proxy is not affected.
        self.assertEqual(login_from(self.port, 'admin@test.bg', PASSWORD, '198.51.100.20').status, 200)

    def test_injected_addresses_are_ignored(self):
        # nginx overwrites the header, but with "append" setups the client-controlled part is on the left.
        for i in range(12):
            login_from(self.port, 'writer@test.bg', 'wrong-{}'.format(i), '1.2.3.{}, 192.0.2.50'.format(i))
        self.assertEqual(login_from(self.port, 'writer@test.bg', PASSWORD, '9.9.9.9, 192.0.2.50').status, 429)


class UntrustedProxyHeaderTests(ServerTestCase):
    """Without trusted proxies a forged X-Forwarded-For must not bypass the lockout."""

    def test_forged_header_does_not_bypass_lockout(self):
        for i in range(12):
            login_from(self.port, 'admin@test.bg', 'wrong-{}'.format(i), '10.0.0.{}'.format(i))
        self.assertEqual(login_from(self.port, 'admin@test.bg', PASSWORD, '10.0.0.99').status, 429)


# --------------------------------------------------------------------------- input validation

class InputValidationTests(ServerTestCase):

    def test_csrf_simple_content_types_rejected(self):
        """Forms from other sites can only send these types; all must be refused."""
        admin = self.client('admin@test.bg')
        for ctype in ['application/x-www-form-urlencoded', 'multipart/form-data; boundary=x', 'text/plain', '']:
            for path in ['/api/auth/login', '/api/projects', '/api/me/password']:
                with self.subTest(ctype=ctype, path=path):
                    r = admin.request('POST', path, raw_body=b'{"name":"Csrf-test","year":"2020"}',
                                      headers={'Content-Type': ctype} if ctype else {})
                    self.assertEqual(r.status, 415)

    def test_no_cors_headers(self):
        r = self.client('reader@test.bg').get('/api/projects', headers={'Origin': 'https://evil.example'})
        self.assertIsNone(r.header('Access-Control-Allow-Origin'))
        self.assertIsNone(r.header('Access-Control-Allow-Credentials'))

    def test_malformed_bodies(self):
        c = self.client('reader@test.bg')
        cases = {
            'not json': b'{not json',
            'array': b'[1, 2, 3]',
            'string': b'"text"',
            'null': b'null',
            'invalid utf-8': b'{"displayName": "\xff\xfe"}',
            'deep nesting': b'[' * 100000 + b']' * 100000,
        }
        for name, raw in cases.items():
            with self.subTest(case=name):
                r = c.request('PATCH', '/api/me', raw_body=raw, headers={'Content-Type': 'application/json'})
                self.assertNotServerError(r)
                self.assertEqual(r.status, 400)

    def test_wrong_field_types(self):
        c = self.client('writer@test.bg')
        for value in [{'a': 1}, [1, 2], 123, True]:
            with self.subTest(value=value):
                r = c.patch('/api/me', {'displayName': value, 'photoURL': ''})
                self.assertNotServerError(r)
                self.assertEqual(r.status, 400)
                r = c.patch('/api/me', {'displayName': '', 'photoURL': value})
                self.assertNotServerError(r)
                self.assertEqual(r.status, 400)
                r = c.post('/api/projects/p-beta/layers', {'title': value, 'content': SAMPLE_GEOJSON})
                self.assertNotServerError(r)
                self.assertEqual(r.status, 400)
                r = Client(self.port).post('/api/auth/login', {'email': value, 'password': value})
                self.assertNotServerError(r)
                self.assertEqual(r.status, 400)

    def test_field_length_limits(self):
        c = self.client('writer@test.bg')
        long = 'А' * 100000
        self.assertEqual(c.patch('/api/me', {'displayName': long, 'photoURL': ''}).status, 400, 'displayName')
        self.assertEqual(c.patch('/api/me', {'displayName': '', 'photoURL': 'https://x.bg/' + long}).status, 400, 'photoURL')
        self.assertEqual(c.post('/api/projects/p-beta/layers', {'title': long, 'content': SAMPLE_GEOJSON}).status, 400, 'title')
        admin = self.client('admin@test.bg')
        self.assertEqual(admin.post('/api/admin/users', {'email': long + '@x.bg'}).status, 400, 'email')
        self.assertEqual(admin.post('/api/admin/users', {'email': 'n@x.bg', 'displayName': long}).status, 400, 'new user name')
        self.assertEqual(c.post('/api/me/password', {'currentPassword': 'x', 'newPassword': 'x' * 1000000}).status, 400, 'password')
        self.assertEqual(Client(self.port).post('/api/auth/login', {'email': 'a@b.bg', 'password': 'x' * 1000000}).status, 400, 'login password')

    def test_photo_url_must_be_http(self):
        c = self.client('writer@test.bg')
        for url in ['javascript:alert(1)', 'JaVaScRiPt:alert(1)', 'data:text/html,<script>alert(1)</script>',
                    'vbscript:msgbox(1)', '//evil.example/x.png', 'https://ok"onerror="alert(1)']:
            with self.subTest(url=url):
                r = c.patch('/api/me', {'displayName': '', 'photoURL': url})
                self.assertEqual(r.status, 400)
        self.assertEqual(c.patch('/api/me', {'displayName': '', 'photoURL': 'https://example.com/me.png'}).status, 200)

    def test_layer_content_must_be_geojson(self):
        c = self.client('writer@test.bg')
        for content in ['1', '"text"', 'null', '[]', '{}', '{"type": 5}', '{"foo": "bar"}']:
            with self.subTest(content=content):
                r = c.post('/api/projects/p-beta/layers', {'title': 'bad.geojson', 'content': content})
                self.assertEqual(r.status, 400)

    def test_control_characters(self):
        c = self.client('writer@test.bg')
        for value in ['a\x00b', 'line\r\nSet-Cookie: x=y', '‮evil.exe', '\ud800'.encode('utf-8', 'surrogatepass').decode('utf-8', 'replace')]:
            with self.subTest(value=repr(value)):
                r = c.post('/api/projects/p-beta/layers', {'title': value, 'content': SAMPLE_GEOJSON})
                self.assertNotServerError(r)
                self.assertNotIn('x=y', ' '.join(r.headers_all('Set-Cookie')))

    def test_xss_payloads_returned_as_json_only(self):
        """Stored payloads come back JSON-encoded with a JSON content type, never as HTML."""
        c = self.client('writer@test.bg')
        for payload in XSS_PAYLOADS:
            with self.subTest(payload=payload):
                r = c.post('/api/projects/p-beta/layers', {'title': payload, 'content': SAMPLE_GEOJSON})
                self.assertEqual(r.status, 201)
                r = c.get('/api/projects/p-beta')
                self.assertTrue(r.header('Content-Type').startswith('application/json'))
                self.assertIn(payload, [l['title'] for l in r.json['layers']])

    def test_content_length_header_abuse(self):
        login = b'{"email":"a@b.bg","password":"x"}'
        cases = {
            'non-numeric': b'abc',
            'negative': b'-1',
            'huge': str(10 ** 12).encode(),
            'float': b'1.5',
        }
        for name, value in cases.items():
            with self.subTest(case=name):
                req = (b'POST /api/auth/login HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n'
                       b'Content-Length: ' + value + b'\r\nConnection: close\r\n\r\n' + login)
                status, _ = raw_request(self.port, req, timeout=3)
                self.assertIsNotNone(status, 'server hung on Content-Length: ' + name)
                code = int(status.split()[1])
                self.assertIn(code, (400, 411, 413), status)

    def test_unknown_routes_and_methods(self):
        c = self.client('admin@test.bg')
        for method, path in [('GET', '/api/'), ('GET', '/api/nope'), ('POST', '/api/projects/p-alpha'),
                             ('PUT', '/api/projects/p-alpha'), ('OPTIONS', '/api/projects'), ('TRACE', '/api/me'),
                             ('HEAD', '/api/me'), ('GET', '/api/projects/p-alpha/layers/l-alpha/extra')]:
            with self.subTest(method=method, path=path):
                r = c.request(method, path)
                if method in ('PUT', 'OPTIONS', 'TRACE'):
                    self.assertIn(r.status, (405, 501))
                else:
                    self.assertNotServerError(r)
                self.assertNotIn('pbkdf2', r.text)


# --------------------------------------------------------------------------- static files / HTTP

class StaticAndHeaderTests(ServerTestCase):

    def test_path_traversal(self):
        markers = ['import db', 'CREATE TABLE', 'root:x:0:0', 'SQLite format 3', 'pbkdf2']
        paths = [
            '/../server/db.py', '/..%2fserver%2fdb.py', '/%2e%2e/server/schema.sql', '/%2e%2e%2f%2e%2e%2fetc%2fpasswd',
            '/....//....//server/app.py', '/..\\server\\db.py', '/%252e%252e/server/db.py', '//etc/passwd',
            '/views/../../server/schema.sql', '/libs/%2e%2e/%2e%2e/data/ngis.db', '/./././../server/manage.py',
            '/%c0%ae%c0%ae/server/db.py', '/index.html%00.py',
        ]
        for path in paths:
            with self.subTest(path=path):
                status, text = raw_request(self.port, 'GET {} HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n'.format(path).encode())
                self.assertIsNotNone(status)
                for marker in markers:
                    self.assertNotIn(marker, text)

    def test_no_directory_listing(self):
        c = Client(self.port)
        for path in ['/libs/', '/views/', '/controllers/', '/samples/', '/images/']:
            with self.subTest(path=path):
                r = c.get(path)
                self.assertNotIn('Directory listing for', r.text)

    def test_security_headers(self):
        c = Client(self.port)
        for path in ['/', '/index.html', '/api/me']:
            with self.subTest(path=path):
                r = c.get(path)
                self.assertEqual((r.header('X-Content-Type-Options') or '').lower(), 'nosniff')
                frame = (r.header('X-Frame-Options') or '').upper()
                csp = r.header('Content-Security-Policy') or ''
                self.assertTrue(frame in ('DENY', 'SAMEORIGIN') or 'frame-ancestors' in csp, 'clickjacking protection missing')
                self.assertIsNotNone(r.header('Referrer-Policy'))

    def test_content_security_policy(self):
        for path in ['/', '/api/me', '/views/map.html']:
            with self.subTest(path=path):
                csp = Client(self.port).get(path).header('Content-Security-Policy') or ''
                directives = {d.strip().split(' ', 1)[0]: d.strip() for d in csp.split(';') if d.strip()}
                for name in ['default-src', 'script-src', 'style-src', 'img-src', 'connect-src', 'object-src',
                             'base-uri', 'form-action', 'frame-ancestors']:
                    self.assertIn(name, directives, csp)
                self.assertNotIn("'unsafe-inline'", directives['script-src'])
                self.assertNotIn('*', directives['script-src'])
                self.assertNotIn('http:', directives['script-src'])
                self.assertEqual(directives['object-src'], "object-src 'none'")
                self.assertEqual(directives['frame-ancestors'], "frame-ancestors 'none'")
                self.assertEqual(directives['connect-src'], "connect-src 'self'")
                # Everything executable or styling the page is self-hosted.
                self.assertEqual(directives['script-src'], "script-src 'self' 'unsafe-eval'")
                self.assertEqual(directives['style-src'], "style-src 'self'")
                self.assertEqual(directives['font-src'], "font-src 'self'")

    def test_server_header_does_not_leak_versions(self):
        server = Client(self.port).get('/').header('Server') or ''
        self.assertNotRegex(server, r'Python/\d', 'Server header: ' + server)

    def test_api_responses_not_cached(self):
        r = self.client('reader@test.bg').get('/api/projects')
        self.assertIn('no-store', r.header('Cache-Control') or '')

    def test_response_splitting_in_path(self):
        for path in ['/%0d%0aSet-Cookie:%20evil=1', '/api/projects/%0d%0aSet-Cookie:%20evil=1']:
            with self.subTest(path=path):
                status, text = raw_request(self.port, 'GET {} HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n'.format(path).encode())
                head = text.split('\r\n\r\n', 1)[0]
                self.assertNotIn('Set-Cookie: evil', head)


if __name__ == '__main__':
    unittest.main()
