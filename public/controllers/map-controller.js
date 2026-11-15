'use strict';

let mapController = (function () {

    let pageID = 'map';
    let pageTitle = 'Карта';
    let pageTemplate = './views/map.html';

    function initPage(container) {
        $(container).load(pageTemplate, function () {
            document.title = pageTitle;

            pageHelper.setActivePage(pageID);

            map.init();

            $('#base-map-layer').change(function () {
                map.setBaseMapLayerStyle(this.value);
            })
        });
    }

    function viewProject(context, container) {
        let id = context.params.id || null;

        $(container).load(pageTemplate, function () {
            document.title = pageTitle;

            pageHelper.setActivePage(pageID);

            map.init();

            $('#base-map-layer').change(function () {
                map.setBaseMapLayerStyle(this.value);
            })

            let mapContainer = $('#map');

            mapContainer.fadeTo('slow', 0.5, function () {
                authService.requireUser().then(function () {
                    return projectService.getProjectData(id);
                }).then(function (layers) {
                    layers.forEach(function (layer) {
                        let vectorSource = new ol.source.Vector({
                            features: (new ol.format.GeoJSON()).readFeatures(JSON.parse(layer.content))
                        });

                        let vectorLayer = new ol.layer.Vector({
                            source: vectorSource,
                            name: layer.title
                        });

                        map.addLayer(vectorLayer);
                    });

                    if (layers.length > 0) {
                        map.zoomToMaxExtent();
                    }

                    mapContainer.fadeTo('slow', 1);
                }, function (error) {
                    mapContainer.fadeTo('slow', 1);

                    toastr.error(error.message);
                });
            });
        });
    }

    return {
        init: initPage,
        view: viewProject
    };
}());