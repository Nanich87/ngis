"""Reader for the Bulgarian cadastral exchange format (CAD, "формат за обмен на кадастрални данни").

Converts the geometry of a CAD file into a GeoJSON FeatureCollection in BGS2005 / CCS2005
(EPSG:7801), which the frontend reprojects with proj4js.

Supported:
  * HEADER  – EKATTE, NAME, REFERENCE (origin of the local coordinates), COORDTYPE.
  * LAYER   – L (lines) and C (contours, i.e. polygons built from line numbers).
  * CONTROL – CONTUR_AREA (official areas, used as a check) and CONTUR_NESTED (enclaves,
              which become holes in the surrounding polygon).
Not yet supported (counted and reported): points, symbols, texts, TABLE sections with attributes.

Coordinates in the file are geodetic: X = northing, Y = easting, both relative to REFERENCE.
Only BGS2005 files are accepted; the 1970 system has no official public transformation.

Text encoding: MIK (Bulgarian DOS code page, the usual one for CAD files), windows-1251 or UTF-8,
detected automatically.
"""

from collections import defaultdict

CRS_NAME = 'urn:ogc:def:crs:EPSG::7801'

# Contour types of the CADASTER layer: (GeoJSON "type" property, readable name).
CONTOUR_TYPES = {
    '1': ('cad-building', 'Сграда'),
    '2': ('cad-parcel', 'Поземлен имот'),
    '3': ('cad-district', 'Кадастрален район'),
    '4': ('cad-territory', 'Землище'),
}
# Drawing order: large areas first, buildings on top.
DRAW_ORDER = {'cad-territory': 0, 'cad-district': 1, 'cad-contour': 2, 'cad-parcel': 2, 'cad-building': 3}

MAX_POINTS = 5_000_000          # guards memory use on huge or malicious files
AREA_TOLERANCE = 0.5            # m²; the official areas are rounded by the producing software
AREA_RELATIVE_TOLERANCE = 0.001


class CadError(ValueError):
    """The file cannot be converted; the message is shown to the user (in Bulgarian)."""


# --------------------------------------------------------------------------- encoding

# MIK = code page 437 with А–Я, а–я in 0x80–0xBF.
_MIK_TABLE = {b: chr(0x410 + b - 0x80) if b < 0xC0 else bytes([b]).decode('cp437') for b in range(0x80, 0x100)}


def decode(data):
    """Returns (text, encoding name)."""
    if data.startswith(b'\xef\xbb\xbf'):
        data = data[3:]
    high = [b for b in data if b >= 0x80]
    if not high:
        return data.decode('ascii'), 'ASCII'
    try:
        return data.decode('utf-8'), 'UTF-8'
    except UnicodeDecodeError:
        pass
    # Cyrillic letters are 0x80–0xBF in MIK and 0xC0–0xFF in windows-1251.
    if sum(1 for b in high if b >= 0xC0) > len(high) / 2:
        return data.decode('cp1251', errors='replace'), 'windows-1251'
    return data.decode('latin-1').translate(_MIK_TABLE), 'МИК'


# --------------------------------------------------------------------------- parsing

def _number(text, what):
    try:
        value = float(text)
    except ValueError:
        raise CadError('Невалидно число „{}“ ({}).'.format(text[:20], what)) from None
    if value != value or value in (float('inf'), float('-inf')):
        raise CadError('Невалидно число „{}“ ({}).'.format(text[:20], what))
    return value


class _Layer:
    def __init__(self, name):
        self.name = name
        self.lines = {}          # line number -> [(x, y), ...]
        self.contours = []       # dicts: type, id, label, date, lines
        self.areas = {}          # contour id -> official area
        self.nested = {}         # contour id -> [enclave ids]
        self.skipped = defaultdict(int)


