"""SQLite access helpers for nGIS."""
import hashlib
import hmac
import os
import secrets
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('NGIS_DB', os.path.join(BASE_DIR, '..', 'data', 'ngis.db'))
SCHEMA_PATH = os.path.join(BASE_DIR, 'schema.sql')

PBKDF2_ITERATIONS = 600_000


def connect(path=None):
    path = path or DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA journal_mode = WAL')
    return conn


def init_db(path=None):
    conn = connect(path)
    with open(SCHEMA_PATH, encoding='utf-8') as f:
        conn.executescript(f.read())
    conn.commit()
    return conn


def new_id():
    """Random URL-safe id, similar in spirit to Firebase push keys."""
    return secrets.token_urlsafe(15)


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, PBKDF2_ITERATIONS)
    return 'pbkdf2_sha256${}${}${}'.format(PBKDF2_ITERATIONS, salt.hex(), digest.hex())


def verify_password(password, stored):
    if not stored:
        return False
    try:
        algo, iterations, salt_hex, digest_hex = stored.split('$')
    except ValueError:
        return False
    if algo != 'pbkdf2_sha256':
        return False
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'),
                                 bytes.fromhex(salt_hex), int(iterations))
    return hmac.compare_digest(digest.hex(), digest_hex)
