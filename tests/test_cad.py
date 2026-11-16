"""Tests for the CAD (cadastral exchange format) reader and its upload endpoint.

    python3 -m unittest discover -s tests -v
"""
import base64
import json
import random
import unittest

from support import Client, ServerTestCase

import cad  # server/cad.py (support.py puts server/ on sys.path)

REF_N, REF_E = 4723000.0, 673000.0


def _line(number, *points):
    coords = ' '.join('{} {:.3f} {:.3f} 0 0 0;'.format(i + 1, x, y) for i, (x, y) in enumerate(points))
    return 'L 146 {} {} 01.01.2024 0\n{}\n'.format(number, len(points), coords)


def make_cad(coordtype='2005,EVRS2007', name='гр.Тест', encoding='mik', areas=None, extra_layer=''):
    """A tiny CAD file: parcel 1.1 (100×100 m) with enclave 1.2 (20×20 m) and building 1.1.1 (10×10 m)."""
    areas = areas or {'1.1': 9600, '1.2': 400, '1.1.1': 100}
    text = (
        'HEADER\nVERSION 4.02\nEKATTE 99999\nNAME {name}\nREFERENCE {n} {e}\n'
        'COORDTYPE {coordtype}\nEND_HEADER\n\n'
        'LAYER CADASTER\n'
        + _line(1, (0, 0), (0, 100), (100, 100))
        + _line(2, (100, 100), (100, 0), (0, 0))
        + _line(3, (40, 40), (40, 60), (60, 60))
        + _line(4, (40, 40), (60, 40), (60, 60))          # same direction as line 3: must be reversed
        + _line(5, (10, 10), (10, 20), (20, 20), (20, 10), (10, 10))
        + 'C 4 0.0 50 50 01.01.2024 0\n1 2\n'
        + 'C 3 1 50 50 01.01.2024 0\n1 2\n'
        + 'C 2 1.1 30 30 01.01.2024 0\n1 2\n'
        + 'C 2 1.2 50 50 01.01.2024 0\n3 4\n'
        + 'C 1 1.1.1 15 15 01.01.2024 0\n5\n'
        + extra_layer
        + 'END_LAYER\n\nCONTROL CADASTER\n'
        + ''.join('CONTUR_AREA {} {:.3f}\n'.format(k, v) for k, v in areas.items())
        + 'CONTUR_NESTED 1.1 1.2\nCONTUR_SURROUND 1.2 1.1\nEND_CONTROL\n'
    ).format(name=name, n=REF_N, e=REF_E, coordtype=coordtype).replace('\n', '\r\n')
    if encoding == 'mik':
        return bytes(0x80 + ord(c) - 0x410 if 'А' <= c <= 'я' else ord(c) for c in text)
    return text.encode(encoding)


def by_id(geojson):
    return {f['properties']['identifier']: f for f in geojson['features']}


def signed_area(ring):
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:])) / 2


class DecodeTests(unittest.TestCase):

    def test_encodings(self):
        for encoding, label in (('mik', 'МИК'), ('cp1251', 'windows-1251'), ('utf-8', 'UTF-8')):
            with self.subTest(encoding=encoding):
                geojson, info = cad.convert(make_cad(encoding=encoding))
                self.assertEqual(info['encoding'], label)
                self.assertEqual(by_id(geojson)['99999']['properties']['name'], 'Землище гр.Тест')

    def test_mik_table(self):
        # Lowercase р–я are where cp866 has box drawing characters.
        self.assertEqual(cad.decode(bytes([0xA3, 0xB0, 0x2E, 0x80, 0xB5]))[0], 'гр.Ах')


