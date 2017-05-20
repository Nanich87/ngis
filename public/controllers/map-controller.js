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
                firebase.auth().onAuthStateChanged(function (user) {
                    if (user) {
                        projectService.getProjectData(id).then(function (snapshot) {
                            snapshot.forEach(function (data) {
                                let vectorSource = new ol.source.Vector({
                                    features: (new ol.format.GeoJSON()).readFeatures(JSON.parse(data.val().content))
                                });

                                let vectorLayer = new ol.layer.Vector({
                                    source: vectorSource,
                                    name: data.val().title
                                });

                                map.addLayer(vectorLayer);
                            });

                            map.zoomToMaxExtent();

                            mapContainer.fadeTo('slow', 1);
                        });
                    } else {
                        window.location.href = '#/auth';
                    }
                });
            });
        });
    }

    return {
        init: initPage,
        view: viewProject
    };
}());