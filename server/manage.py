"""nGIS management commands.

    python3 server/manage.py init
    python3 server/manage.py create-user EMAIL [--admin] [--read] [--write]
    python3 server/manage.py set-password EMAIL
    python3 server/manage.py import-firebase DATABASE_EXPORT.json [--auth USERS_EXPORT.json]
    python3 server/manage.py backup [--dir DIR] [--keep N]

DATABASE_EXPORT.json is the Realtime Database export
(Firebase console -> Realtime Database -> ⋮ -> Export JSON).
USERS_EXPORT.json comes from `firebase auth:export users.json --format=json --project tg-gis`.
Firebase password hashes cannot be reused, so imported users get no password;
set one with `set-password`.
"""
import argparse
import getpass
import gzip
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime

import db


def cmd_init(args):
    db.init_db().close()
    print('Database ready:', db.DB_PATH)


def read_password():
    pw = getpass.getpass('Парола: ')
    if len(pw) < 10:
        sys.exit('Паролата трябва да е поне 10 символа.')
    if pw != getpass.getpass('Повторете паролата: '):
        sys.exit('Паролите не съвпадат.')
    return pw


def cmd_create_user(args):
    conn = db.init_db()
    pw = read_password()
    try:
        conn.execute('INSERT INTO users (id, email, password_hash, is_admin, can_read, can_write) '
                     'VALUES (?, ?, ?, ?, ?, ?)',
                     (db.new_id(), args.email, db.hash_password(pw),
                      int(args.admin), int(args.read or args.admin), int(args.write or args.admin)))
    except sqlite3.IntegrityError:
        sys.exit('Потребител с този Email вече съществува.')
    conn.commit()
    print('Създаден е потребител', args.email)


def cmd_set_password(args):
    conn = db.init_db()
    if conn.execute('SELECT 1 FROM users WHERE email = ?', (args.email,)).fetchone() is None:
        sys.exit('Няма такъв потребител.')
    conn.execute('UPDATE users SET password_hash = ? WHERE email = ?', (db.hash_password(read_password()), args.email))
    conn.execute('DELETE FROM sessions WHERE user_id = (SELECT id FROM users WHERE email = ?)', (args.email,))
    conn.commit()
    print('Паролата е сменена.')


def cmd_import_firebase(args):
    with open(args.database, encoding='utf-8') as f:
        data = json.load(f) or {}

    conn = db.init_db()
    stats = {'users': 0, 'projects': 0, 'layers': 0}

    with conn:
        if args.auth:
            with open(args.auth, encoding='utf-8') as f:
                auth = json.load(f)
            for u in auth.get('users', []):
                if not u.get('email'):
                    print('  пропуснат потребител без email:', u.get('localId'))
                    continue
                conn.execute('INSERT OR IGNORE INTO users (id, email, display_name, photo_url) VALUES (?, ?, ?, ?)',
                             (u['localId'], u['email'], u.get('displayName'), u.get('photoUrl')))
                stats['users'] += 1

        def set_flag(column, uids):
            for uid, value in (uids or {}).items():
                if not value:
                    continue
                cur = conn.execute('UPDATE users SET {} = 1 WHERE id = ?'.format(column), (uid,))
                if cur.rowcount == 0:
                    print('  ВНИМАНИЕ: UID {} ({}) не е намерен сред потребителите – подайте --auth'.format(uid, column))

        set_flag('is_admin', (data.get('groups') or {}).get('admins'))
        set_flag('can_read', (data.get('access') or {}).get('read'))
        set_flag('can_write', (data.get('access') or {}).get('write'))

        for pid, p in (data.get('projects') or {}).items():
            conn.execute('INSERT OR REPLACE INTO projects (id, name, year) VALUES (?, ?, ?)',
                         (pid, p.get('name', pid), str(p.get('year', ''))))
            stats['projects'] += 1

        for pid, pdata in (data.get('project-data') or {}).items():
            if conn.execute('SELECT 1 FROM projects WHERE id = ?', (pid,)).fetchone() is None:
                print('  пропуснати данни за несъществуващ обект', pid)
                continue
            for fid, layer in ((pdata or {}).get('data') or {}).items():
                conn.execute('INSERT OR REPLACE INTO layers (id, project_id, title, content) VALUES (?, ?, ?, ?)',
                             (fid, pid, layer.get('title', fid), layer.get('content', '')))
                stats['layers'] += 1

    print('Импортирани: {users} потребители, {projects} обекта, {layers} файла.'.format(**stats))
    if args.auth:
        print('Задайте пароли с: python3 server/manage.py set-password EMAIL')


def cmd_backup(args):
    """Consistent online copy (works while the server runs, WAL included), verified and gzipped."""
    os.makedirs(args.dir, exist_ok=True)
    name = 'ngis-{}.db'.format(datetime.now().strftime('%Y%m%d-%H%M%S'))
    target = os.path.join(args.dir, name + '.gz')

    source = db.connect()
    with tempfile.TemporaryDirectory(dir=args.dir) as tmp:
        copy_path = os.path.join(tmp, name)
        copy = sqlite3.connect(copy_path)
        source.backup(copy)
        result = copy.execute('PRAGMA integrity_check').fetchone()[0]
        copy.close()
        source.close()
        if result != 'ok':
            sys.exit('Копието не мина проверката за цялост: ' + result)
        with open(copy_path, 'rb') as src, gzip.open(target + '.part', 'wb') as dst:
            shutil.copyfileobj(src, dst)
        os.replace(target + '.part', target)
    os.chmod(target, 0o600)
    print('Резервно копие:', target)

    backups = sorted(f for f in os.listdir(args.dir) if f.startswith('ngis-') and f.endswith('.db.gz'))
    for old in backups[:-args.keep]:
        os.remove(os.path.join(args.dir, old))
        print('Изтрито старо копие:', old)


def main():
    parser = argparse.ArgumentParser(description='nGIS management')
    sub = parser.add_subparsers(dest='cmd', required=True)

    sub.add_parser('init').set_defaults(fn=cmd_init)

    p = sub.add_parser('create-user')
    p.add_argument('email')
    p.add_argument('--admin', action='store_true')
    p.add_argument('--read', action='store_true')
    p.add_argument('--write', action='store_true')
    p.set_defaults(fn=cmd_create_user)

    p = sub.add_parser('set-password')
    p.add_argument('email')
    p.set_defaults(fn=cmd_set_password)

    p = sub.add_parser('import-firebase')
    p.add_argument('database')
    p.add_argument('--auth')
    p.set_defaults(fn=cmd_import_firebase)

    p = sub.add_parser('backup')
    p.add_argument('--dir', default=os.environ.get('NGIS_BACKUP_DIR') or os.path.join(os.path.dirname(os.path.abspath(db.DB_PATH)), 'backups'),
                   help='папка за копията (по подразбиране $NGIS_BACKUP_DIR или data/backups)')
    p.add_argument('--keep', type=int, default=14, help='колко последни копия да се пазят (14)')
    p.set_defaults(fn=cmd_backup)

    args = parser.parse_args()
    args.fn(args)


if __name__ == '__main__':
    main()
