"""Tests for the GPX reader and its upload endpoint.

    python3 -m unittest discover -s tests -v
"""
import base64
import json
import random
import unittest

from support import Client, ServerTestCase

import gpx  # server/gpx.py (support.py puts server/ on sys.path)


def make_gpx(body=None, version='1.1', encoding='UTF-8'):
    """A GPX file with a waypoint, a route and a two-segment track (default body)."""
    if body is None:
        body = (
            '<metadata><name>Разходка</name></metadata>'
            '<wpt lat="42.6977" lon="23.3219"><ele>550.5</ele><time>2024-05-01T08:00:00Z</time>'
            '<name>Начало</name><desc>Паркинг</desc><sym>Flag</sym><type>parking</type></wpt>'
            '<rte><name>План</name>'
            '<rtept lat="42.0" lon="23.0"/><rtept lat="42.0" lon="23.01"/><rtept lat="42.01" lon="23.01"/></rte>'
            '<trk><name>Трасе 1</name><type>hiking</type>'
            '<trkseg>'
            '<trkpt lat="42.0" lon="23.0"><ele>500</ele><time>2024-05-01T08:00:00Z</time></trkpt>'
            '<trkpt lat="42.01" lon="23.0"><ele>510</ele><time>2024-05-01T08:10:00Z</time></trkpt>'
            '</trkseg><trkseg>'
            '<trkpt lat="42.02" lon="23.0"><time>2024-05-01T09:00:00Z</time></trkpt>'
            '<trkpt lat="42.03" lon="23.0"><ele>530</ele><time>2024-05-01T09:30:00Z</time></trkpt>'
            '</trkseg>'
            '<extensions><color>red</color></extensions></trk>'
        )
    text = ('<?xml version="1.0" encoding="{enc}"?>\n'
            '<gpx version="{v}" creator="test" xmlns="http://www.topografix.com/GPX/{ns}">{body}</gpx>\n'
            ).format(enc=encoding, v=version, ns=version.replace('.', '/'), body=body)
    return text.encode(encoding)


def by_type(geojson):
    result = {}
    for f in geojson['features']:
        result.setdefault(f['properties']['type'], []).append(f)
    return result


