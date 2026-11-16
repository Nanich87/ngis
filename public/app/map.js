'use strict';

let map = (function () {

    // ------------------------------------------------------------------ base maps

    const ESRI_ATTRIBUTION = 'Tiles &copy; <a href="https://www.esri.com/" target="_blank" rel="noopener">Esri</a>, Maxar, Earthstar Geographics';

    const BASE_MAPS = [
        { id: 'osm', label: 'Карта', title: 'OpenStreetMap' },
        { id: 'satellite', label: 'Сателит', title: 'Сателитна (Esri World Imagery)' },
        { id: 'satellite-labels', label: 'Хибрид', title: 'Сателитна с граници и надписи' }
    ];

    function esriLayer(service) {
        return new ol.layer.Tile({
            preload: Infinity,
            source: new ol.source.XYZ({
                url: 'https://server.arcgisonline.com/ArcGIS/rest/services/' + service + '/MapServer/tile/{z}/{y}/{x}',
                attributions: ESRI_ATTRIBUTION,
                maxZoom: 19
            })
        });
    }

    function createBaseLayers() {
        let osm = new ol.layer.Tile({ source: new ol.source.OSM() });
        let imagery = esriLayer('World_Imagery');
        let labels = esriLayer('Reference/World_Boundaries_and_Places');

        return {
            all: [osm, imagery, labels],
            byId: {
                'osm': [osm],
                'satellite': [imagery],
                'satellite-labels': [imagery, labels]
            }
        };
    }

    // OpenLayers 7+ exposes the default controls as ol.control.defaults.defaults().
    function defaultControls() {
        let factory = typeof ol.control.defaults === 'function' ? ol.control.defaults : ol.control.defaults.defaults;

        return factory({ attributionOptions: { collapsible: true } });
    }

    // Font Awesome icons instead of the Unicode arrows, which many fonts lack.
    function fullScreenControl() {
        function icon(code) {
            let span = document.createElement('span');
            span.className = 'fa';
            span.textContent = code;

            return span;
        }

        return new ol.control.FullScreen({
            label: icon('\uf065'),
            labelActive: icon('\uf066'),
            tipLabel: 'Цял екран'
        });
    }

    // ------------------------------------------------------------------ styles

    const FONT = '"Roboto", "Helvetica Neue", Arial, sans-serif';

    function stroke(color, width, lineDash) {
        return new ol.style.Stroke({ color: color, width: width, lineDash: lineDash });
    }

    function fill(color) {
        return new ol.style.Fill({ color: color });
    }

    function circle(radius, strokeColor, strokeWidth, fillColor) {
        return new ol.style.Circle({
            radius: radius,
            stroke: stroke(strokeColor, strokeWidth),
            fill: fillColor ? fill(fillColor) : undefined
        });
    }

    function label(text, color, haloColor, size, weight, offsetX, offsetY) {
        return new ol.style.Text({
            text: text || '',
            font: weight + ' ' + size + 'px ' + FONT,
            fill: fill(color),
            stroke: haloColor ? stroke(haloColor, 3) : undefined,
            offsetX: offsetX || 0,
            offsetY: offsetY || 0
        });
    }

    // Last part of a CAD identifier: district 00833.502 -> 502, parcel 00833.502.10 -> 10,
    // building 00833.502.10.1 -> 1.
    const CAD_NUMBER_RESOLUTION = 0.65;   // parcel and building numbers from zoom 18

    function cadNumber(feature) {
        return String(feature.get('identifier') || '').split('.').pop();
    }

    // Legend metadata + style for every known "<geometry>:<type>" combination.
    // swatch: { shape: 'point'|'line'|'polygon'|'text', stroke, fill, dash, width, radius }
    const STYLE_DEFS = {
        'Point:default': {
            label: 'Точка',
            swatch: { shape: 'point', stroke: 'red', fill: 'white', radius: 5 },
            style: () => new ol.style.Style({ image: circle(5, 'red', 1, 'white') })
        },
        'Point:overpass': {
            label: 'Надлез',
            swatch: { shape: 'point', stroke: 'red', fill: 'white', radius: 6, width: 2 },
            style: f => [
                new ol.style.Style({ image: circle(7, 'red', 2, 'white') }),
                new ol.style.Style({ text: label(f.get('intersection_number'), 'white', 'red', 14, 'bold', 15, -15) }),
                new ol.style.Style({ text: label(f.get('railroad_station'), 'white', 'black', 13, 'normal', 15, 20) })
            ]
        },
        'Point:underpass': {
            label: 'Подлез',
            swatch: { shape: 'point', stroke: 'blue', fill: 'white', radius: 6, width: 2 },
            style: f => [
                new ol.style.Style({ image: circle(7, 'blue', 2, 'white') }),
                new ol.style.Style({ text: label(f.get('intersection_number'), 'white', 'blue', 14, 'bold', 15, -15) }),
                new ol.style.Style({ text: label(f.get('railroad_station'), 'white', 'black', 13, 'normal', 15, 20) })
            ]
        },
        'Point:r-prop-text-private': {
            label: 'Надпис – частен имот',
            swatch: { shape: 'text', fill: 'blue' },
            style: (f, res) => new ol.style.Style({ text: label(res < 0.5 ? f.get('text') : '', 'blue', null, 14, 'normal') })
        },
        'Point:r-prop-text-public': {
            label: 'Надпис – публичен имот',
            swatch: { shape: 'text', fill: 'red' },
            style: (f, res) => new ol.style.Style({ text: label(res < 0.5 ? f.get('text') : '', 'red', null, 14, 'normal') })
        },
        'Point:r-zone-text': {
            label: 'Зона',
            swatch: { shape: 'point', stroke: 'red', radius: 7 },
            style: f => new ol.style.Style({
                image: circle(20, 'red', 1),
                text: label(f.get('text'), 'red', null, 20, 'normal')
            })
        },
        'Point:r-strt-node-text': {
            label: 'Надпис – възел',
            swatch: { shape: 'text', fill: 'red' },
            style: (f, res) => new ol.style.Style({ text: label(res < 0.5 ? f.get('text') : '', 'red', null, 12, 'normal') })
        },
        'Point:r-strt-node': {
            label: 'Възел',
            swatch: { shape: 'point', stroke: 'red', radius: 3 },
            style: () => new ol.style.Style({ image: circle(3, 'red', 1) })
        },
        'LineString:default': {
            label: 'Линия',
            swatch: { shape: 'line', stroke: 'green', width: 1.5 },
            style: () => new ol.style.Style({ stroke: stroke('green', 1.5) })
        },
        'LineString:axis': {
            label: 'Ос',
            swatch: { shape: 'line', stroke: 'red', width: 2 },
            style: () => new ol.style.Style({ stroke: stroke('red', 2) })
        },
        'LineString:r-strt-axis': {
            label: 'Ос на улица',
            swatch: { shape: 'line', stroke: 'red', width: 1, dash: '8 3 0 3' },
            style: () => new ol.style.Style({ stroke: stroke('red', 1, [30, 10, 0, 10]) })
        },
        'LineString:r-prop-line-private': {
            label: 'Граница – частен имот',
            swatch: { shape: 'line', stroke: 'blue', width: 1.5 },
            style: () => new ol.style.Style({ stroke: stroke('blue', 1.5) })
        },
        'LineString:r-prop-line-public': {
            label: 'Граница – публичен имот',
            swatch: { shape: 'line', stroke: 'red', width: 1.5 },
            style: () => new ol.style.Style({ stroke: stroke('red', 1.5) })
        },
        'LineString:r-prop-strt-line': {
            label: 'Улична регулация',
            swatch: { shape: 'line', stroke: 'red', width: 3 },
            style: () => new ol.style.Style({ stroke: stroke('red', 3) })
        },
        'LineString:r-prop-strt-line-bldg': {
            label: 'Улична регулация (застроена)',
            swatch: { shape: 'line', stroke: 'red', width: 3, dash: '8 3' },
            style: () => new ol.style.Style({ stroke: stroke('red', 3, [30, 10]) })
        },
        'LineString:r-curb-line': {
            label: 'Бордюр',
            swatch: { shape: 'line', stroke: 'blue', width: 1 },
            style: () => new ol.style.Style({ stroke: stroke('blue', 1) })
        },
        'LineString:r-curb-line-bldg': {
            label: 'Бордюр (застроен)',
            swatch: { shape: 'line', stroke: 'blue', width: 1, dash: '8 3' },
            style: () => new ol.style.Style({ stroke: stroke('blue', 1, [30, 10]) })
        },
        'MultiLineString:default': {
            label: 'Линии',
            swatch: { shape: 'line', stroke: 'green', width: 1.5 },
            style: () => new ol.style.Style({ stroke: stroke('green', 1.5) })
        },
        'MultiPoint:default': {
            label: 'Точки',
            swatch: { shape: 'point', stroke: 'red', fill: 'white', radius: 5 },
            style: () => new ol.style.Style({ image: circle(5, 'red', 1, 'white') })
        },
        'Polygon:default': {
            label: 'Площ',
            swatch: { shape: 'polygon', stroke: 'blue', fill: 'rgba(0, 0, 255, 0.15)', dash: '3 2', width: 2 },
            style: () => new ol.style.Style({ stroke: stroke('blue', 3, [4]), fill: fill('rgba(0, 0, 255, 0.1)') })
        },
        'Polygon:building': {
            label: 'Сграда',
            swatch: { shape: 'polygon', stroke: 'red', fill: 'rgba(0, 0, 255, 0.15)', dash: '3 2', width: 2 },
            style: () => new ol.style.Style({ stroke: stroke('red', 3, [4]), fill: fill('rgba(0, 0, 255, 0.1)') })
        },
        // Cadastral exchange format (CAD) contours, see server/cad.py.
        'Polygon:cad-territory': {
            label: 'Землище',
            swatch: { shape: 'polygon', stroke: '#e040fb', fill: 'none', dash: '6 3', width: 2 },
            style: () => new ol.style.Style({ stroke: stroke('#e040fb', 3, [12, 6]) })
        },
        'Polygon:cad-district': {
            label: 'Кадастрален район',
            swatch: { shape: 'polygon', stroke: '#ff9800', fill: 'none', width: 2 },
            style: (f, res) => new ol.style.Style({
                stroke: stroke('#ff9800', 2),
                // District number (e.g. 502) from about zoom 12, until parcel numbers take over.
                text: res < 40 && res >= CAD_NUMBER_RESOLUTION ? label(cadNumber(f), 'white', '#e65100', 14, 'bold') : undefined
            })
        },
        'Polygon:cad-parcel': {
            label: 'Поземлен имот',
            maxResolution: 5,     // m/pixel (≈ zoom 15): hidden when zoomed further out
            swatch: { shape: 'polygon', stroke: '#ffd600', fill: 'rgba(255, 214, 0, 0.15)', width: 1 },
            style: (f, res) => new ol.style.Style({
                stroke: stroke('#ffd600', 1),
                fill: fill('rgba(255, 214, 0, 0.08)'),
                // Parcel number once zoomed in.
                text: res < CAD_NUMBER_RESOLUTION ? label(cadNumber(f), 'black', 'rgba(255, 214, 0, 0.9)', 12, 'normal') : undefined
            })
        },
        'Polygon:cad-building': {
            label: 'Сграда',
            maxResolution: 1.5,   // ≈ zoom 17
            swatch: { shape: 'polygon', stroke: '#ff1744', fill: 'rgba(255, 23, 68, 0.35)', width: 1 },
            style: (f, res) => new ol.style.Style({
                stroke: stroke('#ff1744', 1),
                fill: fill('rgba(255, 23, 68, 0.3)'),
                // Building number within its parcel; hidden by OpenLayers when it does not fit inside.
                text: res < CAD_NUMBER_RESOLUTION ? label(cadNumber(f), 'white', '#d50000', 11, 'normal') : undefined
            })
        },
        'Polygon:cad-contour': {
            label: 'Кадастрален контур',
            swatch: { shape: 'polygon', stroke: '#00e5ff', fill: 'rgba(0, 229, 255, 0.15)', width: 1 },
            style: () => new ol.style.Style({ stroke: stroke('#00e5ff', 1), fill: fill('rgba(0, 229, 255, 0.08)') })
        },
        'MultiPolygon:default': {
            label: 'Площи',
            swatch: { shape: 'polygon', stroke: 'yellow', fill: 'rgba(255, 255, 0, 0.15)', width: 1 },
            style: () => new ol.style.Style({ stroke: stroke('yellow', 1), fill: fill('rgba(255, 255, 0, 0.1)') })
        },
        'GeometryCollection:default': {
            label: 'Смесена геометрия',
            swatch: { shape: 'polygon', stroke: 'magenta', fill: 'rgba(255, 0, 255, 0.3)', width: 2 },
            style: () => new ol.style.Style({
                stroke: stroke('magenta', 2),
                fill: fill('rgba(255, 0, 255, 0.3)'),
                image: circle(10, 'magenta', 1)
            })
        }
    };

    ['cad-territory', 'cad-district', 'cad-parcel', 'cad-building', 'cad-contour'].forEach(function (type) {
        STYLE_DEFS['MultiPolygon:' + type] = STYLE_DEFS['Polygon:' + type];
    });

    function featureKey(feature) {
        let geometryType = feature.getGeometry() ? feature.getGeometry().getType() : 'GeometryCollection';
        let type = feature.get('type');
        let key = geometryType + ':' + (type !== undefined ? type : 'default');

        // Unknown types fall back to the default style of their geometry.
        return STYLE_DEFS[key] ? key : geometryType + ':default';
    }

    // Types with maxResolution are not drawn (nor clickable) when zoomed out further.
    function hiddenAt(def, resolution) {
        return Boolean(def.maxResolution && resolution > def.maxResolution);
    }

    function styleFunction(feature, resolution) {
        let def = STYLE_DEFS[featureKey(feature)] || STYLE_DEFS['GeometryCollection:default'];

        return hiddenAt(def, resolution) ? null : def.style(feature, resolution);
    }

    // ------------------------------------------------------------------ map state

    let olMap = null;
    let baseLayers = null;
    let overlay = null;
    let dataLayers = {};      // id -> ol.layer.Vector
    let changeListeners = [];

    function init(options) {
        options = options || {};

        baseLayers = createBaseLayers();
        dataLayers = {};
        changeListeners = [];

        olMap = new ol.Map({
            layers: baseLayers.all.slice(),
            target: options.target || 'map',
            controls: defaultControls().extend([
                fullScreenControl(),
                new ol.control.ScaleLine()
            ]),
            view: new ol.View({
                center: ol.proj.fromLonLat([25.3, 42.7]),
                zoom: 7
            })
        });

        setBaseMap(options.baseMap || 'osm');
        initPopup();

        // Some types appear only when zoomed in, so the legend depends on the zoom level.
        olMap.on('moveend', notifyChange);
    }

    function setBaseMap(id) {
        let visible = baseLayers.byId[id] || baseLayers.byId.osm;

        baseLayers.all.forEach(layer => layer.setVisible(visible.indexOf(layer) !== -1));
    }

    // ------------------------------------------------------------------ projection detection

    const MAP_PROJECTION = 'EPSG:3857';

    // Codes that mean the same projection as one OpenLayers already knows.
    const CRS_ALIASES = {
        'CRS84': 'EPSG:4326',
        'EPSG:900913': 'EPSG:3857',
        'EPSG:102100': 'EPSG:3857',
        'EPSG:102113': 'EPSG:3857'
    };

    // Coordinate systems used for data in Bulgaria, reprojected with proj4js.
    // Definitions from the EPSG registry (epsg.io / spatialreference.org).
    const PROJ4_DEFS = {
        'EPSG:7801': ['BGS2005 / CCS2005', '+proj=lcc +lat_0=42.6678756833333 +lon_0=25.5 +lat_1=42 +lat_2=43.3333333333333 +x_0=500000 +y_0=4725824.3591 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs'],
        'EPSG:7803': ['BGS2005 / UTM 34N', '+proj=utm +zone=34 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs'],
        // The EPSG registry pairs this CRS with the "UTM zone 34N" conversion, contradicting its name
        // and its area of use (east of 24°E = zone 35). Zone 35 is used here.
        'EPSG:7804': ['BGS2005 / UTM 35N', '+proj=utm +zone=35 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs'],
        'EPSG:7805': ['BGS2005 / UTM 36N', '+proj=utm +zone=36 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs'],
        'EPSG:32634': ['WGS84 / UTM 34N', '+proj=utm +zone=34 +datum=WGS84 +units=m +no_defs'],
        'EPSG:32635': ['WGS84 / UTM 35N', '+proj=utm +zone=35 +datum=WGS84 +units=m +no_defs'],
        'EPSG:25834': ['ETRS89 / UTM 34N', '+proj=utm +zone=34 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs'],
        'EPSG:25835': ['ETRS89 / UTM 35N', '+proj=utm +zone=35 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs'],
        'EPSG:4258': ['ETRS89', '+proj=longlat +ellps=GRS80 +no_defs'],
        'EPSG:3035': ['ETRS89 / LAEA Europe', '+proj=laea +lat_0=52 +lon_0=10 +x_0=4321000 +y_0=3210000 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs']
    };

    const PROJECTION_NAMES = {
        'EPSG:4326': 'WGS84',
        'EPSG:3857': 'Web Mercator'
    };

    if (window.proj4 && ol.proj.proj4) {
        Object.keys(PROJ4_DEFS).forEach(function (code) {
            proj4.defs(code, PROJ4_DEFS[code][1]);
            PROJECTION_NAMES[code] = PROJ4_DEFS[code][0];
        });

        ol.proj.proj4.register(proj4);
    }

    function projectionLabel(code) {
        return (PROJECTION_NAMES[code] ? PROJECTION_NAMES[code] + ' ' : '') + '(' + code + ')';
    }

    // "urn:ogc:def:crs:EPSG::7801", "EPSG:7801", "urn:ogc:def:crs:OGC:1.3:CRS84" -> a code
    // OpenLayers can reproject from, or null.
    function crsFromName(name) {
        let text = String(name).trim();
        let match = /(?:EPSG:+|^)(\d+)$/.exec(text);
        let code = match ? 'EPSG:' + match[1] : (/CRS84$/i.test(text) ? 'CRS84' : null);

        if (!code) {
            return null;
        }

        code = CRS_ALIASES[code] || code;

        return ol.proj.get(code) ? code : null;
    }

    // Visits up to `limit` coordinate pairs of any geometry.
    function sampleCoordinates(geojson, limit) {
        let samples = [];

        function walk(coords) {
            if (samples.length >= limit || !Array.isArray(coords)) {
                return;
            }

            if (typeof coords[0] === 'number') {
                samples.push(coords);

                return;
            }

            for (let i = 0; i < coords.length && samples.length < limit; i++) {
                walk(coords[i]);
            }
        }

        function visitGeometry(geometry) {
            if (!geometry) {
                return;
            }

            if (geometry.type === 'GeometryCollection') {
                (geometry.geometries || []).forEach(visitGeometry);
            } else {
                walk(geometry.coordinates);
            }
        }

        if (geojson.type === 'FeatureCollection') {
            (geojson.features || []).forEach(f => samples.length < limit && visitGeometry(f && f.geometry));
        } else if (geojson.type === 'Feature') {
            visitGeometry(geojson.geometry);
        } else {
            visitGeometry(geojson);
        }

        return samples;
    }

    // Returns the projection the file's coordinates are in: the declared "crs" if it is one we
    // know, otherwise WGS84 when every sampled coordinate fits in degrees, otherwise Web Mercator.
    function detectProjection(geojson) {
        let declared = geojson && geojson.crs && geojson.crs.properties && geojson.crs.properties.name;

        if (declared) {
            let known = crsFromName(declared);

            if (known) {
                return known;
            }
        }

        let samples = sampleCoordinates(geojson, 2000);

        if (samples.length === 0) {
            return MAP_PROJECTION;
        }

        let degrees = samples.every(c => Math.abs(c[0]) <= 180 && Math.abs(c[1]) <= 90);

        return degrees ? 'EPSG:4326' : MAP_PROJECTION;
    }

    // Name of a declared "crs" we cannot reproject, or null.
    function unsupportedCrs(geojson) {
        let declared = geojson && geojson.crs && geojson.crs.properties && geojson.crs.properties.name;

        return declared && !crsFromName(declared) ? String(declared) : null;
    }

    function readGeoJSON(geojson) {
        return (new ol.format.GeoJSON()).readFeatures(geojson, {
            dataProjection: detectProjection(geojson),
            featureProjection: MAP_PROJECTION
        });
    }

    // ------------------------------------------------------------------ data layers

    function addLayer(id, title, geojson) {
        if (dataLayers[id]) {
            return dataLayers[id];
        }

        let features = readGeoJSON(geojson);

        let layer = new ol.layer.Vector({
            source: new ol.source.Vector({ features: features }),
            style: styleFunction
        });

        layer.set('title', title);
        layer.on('change:visible', notifyChange);

        dataLayers[id] = layer;
        olMap.addLayer(layer);

        notifyChange();

        return layer;
    }

    function setLayerVisible(id, visible) {
        if (dataLayers[id]) {
            dataLayers[id].setVisible(visible);
        }
    }

    function getFeatureCount(id) {
        return dataLayers[id] ? dataLayers[id].getSource().getFeatures().length : 0;
    }

    function zoomToLayers(ids) {
        let extent = ol.extent.createEmpty();

        ids.forEach(function (id) {
            if (dataLayers[id] && dataLayers[id].getSource().getFeatures().length > 0) {
                ol.extent.extend(extent, dataLayers[id].getSource().getExtent());
            }
        });

        if (ol.extent.isEmpty(extent)) {
            return false;
        }

        olMap.getView().fit(extent, { padding: [40, 40, 40, 40], maxZoom: maxZoomFor(extent), duration: 400 });

        return true;
    }

    // A single point has an empty extent; don't zoom all the way in on it.
    function maxZoomFor(extent) {
        return ol.extent.getWidth(extent) === 0 && ol.extent.getHeight(extent) === 0 ? 15 : 18;
    }

    function onChange(listener) {
        changeListeners.push(listener);
    }

    function notifyChange() {
        changeListeners.forEach(listener => listener());
    }

    // ------------------------------------------------------------------ legend

    // Entries for the feature types present in the visible data layers.
    function getLegend() {
        return legendFor(Object.keys(dataLayers).map(id => dataLayers[id]), olMap.getView().getResolution());
    }

    // hidden: the type is not drawn at this resolution (zoom in to see it).
    function legendFor(layers, resolution) {
        let counts = {};

        layers.forEach(function (layer) {
            if (!layer.getVisible()) {
                return;
            }

            layer.getSource().getFeatures().forEach(function (feature) {
                let key = featureKey(feature);
                counts[key] = (counts[key] || 0) + 1;
            });
        });

        return Object.keys(counts).map(function (key) {
            let def = STYLE_DEFS[key] || STYLE_DEFS['GeometryCollection:default'];

            return {
                key: key,
                label: def.label,
                count: counts[key],
                swatch: swatchSvg(def.swatch),
                hidden: hiddenAt(def, resolution)
            };
        });
    }

    function swatchSvg(s) {
        let dash = s.dash ? ' stroke-dasharray="' + s.dash + '"' : '';
        let width = s.width || 1;
        let body;

        switch (s.shape) {
            case 'point':
                body = '<circle cx="12" cy="8" r="' + (s.radius || 5) + '" stroke="' + s.stroke + '" stroke-width="' + width + '" fill="' + (s.fill || 'none') + '"/>';
                break;
            case 'line':
                body = '<line x1="2" y1="8" x2="22" y2="8" stroke="' + s.stroke + '" stroke-width="' + width + '"' + dash + '/>';
                break;
            case 'polygon':
                body = '<rect x="3" y="2" width="18" height="12" stroke="' + s.stroke + '" stroke-width="' + width + '" fill="' + s.fill + '"' + dash + '/>';
                break;
            default:
                body = '<text x="12" y="13" text-anchor="middle" font-size="13" font-family="sans-serif" fill="' + s.fill + '">Aa</text>';
        }

        return '<svg width="24" height="16" viewBox="0 0 24 16" aria-hidden="true">' + body + '</svg>';
    }

    // ------------------------------------------------------------------ popup

    const PROPERTY_LABELS = {
        name: 'Име',
        type: 'Тип',
        intersection_number: 'Номер',
        railroad_station: 'Гара',
        text: 'Текст',
        identifier: 'Идентификатор',
        area: 'Площ (м²)',
        date: 'Дата',
        cad_type: 'Тип на контура',
        cad_layer: 'Слой'
    };

    function escapeHtml(value) {
        return String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    function initPopup() {
        let container = document.getElementById('popup');
        let content = document.getElementById('popup-content');
        let closer = document.getElementById('popup-closer');

        if (!container) {
            return;
        }

        overlay = new ol.Overlay({
            element: container,
            autoPan: true,
            autoPan: { animation: { duration: 250 } },
            offset: [0, -10]
        });

        olMap.addOverlay(overlay);

        closer.onclick = function () {
            overlay.setPosition(undefined);
            closer.blur();

            return false;
        };

        olMap.on('singleclick', function (e) {
            let hit = olMap.forEachFeatureAtPixel(e.pixel, (feature, layer) => ({ feature: feature, layer: layer }),
                { layerFilter: layer => layer instanceof ol.layer.Vector, hitTolerance: 4 });

            if (!hit) {
                overlay.setPosition(undefined);

                return;
            }

            content.innerHTML = popupHtml(hit.feature, hit.layer);
            overlay.setPosition(e.coordinate);
        });

        olMap.on('pointermove', function (e) {
            if (e.dragging) {
                return;
            }

            let hit = olMap.hasFeatureAtPixel(e.pixel, { layerFilter: layer => layer instanceof ol.layer.Vector, hitTolerance: 4 });

            olMap.getTargetElement().style.cursor = hit ? 'pointer' : '';
        });
    }

    function popupHtml(feature, layer) {
        let def = STYLE_DEFS[featureKey(feature)];
        let props = feature.getProperties();
        let title = props.name || (def ? def.label : 'Обект');
        let rows = '';

        Object.keys(props).forEach(function (key) {
            let value = props[key];

            if (key === feature.getGeometryName() || key === 'name' || value === null || value === undefined || typeof value === 'object') {
                return;
            }

            if (key === 'type' && def) {
                value = /^cad-/.test(value) ? def.label : def.label + ' (' + value + ')';
            }

            rows += '<tr><th>' + escapeHtml(PROPERTY_LABELS[key] || key) + '</th><td>' + escapeHtml(value) + '</td></tr>';
        });

        return '<div class="ol-popup-title">' + escapeHtml(title) + '</div>' +
            '<div class="ol-popup-layer">' + escapeHtml(layer.get('title') || '') + '</div>' +
            (rows ? '<table class="ol-popup-props">' + rows + '</table>' : '');
    }

    // ------------------------------------------------------------------ single-file preview

    // Small standalone map showing one GeoJSON document with the regular styles.
    function createPreview(target, geojson) {
        let features = readGeoJSON(geojson);
        let source = new ol.source.Vector({ features: features });
        let layer = new ol.layer.Vector({ source: source, style: styleFunction });

        let preview = new ol.Map({
            target: target,
            layers: [new ol.layer.Tile({ source: new ol.source.OSM() }), layer],
            controls: defaultControls().extend([
                fullScreenControl(),
                new ol.control.ScaleLine()
            ]),
            view: new ol.View({ center: ol.proj.fromLonLat([25.3, 42.7]), zoom: 7 })
        });

        function fit(extent) {
            if (!ol.extent.isEmpty(extent)) {
                preview.getView().fit(extent, { size: preview.getSize(), padding: [30, 30, 30, 30], maxZoom: maxZoomFor(extent), duration: 300 });
            }
        }

        if (features.length > 0) {
            preview.getView().fit(source.getExtent(), { size: preview.getSize(), padding: [30, 30, 30, 30], maxZoom: maxZoomFor(source.getExtent()) });
        }

        return {
            features: features,
            getLegend: () => legendFor([layer], preview.getView().getResolution()),
            onChange: listener => preview.on('moveend', listener),
            zoomToFeature: function (feature) {
                if (feature.getGeometry()) {
                    fit(feature.getGeometry().getExtent());
                }
            },
            zoomToAll: function () {
                fit(source.getExtent());
            }
        };
    }

    function updateSize() {
        if (olMap) {
            olMap.updateSize();
        }
    }

    return {
        BASE_MAPS: BASE_MAPS,
        init: init,
        setBaseMap: setBaseMap,
        addLayer: addLayer,
        setLayerVisible: setLayerVisible,
        getFeatureCount: getFeatureCount,
        zoomToLayers: zoomToLayers,
        getLegend: getLegend,
        onChange: onChange,
        updateSize: updateSize,
        createPreview: createPreview,
        typeLabel: feature => (STYLE_DEFS[featureKey(feature)] || {}).label,
        detectProjection: detectProjection,
        projectionLabel: projectionLabel,
        unsupportedCrs: unsupportedCrs
    };
}());
