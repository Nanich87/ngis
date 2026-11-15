# nGIS

### Features

 - Map
 - Projects (Create / List / View / Edit / Delete)
 - Users (Sign in / Sign up)
 - Admin Panel (User rights management)

### Running

The backend uses only the Python 3 standard library (3.8+) and stores everything in SQLite (`data/ngis.db`, override with `NGIS_DB`).

```bash
python3 server/manage.py init
python3 server/manage.py create-user admin@example.com --admin
python3 server/app.py --port 8000          # http://127.0.0.1:8000
```

Set `NGIS_SECURE_COOKIE=1` when serving over HTTPS (behind a reverse proxy).

### Migrating from Firebase

1. Export the Realtime Database: Firebase console → Realtime Database → ⋮ → *Export JSON*.
2. Export the users: `firebase auth:export users.json --format=json --project tg-gis`.
3. Import: `python3 server/manage.py import-firebase tg-gis-export.json --auth users.json`
4. Firebase password hashes cannot be reused – set new ones with `python3 server/manage.py set-password EMAIL`.

Project, file and user IDs are preserved, so old links keep working.

### Todos

 - Write Tests
 - Add Code Comments

### License

Code by Nanko Geshkov. Copyright 2017 Nanko Geshkov [http://sixeightone.eu](http://sixeightone.eu)

### Any questions, comments or additions?

If you have a feature request or bug report, leave an issue on the [issues page](https://github.com/Nanich87/ngis/issues) or send a [pull request](https://github.com/Nanich87/ngis/pulls).