def parse(text):
    header = {}
    layers = {}
    rows = text.splitlines()
    i = 0
    section = None           # ('HEADER',) | ('LAYER', layer) | ('CONTROL', layer) | ('TABLE',)
    points = 0

    def continuation(start):
        # Data lines of a record start with a digit (or a minus sign); the next record starts with a letter.
        j = start
        while j < len(rows):
            stripped = rows[j].strip()
            if not stripped or not (stripped[0].isdigit() or stripped[0] in '-.'):
                break
            j += 1
        return j

    while i < len(rows):
        tokens = rows[i].split()
        if not tokens:
            i += 1
            continue
        key = tokens[0].upper()

        if key == 'HEADER':
            section = ('HEADER',)
        elif key in ('END_HEADER', 'END_LAYER', 'END_CONTROL', 'END_TABLE'):
            section = None
        elif key in ('LAYER', 'CONTROL'):
            name = tokens[1] if len(tokens) > 1 else ''
            layer = layers.setdefault(name, _Layer(name))
            section = (key, layer)
        elif key == 'TABLE':
            section = ('TABLE',)
        elif section is None:
            pass
        elif section[0] == 'HEADER':
            header[key] = rows[i].strip()[len(tokens[0]):].strip()
        elif section[0] == 'LAYER':
            layer = section[1]
            end = continuation(i + 1)
            if key == 'L':
                if len(tokens) < 3:
                    raise CadError('Невалиден запис за линия на ред {}.'.format(i + 1))
                coords = []
                for row in rows[i + 1:end]:
                    for item in row.split(';'):
                        parts = item.split()
                        if len(parts) >= 3:
                            coords.append((_number(parts[1], 'ред {}'.format(i + 1)),
                                           _number(parts[2], 'ред {}'.format(i + 1))))
                points += len(coords)
                if points > MAX_POINTS:
                    raise CadError('Файлът съдържа твърде много точки.')
                if len(coords) >= 2:
                    layer.lines[tokens[2]] = coords
            elif key == 'C':
                if len(tokens) < 5:
                    raise CadError('Невалиден запис за контур на ред {}.'.format(i + 1))
                line_ids = [n for row in rows[i + 1:end] for n in row.split()]
                layer.contours.append({
                    'type': tokens[1],
                    'id': tokens[2],
                    'label': (_number(tokens[3], 'ред {}'.format(i + 1)), _number(tokens[4], 'ред {}'.format(i + 1))),
                    'date': tokens[5] if len(tokens) > 5 else None,
                    'lines': line_ids,
                })
            else:
                layer.skipped[key] += 1
            i = end
            continue
        elif section[0] == 'CONTROL':
            layer = section[1]
            if key == 'CONTUR_AREA' and len(tokens) >= 3:
                layer.areas[tokens[1]] = _number(tokens[2], 'площ на ' + tokens[1])
            elif key == 'CONTUR_NESTED' and len(tokens) >= 3:
                layer.nested.setdefault(tokens[1], []).extend(tokens[2:])
        i += 1

    if 'HEADER' not in (r.split()[0].upper() for r in rows[:50] if r.split()):
        raise CadError('Файлът не е във формат CAD (липсва HEADER).')
    return header, layers


# --------------------------------------------------------------------------- geometry

def _key(point):
    return (round(point[0], 3), round(point[1], 3))


def _rings(segments):
    """Joins line segments end to end into closed rings. Returns None if a ring stays open."""
    by_end = defaultdict(list)
    for index, seg in enumerate(segments):
        by_end[_key(seg[0])].append(index)
        by_end[_key(seg[-1])].append(index)
    used = [False] * len(segments)
    rings = []

    for start in range(len(segments)):
        if used[start]:
            continue
        used[start] = True
        ring = list(segments[start])
        while _key(ring[-1]) != _key(ring[0]):
            end = _key(ring[-1])
            candidates = [k for k in by_end[end] if not used[k]]
            if not candidates:
                return None
            k = candidates[0]
            used[k] = True
            seg = segments[k]
            ring.extend(seg[1:] if _key(seg[0]) == end else reversed(seg[:-1]))
        ring[-1] = ring[0]
        if len(ring) >= 4:
            rings.append(ring)
    return rings


def _signed_area(ring):
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:])) / 2


def _inside(point, ring):
    x, y = point
    result = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            result = not result
    return result


def _ring_inside(ring, outer):
    # Rings may share vertices with the outer ring, so let the majority of vertices decide.
    votes = sum(1 if _inside(p, outer) else -1 for p in ring[:-1])
    return votes > 0


def _polygons(rings):
    """Groups rings into polygons: [[outer, hole, ...], ...]; returns (polygons, area)."""
    rings = sorted(rings, key=lambda r: abs(_signed_area(r)), reverse=True)
    polygons = []
    for ring in rings:
        owner = None
        for polygon in reversed(polygons):        # smallest enclosing outer ring wins
            if _ring_inside(ring, polygon[0]) and not any(_ring_inside(ring, h) for h in polygon[1:]):
                owner = polygon
                break
        if owner is None:
            polygons.append([ring])
        else:
            owner.append(ring)
    area = sum(abs(_signed_area(p[0])) - sum(abs(_signed_area(h)) for h in p[1:]) for p in polygons)
    return polygons, area


def _to_lonlat_order(polygon, ref_n, ref_e):
    """Local (x=north, y=east) -> absolute [easting, northing]; outer ring CCW, holes CW (RFC 7946)."""
    result = []
    for index, ring in enumerate(polygon):
        coords = [[round(ref_e + y, 3), round(ref_n + x, 3)] for x, y in ring]
        ccw = _signed_area(coords) > 0
        if ccw != (index == 0):
            coords.reverse()
        result.append(coords)
    return result


# --------------------------------------------------------------------------- conversion

