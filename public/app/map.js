'use strict';

let map = (function () {

    const BING_MAPS_KEY = 'AinK94rmhEYAloFP7dcaPS64T6HXZsv8MROuBIkk9tdgxlPruC050d9qHP0uo12d';

    let mapLayers = [];

    let mapExtent = {
        minX: null,
        minY: null,
        maxX: null,
        maxY: null
    }

    let olMap;

    let roadMapBaseLayer = new ol.layer.Tile({
        name: 'Road',
        visible: false,
        preload: Infinity,
        source: new ol.source.BingMaps({
            key: BING_MAPS_KEY,
            imagerySet: 'Road'
        })
    });

    let aerialMapBaseLayer = new ol.layer.Tile({
        name: 'Aerial',
        visible: false,
        preload: Infinity,
        source: new ol.source.BingMaps({
            key: BING_MAPS_KEY,
            imagerySet: 'Aerial'
        })
    });

    let aerialWithLabelsMapBaseLayer = new ol.layer.Tile({
        name: 'AerialWithLabels',
        visible: false,
        preload: Infinity,
        source: new ol.source.BingMaps({
            key: BING_MAPS_KEY,
            imagerySet: 'AerialWithLabels'
        })
    });

    let openStreetMapBaseLayer = new ol.layer.Tile({
        name: 'OpenStreetMaps',
        source: new ol.source.OSM()
    });

    let baseMapLayers = {
        road: roadMapBaseLayer,
        aerial: aerialMapBaseLayer,
        aerialWithLabels: aerialWithLabelsMapBaseLayer,
        osm: openStreetMapBaseLayer
    };

    function init() {
        olMap = new ol.Map({
            layers: [baseMapLayers.road, baseMapLayers.aerial, baseMapLayers.aerialWithLabels, baseMapLayers.osm],
            target: 'map',
            loadTilesWhileInteracting: true,
            view: new ol.View({
                center: ol.proj.transform([23.3, 42.7], 'EPSG:4326', 'EPSG:3857'),
                zoom: 8
            })
        });

        _addLayers(mapLayers);

        olMap.addControl(new ol.control.FullScreen());

        let popupContainer = document.getElementById('popup');
        let popupContent = document.getElementById('popup-content');
        let popupCloser = document.getElementById('popup-closer');

        popupCloser.onclick = function () {
            overlay.setPosition(undefined);
            popupCloser.blur();

            return false;
        };

        let overlay = new ol.Overlay({
            element: popupContainer,
            autoPan: true,
            offset: [0, -10]
        });

        olMap.addOverlay(overlay);

        olMap.on('singleclick', function (e) {
            let feature = this.forEachFeatureAtPixel(e.pixel, function (feature, layer) {
                return feature;
            });

            if (feature) {
                let content = '<p>Type: ' + feature.get('type') + '</p>';

                popupContent.innerHTML = content;

                overlay.setPosition(e.coordinate);

                // console.info(feature.getProperties());
            }
        });

        //olMap.on('pointermove', function (e) {
        //    if (e.dragging) {
        //        return;
        //    };
        //
        //    let pixel = this.getEventPixel(e.originalEvent);
        //    let hit = this.hasFeatureAtPixel(pixel);
        //
        //    document.getElementById(this.getTarget()).style.cursor = hit ? 'pointer' : '';
        //});
    }

    function pointStyleFunction(feature, type, resolution) {
        let symbolStyles = {
            'default': new ol.style.Style({
                image: new ol.style.Circle({
                    radius: 5,
                    stroke: new ol.style.Stroke({ color: 'red', width: 1 }),
                    fill: new ol.style.Fill({ color: 'white' }),
                })
            }),
            'overpass': [
                new ol.style.Style({
                    image: new ol.style.Circle({
                        radius: 7,
                        stroke: new ol.style.Stroke({ color: 'red', width: 2 }),
                        fill: new ol.style.Fill({ color: 'white' }),
                    }),
                }),
                new ol.style.Style({
                    text: new ol.style.Text({
                        text: feature.get('intersection_number'),
                        fill: new ol.style.Fill({ color: 'white' }),
                        font: 'Bold ' + 14 + 'px Times New Roman',
                        offsetX: 15,
                        offsetY: -15,
                        stroke: new ol.style.Stroke({ color: 'red', width: 3 }),
                    })
                }),
                new ol.style.Style({
                    text: new ol.style.Text({
                        text: feature.get('railroad_station'),
                        fill: new ol.style.Fill({ color: 'white' }),
                        font: 'Normal ' + 14 + 'px Times New Roman',
                        offsetX: 15,
                        offsetY: 20,
                        stroke: new ol.style.Stroke({ color: 'black', width: 3 }),
                    })
                })
            ],
            'underpass': [
                new ol.style.Style({
                    image: new ol.style.Circle({
                        radius: 7,
                        stroke: new ol.style.Stroke({ color: 'blue', width: 2 }),
                        fill: new ol.style.Fill({ color: 'white' }),
                    }),
                }),
                new ol.style.Style({
                    text: new ol.style.Text({
                        text: feature.get('intersection_number'),
                        fill: new ol.style.Fill({ color: 'white' }),
                        font: 'Bold ' + 14 + 'px Times New Roman',
                        offsetX: 15,
                        offsetY: -15,
                        stroke: new ol.style.Stroke({ color: 'blue', width: 3 }),
                    })
                }),
                new ol.style.Style({
                    text: new ol.style.Text({
                        text: feature.get('railroad_station'),
                        fill: new ol.style.Fill({ color: 'white' }),
                        font: 'Normal ' + 14 + 'px Times New Roman',
                        offsetX: 15,
                        offsetY: 20,
                        stroke: new ol.style.Stroke({ color: 'black', width: 3 }),
                    })
                })
            ],
            'r-prop-text-private': new ol.style.Style({
                text: new ol.style.Text({
                    text: resolution < 0.5 ? feature.get('text') : '',
                    fill: new ol.style.Fill({ color: 'blue' }),
                    font: 'Normal ' + 14 + 'px Times New Roman'
                })
            }),
            'r-prop-text-public': new ol.style.Style({
                text: new ol.style.Text({
                    text: resolution < 0.5 ? feature.get('text') : '',
                    fill: new ol.style.Fill({ color: 'red' }),
                    font: 'Normal ' + 14 + 'px Times New Roman'
                })
            }),
            'r-zone-text': new ol.style.Style({
                image: new ol.style.Circle({
                    radius: 20,
                    stroke: new ol.style.Stroke({ color: 'red', width: 1 }),
                }),
                text: new ol.style.Text({
                    text: feature.get('text'),
                    fill: new ol.style.Fill({ color: 'red' }),
                    font: 'Normal ' + 20 + 'px Times New Roman'
                })
            }),
            'r-strt-node-text': new ol.style.Style({
                text: new ol.style.Text({
                    text: resolution < 0.5 ? feature.get('text') : '',
                    fill: new ol.style.Fill({ color: 'red' }),
                    font: 'Normal ' + 12 + 'px Times New Roman'
                })
            }),
            'r-strt-node': new ol.style.Style({
                image: new ol.style.Circle({
                    radius: 3,
                    stroke: new ol.style.Stroke({ color: 'red', width: 1 }),
                })
            })
        };

        return symbolStyles[type];
    }

    function addLayer(layer) {
        if (mapLayers.find(item => item.get('name') === layer.get('name')) !== undefined) {
            return;
        }

        let styles = {
            'LineString': {
                'default': new ol.style.Style({
                    stroke: new ol.style.Stroke({
                        color: 'green',
                        width: 1
                    })
                }),
                'axis': new ol.style.Style({
                    stroke: new ol.style.Stroke({
                        color: 'red',
                        width: 2
                    })
                }),
                'r-strt-axis': new ol.style.Style({
                    stroke: new ol.style.Stroke({
                        color: 'red',
                        width: 1,
                        lineDash: [30, 10, 0, 10]
                    })
                }),
                'r-prop-line-private': new ol.style.Style({
                    stroke: new ol.style.Stroke({
                        color: 'blue',
                        width: 1.5
                    })
                }),
                'r-prop-line-public': new ol.style.Style({
                    stroke: new ol.style.Stroke({
                        color: 'red',
                        width: 1.5
                    })
                }),
                'r-prop-strt-line': new ol.style.Style({
                    stroke: new ol.style.Stroke({
                        color: 'red',
                        width: 3
                    })
                }),
                'r-prop-strt-line-bldg': new ol.style.Style({
                    stroke: new ol.style.Stroke({
                        color: 'red',
                        width: 3,
                        lineDash: [30, 10]
                    })
                }),
                'r-curb-line': new ol.style.Style({
                    stroke: new ol.style.Stroke({
                        color: 'blue',
                        width: 1
                    })
                }),
                'r-curb-line-bldg': new ol.style.Style({
                    stroke: new ol.style.Stroke({
                        color: 'blue',
                        width: 1,
                        lineDash: [30, 10]
                    })
                })
            },
            'MultiLineString': new ol.style.Style({
                stroke: new ol.style.Stroke({
                    color: 'green',
                    width: 1
                })
            }),
            'MultiPoint': new ol.style.Style({
                stroke: new ol.style.Stroke({
                    color: 'green',
                    width: 1
                })
            }),
            'MultiPolygon': new ol.style.Style({
                stroke: new ol.style.Stroke({
                    color: 'yellow',
                    width: 1
                }),
                fill: new ol.style.Fill({
                    color: 'rgba(255, 255, 0, 0.1)'
                })
            }),
            'Polygon': {
                'default': new ol.style.Style({
                    stroke: new ol.style.Stroke({
                        color: 'blue',
                        lineDash: [4],
                        width: 3
                    }),
                    fill: new ol.style.Fill({
                        color: 'rgba(0, 0, 255, 0.1)'
                    })
                }),
                'building': new ol.style.Style({
                    stroke: new ol.style.Stroke({
                        color: 'red',
                        lineDash: [4],
                        width: 3
                    }),
                    fill: new ol.style.Fill({
                        color: 'rgba(0, 0, 255, 0.1)'
                    })
                })
            },
            'GeometryCollection': new ol.style.Style({
                stroke: new ol.style.Stroke({
                    color: 'magenta',
                    width: 2
                }),
                fill: new ol.style.Fill({
                    color: 'magenta'
                }),
                image: new ol.style.Circle({
                    radius: 10,
                    fill: null,
                    stroke: new ol.style.Stroke({
                        color: 'magenta'
                    })
                })
            }),
            'Circle': new ol.style.Style({
                stroke: new ol.style.Stroke({
                    color: 'red',
                    width: 2
                }),
                fill: new ol.style.Fill({
                    color: 'rgba(255,0,0,0.2)'
                })
            })
        };

        let styleFunction = function (feature, resolution) {
            let featureGeometryType = feature.getGeometry().getType();
            let featureType = feature.get('type') !== undefined ? feature.get('type') : 'default';

            if (featureGeometryType === 'Point') {
                return pointStyleFunction(feature, featureType, resolution);
            } else {
                return styles[featureGeometryType][featureType];
            }
        };

        layer.setStyle(styleFunction);

        olMap.addLayer(layer);

        mapLayers.push(layer);

        _updateMaxExtent(layer.getSource().getExtent())
    }

    function zoomToMaxExtent() {
        olMap.getView().fit([mapExtent.minX, mapExtent.minY, mapExtent.maxX, mapExtent.maxY]);
    }

    function getLayers() {
        return olMap.getLayers();
    }

    function setBaseMapLayerStyle(style) {
        for (let key in baseMapLayers) {
            baseMapLayers[key].setVisible(baseMapLayers[key].get('name') === style);
        }
    }

    function _addLayers(layers) {
        layers.forEach(function (layer) {
            olMap.addLayer(layer);
        });
    }

    function _updateMaxExtent(extent) {
        if (mapExtent.minX !== null) {
            if (extent[0] < mapExtent.minX) {
                mapExtent.minX = extent[0];
            }
        } else {
            mapExtent.minX = extent[0];
        }

        if (mapExtent.minY !== null) {
            if (extent[1] < mapExtent.minY) {
                mapExtent.minY = extent[1];
            }
        } else {
            mapExtent.minY = extent[1];
        }

        if (mapExtent.maxX !== null) {
            if (extent[2] > mapExtent.maxX) {
                mapExtent.maxX = extent[2];
            }
        } else {
            mapExtent.maxX = extent[2];
        }

        if (mapExtent.maxY !== null) {
            if (extent[3] > mapExtent.maxY) {
                mapExtent.maxY = extent[3];
            }
        } else {
            mapExtent.maxY = extent[3];
        }
    }

    return {
        init: init,
        addLayer: addLayer,
        getLayers: getLayers,
        zoomToMaxExtent: zoomToMaxExtent,
        setBaseMapLayerStyle: setBaseMapLayerStyle
    };
}());