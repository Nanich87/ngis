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

### Coordinate systems

Uploaded GeoJSON is reprojected to the map (Web Mercator) in the browser with proj4js. Supported:

- WGS84 (EPSG:4326 / CRS84) and Web Mercator (EPSG:3857) – detected automatically
- BGS2005 / CCS2005 (EPSG:7801), BGS2005 / UTM 34N, 35N, 36N (EPSG:7803–7805)
- WGS84 / UTM 34N, 35N (EPSG:32634, 32635), ETRS89 / UTM 34N, 35N (EPSG:25834, 25835)
- ETRS89 (EPSG:4258), ETRS89 / LAEA Europe (EPSG:3035)

Projected systems other than Web Mercator must be declared in the file's `crs` member
(QGIS/GDAL do this on export). Coordinates are read as easting, northing.

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