def convert(data):
    """CAD file bytes -> (GeoJSON dict, info dict with counts and warnings)."""
    text, encoding = decode(data)
    header, layers = parse(text)

    coordtype = header.get('COORDTYPE', '')
    system = coordtype.split(',')[0].strip()
    if not system:
        raise CadError('Във файла липсва координатна система (COORDTYPE).')
    if system != '2005':
        raise CadError('Координатна система „{}“ не се поддържа. Поддържа се само БГС2005 (COORDTYPE 2005).'.format(system))

    try:
        ref_n, ref_e = (float(v) for v in header.get('REFERENCE', '0 0').split()[:2])
    except ValueError:
        raise CadError('Невалиден REFERENCE в заглавната част.') from None

    ekatte = header.get('EKATTE', '').strip()
    place = header.get('NAME', '').strip()
    features = []
    warnings = []
    skipped = defaultdict(int)

    for layer in layers.values():
        for record, count in layer.skipped.items():
            skipped[record] += count
        by_id = {c['id']: c for c in layer.contours}
        bad_area = []
        unclosed = []

        for contour in layer.contours:
            segments = [layer.lines[n] for n in contour['lines'] if n in layer.lines]
            if len(segments) != len(contour['lines']) or not segments:
                unclosed.append(contour['id'])
                continue
            rings = _rings(segments)
            if not rings:
                unclosed.append(contour['id'])
                continue

            # Enclaves: lines shared by two neighbouring enclaves cancel out, leaving their outline.
            counts = defaultdict(int)
            for inner in layer.nested.get(contour['id'], []):
                for n in by_id.get(inner, {}).get('lines', []):
                    counts[n] += 1
            hole_segments = [layer.lines[n] for n, c in counts.items() if c % 2 == 1 and n in layer.lines]
            holes = _rings(hole_segments) if hole_segments else []
            polygons, area = _polygons(rings + (holes or []))

            official = layer.areas.get(contour['id'])
            if official is not None and abs(area - official) > max(AREA_TOLERANCE, official * AREA_RELATIVE_TOLERANCE):
                bad_area.append(contour['id'])

            if layer.name == 'CADASTER' and contour['type'] in CONTOUR_TYPES:
                kind, kind_name = CONTOUR_TYPES[contour['type']]
            else:
                kind, kind_name = 'cad-contour', 'Контур (тип {})'.format(contour['type'])

            identifier = contour['id']
            if ekatte and kind in ('cad-building', 'cad-parcel', 'cad-district'):
                identifier = ekatte + '.' + identifier
            if kind == 'cad-territory':
                identifier = ekatte or identifier
                name = 'Землище ' + (place or ekatte)
            elif kind == 'cad-district':
                name = 'Кадастрален район ' + contour['id']
            else:
                name = identifier

            coords = [_to_lonlat_order(p, ref_n, ref_e) for p in polygons]
            geometry = ({'type': 'Polygon', 'coordinates': coords[0]} if len(coords) == 1
                        else {'type': 'MultiPolygon', 'coordinates': coords})
            properties = {'name': name, 'type': kind, 'identifier': identifier}
            if kind == 'cad-contour':
                properties['cad_type'] = contour['type']
            if layer.name != 'CADASTER':
                properties['cad_layer'] = layer.name
            properties['area'] = official if official is not None else round(area, 2)
            if contour['date']:
                properties['date'] = contour['date']
            features.append({'type': 'Feature', 'properties': properties, 'geometry': geometry})

        if unclosed:
            warnings.append('{} контура в слой {} не могат да бъдат затворени и са пропуснати: {}'.format(
                len(unclosed), layer.name, ', '.join(unclosed[:10]) + (' …' if len(unclosed) > 10 else '')))
        if bad_area:
            warnings.append('{} контура в слой {} се различават от официалната площ: {}'.format(
                len(bad_area), layer.name, ', '.join(bad_area[:10]) + (' …' if len(bad_area) > 10 else '')))

    names = {'P': 'точки', 'S': 'символи', 'T': 'текстове'}
    for record, count in sorted(skipped.items()):
        warnings.append('Пропуснати {} {} (още не се поддържат).'.format(count, names.get(record, 'записа „' + record + '“')))
    if 'TABLE' in text and any(r.strip().upper().startswith('TABLE') for r in text.splitlines()):
        warnings.append('Таблиците с атрибути (TABLE) още не се поддържат.')

    if not features:
        raise CadError('Във файла няма контури, които да могат да бъдат показани.')

    features.sort(key=lambda f: DRAW_ORDER.get(f['properties']['type'], 2))
    geojson = {
        'type': 'FeatureCollection',
        'name': place or ekatte,
        'crs': {'type': 'name', 'properties': {'name': CRS_NAME}},
        'features': features,
    }
    info = {'features': len(features), 'encoding': encoding, 'warnings': warnings}
    return geojson, info
