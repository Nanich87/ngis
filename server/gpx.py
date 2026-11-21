"""Reader for GPX files (GPS Exchange Format, versions 1.0 and 1.1).

Converts a GPX file into a GeoJSON FeatureCollection in WGS84 (longitude, latitude), which is the
GeoJSON default, so no "crs" member is written.

  * wpt – Point, type "gpx-waypoint"
  * rte – LineString, type "gpx-route"
  * trk – LineString (one segment) or MultiLineString (several), type "gpx-track"

Elevation becomes the third coordinate when every point of a geometry has one. Extensions and
metadata are ignored. Points with missing or out-of-range coordinates are skipped with a warning.
"""

import math
import xml.etree.ElementTree as ET
from xml.parsers import expat

from i18n import _

MAX_POINTS = 5_000_000          # guards memory use on huge or malicious files
EARTH_RADIUS = 6_371_008.8      # m, mean radius

# Text properties copied from <wpt>, <rte> and <trk> (GPX <type> is renamed: "type" selects the style).
TEXT_FIELDS = (('name', 'name'), ('desc', 'desc'), ('cmt', 'cmt'), ('src', 'src'), ('type', 'category'))
WAYPOINT_FIELDS = TEXT_FIELDS + (('sym', 'sym'), ('time', 'time'))


class GpxError(ValueError):
    """The file cannot be converted; the message (an i18n Message) is shown to the user."""


def _local(tag):
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''


def _children(element, name):
    return [child for child in element if _local(child.tag) == name]


def _text(element, name):
    for child in _children(element, name):
        value = (child.text or '').strip()
        if value:
            return value
    return None


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _parse_xml(data):
    if not data.strip():
        raise GpxError(_('Файлът е празен.'))
    # No DTDs: rules out entity expansion ("billion laughs") and external entities. The C
    # ElementTree parser does not expose expat's handlers, so a plain expat pass checks first.
    def reject_dtd(*args):
        raise GpxError(_('GPX файлът съдържа DOCTYPE декларация, която не се поддържа.'))

    try:
        check = expat.ParserCreate()
        check.StartDoctypeDeclHandler = reject_dtd
        check.EntityDeclHandler = reject_dtd
        check.Parse(data, True)
        root = ET.fromstring(data)
    except GpxError:
        raise
    except (expat.ExpatError, ET.ParseError) as e:
        raise GpxError(_('Файлът не е валиден XML ({error}).', error=str(e)))
    except (ValueError, LookupError):
        raise GpxError(_('Файлът не е валиден XML.'))
    if _local(root.tag) != 'gpx':
        raise GpxError(_('Файлът не е GPX (основният елемент трябва да е <gpx>).'))
    return root


class _Reader:

    def __init__(self):
        self.points = 0
        self.skipped = 0

    def point(self, element):
        """[lon, lat] or [lon, lat, ele]; None for an invalid point."""
        lat = _number(element.get('lat'))
        lon = _number(element.get('lon'))
        if lat is None or lon is None or not -90 <= lat <= 90 or not -180 <= lon <= 180:
            self.skipped += 1
            return None
        self.points += 1
        if self.points > MAX_POINTS:
            raise GpxError(_('Файлът има повече от {max} точки.', max=MAX_POINTS))
        ele = _number(_text(element, 'ele'))
        return [lon, lat] if ele is None else [lon, lat, ele]

    def line(self, elements):
        coords = [c for c in map(self.point, elements) if c is not None]
        # Mixed 2D/3D is not allowed within one geometry: drop elevation unless every point has it.
        if any(len(c) == 2 for c in coords):
            coords = [c[:2] for c in coords]
        return coords


def _length(lines):
    """Length in metres along the great circle."""
    total = 0.0
    for line in lines:
        for (lon1, lat1, *_), (lon2, lat2, *_) in zip(line, line[1:]):
            p1, p2 = math.radians(lat1), math.radians(lat2)
            dp, dl = p2 - p1, math.radians(lon2 - lon1)
            a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
            total += 2 * EARTH_RADIUS * math.asin(min(1.0, math.sqrt(a)))
    return round(total, 1)


def _properties(element, kind, fields):
    props = {'type': kind}
    for tag, key in fields:
        value = _text(element, tag)
        if value is not None:
            props[key] = value
    return props


def _times(elements):
    times = [t for t in (_text(e, 'time') for e in elements) if t is not None]
    return (min(times), max(times)) if times else (None, None)   # ISO 8601 UTC sorts as text


def _feature(geometry, props):
    return {'type': 'Feature', 'geometry': geometry, 'properties': props}


def convert(data):
    """GPX bytes -> (GeoJSON dict, info dict with 'features' and 'warnings')."""
    root = _parse_xml(data)
    reader = _Reader()
    tracks, routes, waypoints = [], [], []
    warnings = []

    for trk in _children(root, 'trk'):
        segments, elements = [], []
        for seg in _children(trk, 'trkseg'):
            points = _children(seg, 'trkpt')
            coords = reader.line(points)
            if len(coords) >= 2:
                segments.append(coords)
                elements.extend(points)
        props = _properties(trk, 'gpx-track', TEXT_FIELDS)
        if not segments:
            warnings.append(_('Трасето „{name}“ няма сегмент с поне 2 точки и е пропуснато.', name=props.get('name', '')))
            continue
        props['length'] = _length(segments)
        start, end = _times(elements)
        if start:
            props['start_time'], props['end_time'] = start, end
        geometry = ({'type': 'LineString', 'coordinates': segments[0]} if len(segments) == 1
                    else {'type': 'MultiLineString', 'coordinates': segments})
        tracks.append(_feature(geometry, props))

    for rte in _children(root, 'rte'):
        coords = reader.line(_children(rte, 'rtept'))
        props = _properties(rte, 'gpx-route', TEXT_FIELDS)
        if len(coords) < 2:
            warnings.append(_('Маршрутът „{name}“ има по-малко от 2 точки и е пропуснат.', name=props.get('name', '')))
            continue
        props['length'] = _length([coords])
        routes.append(_feature({'type': 'LineString', 'coordinates': coords}, props))

    for wpt in _children(root, 'wpt'):
        coords = reader.point(wpt)
        if coords is None:
            continue
        props = _properties(wpt, 'gpx-waypoint', WAYPOINT_FIELDS)
        if len(coords) == 3:
            props['ele'] = coords[2]
        waypoints.append(_feature({'type': 'Point', 'coordinates': coords}, props))

    if reader.skipped:
        warnings.append(_('Пропусната е 1 точка с липсващи или невалидни координати.') if reader.skipped == 1 else
                        _('Пропуснати са {count} точки с липсващи или невалидни координати.', count=reader.skipped))

    # Drawing order: tracks, routes, then waypoints on top.
    features = tracks + routes + waypoints
    if not features:
        raise GpxError(_('Файлът не съдържа точки, маршрути или трасета.'))

    return {'type': 'FeatureCollection', 'features': features}, {'features': len(features), 'warnings': warnings}