class ConvertTests(unittest.TestCase):

    def setUp(self):
        self.geojson, self.info = gpx.convert(make_gpx())
        self.types = by_type(self.geojson)

    def test_feature_types_and_order(self):
        types = [f['properties']['type'] for f in self.geojson['features']]
        self.assertEqual(types, ['gpx-track', 'gpx-route', 'gpx-waypoint'])
        self.assertEqual(self.info, {'features': 3, 'warnings': []})
        self.assertNotIn('crs', self.geojson)    # WGS84 is the GeoJSON default

    def test_waypoint(self):
        wpt = self.types['gpx-waypoint'][0]
        self.assertEqual(wpt['geometry'], {'type': 'Point', 'coordinates': [23.3219, 42.6977, 550.5]})
        props = wpt['properties']
        self.assertEqual(props['name'], 'Начало')
        self.assertEqual(props['desc'], 'Паркинг')
        self.assertEqual(props['sym'], 'Flag')
        self.assertEqual(props['category'], 'parking')    # GPX <type> must not replace the style type
        self.assertEqual(props['time'], '2024-05-01T08:00:00Z')
        self.assertEqual(props['ele'], 550.5)

    def test_route(self):
        rte = self.types['gpx-route'][0]
        self.assertEqual(rte['geometry']['type'], 'LineString')
        self.assertEqual(rte['geometry']['coordinates'][1], [23.01, 42.0])
        self.assertAlmostEqual(rte['properties']['length'], 826.6 + 1111.9, delta=2)

    def test_track_segments_elevation_and_times(self):
        trk = self.types['gpx-track'][0]
        self.assertEqual(trk['geometry']['type'], 'MultiLineString')
        first, second = trk['geometry']['coordinates']
        self.assertEqual(first, [[23.0, 42.0, 500.0], [23.0, 42.01, 510.0]])
        self.assertEqual(second, [[23.0, 42.02], [23.0, 42.03]])   # one point without <ele>: 2D
        props = trk['properties']
        self.assertEqual((props['name'], props['category']), ('Трасе 1', 'hiking'))
        self.assertAlmostEqual(props['length'], 2 * 1111.95, delta=1)     # the gap is not counted
        self.assertEqual((props['start_time'], props['end_time']), ('2024-05-01T08:00:00Z', '2024-05-01T09:30:00Z'))

    def test_single_segment_track_is_linestring(self):
        geojson, _ = gpx.convert(make_gpx('<trk><trkseg><trkpt lat="1" lon="2"/><trkpt lat="1.1" lon="2"/></trkseg></trk>'))
        self.assertEqual(geojson['features'][0]['geometry']['type'], 'LineString')

    def test_gpx_10_and_other_encodings(self):
        body = '<wpt lat="42" lon="23"><name>Връх</name></wpt>'
        for version, encoding in (('1.0', 'UTF-8'), ('1.1', 'windows-1251'), ('1.1', 'UTF-16')):
            with self.subTest(version=version, encoding=encoding):
                geojson, _ = gpx.convert(make_gpx(body, version, encoding))
                self.assertEqual(geojson['features'][0]['properties']['name'], 'Връх')

    def test_invalid_points_are_skipped(self):
        body = ('<wpt lat="91" lon="23"/><wpt lat="x" lon="23"/><wpt lon="23"/><wpt lat="nan" lon="1"/>'
                '<wpt lat="42" lon="23"/>'
                '<rte><name>Къс</name><rtept lat="42" lon="23"/></rte>'
                '<trk><name>Празно</name><trkseg/></trk>')
        geojson, info = gpx.convert(make_gpx(body))
        self.assertEqual(len(geojson['features']), 1)
        self.assertTrue(any('4 точки' in w for w in info['warnings']))
        self.assertTrue(any('Къс' in w for w in info['warnings']))
        self.assertTrue(any('Празно' in w for w in info['warnings']))

    def test_rejected_files(self):
        cases = {
            'empty': b'',
            'not XML': b'{"type": "FeatureCollection", "features": []}',
            'not GPX': b'<?xml version="1.0"?><kml><Placemark/></kml>',
            'no features': make_gpx('<metadata><name>x</name></metadata>'),
            'doctype': b'<?xml version="1.0"?><!DOCTYPE gpx [<!ENTITY a "b">]><gpx><wpt lat="1" lon="1"><name>&a;</name></wpt></gpx>',
            'external entity': b'<?xml version="1.0"?><!DOCTYPE gpx [<!ENTITY x SYSTEM "file:///etc/passwd">]><gpx/>',
            'billion laughs': b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">]><gpx>&b;</gpx>',
            'utf-16 doctype': '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE gpx><gpx/>'.encode('utf-16'),
        }
        for name, data in cases.items():
            with self.subTest(name):
                with self.assertRaises(gpx.GpxError):
                    gpx.convert(data)

    def test_random_corruption_never_crashes(self):
        rng = random.Random(1)
        original = make_gpx()
        for _ in range(500):
            data = bytearray(original)
            for _ in range(rng.randint(1, 20)):
                data[rng.randrange(len(data))] = rng.randrange(256)
            try:
                geojson, _ = gpx.convert(bytes(data))
                json.dumps(geojson, allow_nan=False)
            except gpx.GpxError:
                pass


class GpxUploadApiTests(ServerTestCase):

    URL = '/api/projects/p-alpha/layers/gpx'

    def body(self, data=None):
        return {'title': 'walk.gpx', 'data': base64.b64encode(make_gpx() if data is None else data).decode()}

    def test_upload_creates_geojson_layer(self):
        resp = self.client('writer@test.bg').post(self.URL, self.body())
        self.assertEqual(resp.status, 201, resp.text)
        self.assertEqual(resp.json['features'], 3)
        self.assertEqual(resp.json['warnings'], [])

        layer = self.client('reader@test.bg').get('/api/projects/p-alpha/layers/' + resp.json['id']).json
        self.assertEqual(layer['title'], 'walk.gpx')
        self.assertEqual(json.loads(layer['content'])['type'], 'FeatureCollection')

    def test_permissions(self):
        self.assertEqual(Client(self.port).post(self.URL, self.body()).status, 401)
        self.assertEqual(self.client('reader@test.bg').post(self.URL, self.body()).status, 403)
        self.assertEqual(self.client('writer@test.bg').post('/api/projects/missing/layers/gpx', self.body()).status, 404)

    def test_invalid_input(self):
        writer = self.client('writer@test.bg')
        for body in ({'title': 'x.gpx', 'data': 'not base64!'},
                     {'title': 'x.gpx'},
                     {'title': '', 'data': 'AAAA'},
                     self.body(b'<kml/>'),
                     self.body(b'\x00\xff' * 1000)):
            with self.subTest(body=str(body)[:60]):
                resp = writer.post(self.URL, body)
                self.assertEqual(resp.status, 400, resp.text)
                self.assertIn('error', resp.json)


if __name__ == '__main__':
    unittest.main()
