'use strict';

let map = (function () {

    // ------------------------------------------------------------------ base maps

    const ESRI_ATTRIBUTION = new ol.Attribution({
        html: 'Tiles &copy; <a href="https://www.esri.com/" target="_blank" rel="noopener">Esri</a>, Maxar, Earthstar Geographics'
    });

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
                attributions: [ESRI_ATTRIBUTION],
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

    function featureKey(feature) {
        let geometryType = feature.getGeometry() ? feature.getGeometry().getType() : 'GeometryCollection';
        let type = feature.get('type');
        let key = geometryType + ':' + (type !== undefined ? type : 'default');

        // Unknown types fall back to the default style of their geometry.
        return STYLE_DEFS[key] ? key : geometryType + ':default';
    }

    function styleFunction(feature, resolution) {
        let def = STYLE_DEFS[featureKey(feature)] || STYLE_DEFS['GeometryCollection:default'];

        return def.style(feature, resolution);
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
            loadTilesWhileInteracting: true,
            controls: ol.control.defaults({ attributionOptions: { collapsible: true } }).extend([
                new ol.control.FullScreen(),
                new ol.control.ScaleLine()
            ]),
            view: new ol.View({
                center: ol.proj.fromLonLat([25.3, 42.7]),
                zoom: 7
            })
        });

        setBaseMap(options.baseMap || 'osm');
        initPopup();
    }

    function setBaseMap(id) {
        let visible = baseLayers.byId[id] || baseLayers.byId.osm;

        baseLayers.all.forEach(layer => layer.setVisible(visible.indexOf(layer) !== -1));
    }

    // ------------------------------------------------------------------ data layers

    function addLayer(id, title, geojson) {
        if (dataLayers[id]) {
            return dataLayers[id];
        }

        let features = (new ol.format.GeoJSON()).readFeatures(geojson);

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

        olMap.getView().fit(extent, { padding: [40, 40, 40, 40], maxZoom: 18, duration: 400 });

        return true;
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
        let counts = {};

        Object.keys(dataLayers).forEach(function (id) {
            let layer = dataLayers[id];

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

            return { key: key, label: def.label, count: counts[key], swatch: swatchSvg(def.swatch) };
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
        text: 'Текст'
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
            autoPanAnimation: { duration: 250 },
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
                value = def.label + ' (' + value + ')';
            }

            rows += '<tr><th>' + escapeHtml(PROPERTY_LABELS[key] || key) + '</th><td>' + escapeHtml(value) + '</td></tr>';
        });

        return '<div class="ol-popup-title">' + escapeHtml(title) + '</div>' +
            '<div class="ol-popup-layer">' + escapeHtml(layer.get('title') || '') + '</div>' +
            (rows ? '<table class="ol-popup-props">' + rows + '</table>' : '');
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
        updateSize: updateSize
    };
}());