class ConvertTests(unittest.TestCase):

    def setUp(self):
        self.geojson, self.info = cad.convert(make_cad())
        self.features = by_id(self.geojson)

    def test_feature_types_and_order(self):
        types = [f['properties']['type'] for f in self.geojson['features']]
        self.assertEqual(types, ['cad-territory', 'cad-district', 'cad-parcel', 'cad-parcel', 'cad-building'])
        self.assertEqual(self.info['warnings'], [])
        self.assertEqual(self.geojson['crs']['properties']['name'], 'urn:ogc:def:crs:EPSG::7801')

    def test_identifiers_include_ekatte(self):
        self.assertEqual(set(self.features), {'99999', '99999.1', '99999.1.1', '99999.1.2', '99999.1.1.1'})
        self.assertEqual(self.features['99999.1.1']['properties']['area'], 9600)

    def test_coordinates_are_absolute_easting_northing(self):
        ring = self.features['99999.1.1.1']['geometry']['coordinates'][0]
        self.assertIn([REF_E + 10, REF_N + 10], ring)
        self.assertIn([REF_E + 20, REF_N + 10], ring)   # x (north) 10, y (east) 20
        eastings = [c[0] for c in ring]
        self.assertEqual((min(eastings), max(eastings)), (REF_E + 10, REF_E + 20))

    def test_enclave_becomes_hole(self):
        rings = self.features['99999.1.1']['geometry']['coordinates']
        self.assertEqual(len(rings), 2)
        self.assertAlmostEqual(abs(signed_area(rings[0])) - abs(signed_area(rings[1])), 9600)
        # RFC 7946: outer ring counterclockwise, holes clockwise.
        self.assertGreater(signed_area(rings[0]), 0)
        self.assertLess(signed_area(rings[1]), 0)
        self.assertEqual(rings[0][0], rings[0][-1])
        self.assertEqual(len(self.features['99999.1.2']['geometry']['coordinates']), 1)

    def test_area_mismatch_is_reported(self):
        _, info = cad.convert(make_cad(areas={'1.1': 10000, '1.2': 400, '1.1.1': 100}))
        self.assertTrue(any('официалната площ' in w and '1.1' in w for w in info['warnings']))

    def test_unclosed_contour_is_skipped(self):
        extra = _line(6, (0, 200), (0, 300)) + 'C 2 1.3 0 250 01.01.2024 0\n6\n'
        geojson, info = cad.convert(make_cad(extra_layer=extra))
        self.assertNotIn('99999.1.3', by_id(geojson))
        self.assertTrue(any('1.3' in w for w in info['warnings']))

    def test_unsupported_records_are_reported(self):
        _, info = cad.convert(make_cad(extra_layer='T 1 1 5 5 0 0 0 0 0 "текст"\n'))
        self.assertTrue(any('текстове' in w for w in info['warnings']))

    def test_rejected_files(self):
        cases = {
            '1970 system': make_cad(coordtype='1970,BALT'),
            'no coordtype': make_cad().replace(b'COORDTYPE 2005,EVRS2007', b''),
            'not CAD': b'{"type": "FeatureCollection", "features": []}',
            'empty': b'',
            'bad number': make_cad().replace(b'10.000 20.000', b'1e999 nan'),
        }
        for name, data in cases.items():
            with self.subTest(name):
                with self.assertRaises(cad.CadError):
                    cad.convert(data)

    def test_random_corruption_never_crashes(self):
        rng = random.Random(1)
        original = make_cad()
        for _ in range(500):
            data = bytearray(original)
            for _ in range(rng.randint(1, 20)):
                data[rng.randrange(len(data))] = rng.randrange(256)
            try:
                geojson, _ = cad.convert(bytes(data))
                json.dumps(geojson, allow_nan=False)
            except cad.CadError:
                pass


class CadUploadApiTests(ServerTestCase):

    URL = '/api/projects/p-alpha/layers/cad'

    def body(self, data=None):
        return {'title': 'test.cad', 'data': base64.b64encode(make_cad() if data is None else data).decode()}

    def test_upload_creates_geojson_layer(self):
        resp = self.client('writer@test.bg').post(self.URL, self.body())
        self.assertEqual(resp.status, 201, resp.text)
        self.assertEqual(resp.json['features'], 5)
        self.assertEqual(resp.json['encoding'], 'МИК')

        layer = self.client('reader@test.bg').get('/api/projects/p-alpha/layers/' + resp.json['id']).json
        self.assertEqual(layer['title'], 'test.cad')
        self.assertEqual(json.loads(layer['content'])['type'], 'FeatureCollection')

    def test_permissions(self):
        self.assertEqual(Client(self.port).post(self.URL, self.body()).status, 401)
        self.assertEqual(self.client('reader@test.bg').post(self.URL, self.body()).status, 403)
        self.assertEqual(self.client('writer@test.bg').post('/api/projects/missing/layers/cad', self.body()).status, 404)

    def test_invalid_input(self):
        writer = self.client('writer@test.bg')
        for body in ({'title': 'x.cad', 'data': 'not base64!'},
                     {'title': 'x.cad'},
                     {'title': '', 'data': 'AAAA'},
                     {'title': 'x.cad', 'data': 123},
                     self.body(make_cad(coordtype='1970')),
                     self.body(b'\x00\xff' * 1000)):
            with self.subTest(body=str(body)[:60]):
                resp = writer.post(self.URL, body)
                self.assertEqual(resp.status, 400, resp.text)
                self.assertIn('error', resp.json)


if __name__ == '__main__':
    unittest.main()
