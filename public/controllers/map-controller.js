'use strict';

let mapController = (function () {

    let pageID = 'map';
    let pageTitle = 'Карта';
    let pageTemplate = './views/map.html';
    let baseMapStorageKey = 'ngis.baseMap';

    // Incremented on every render so late async callbacks from a previous visit are ignored.
    let renderToken = 0;

    // project id -> { loaded, loading, layers: [{ id, title }] }
    let projectState = {};

    function initPage(container) {
        render(container, null);
    }

    function viewProject(context, container) {
        render(container, context.params.id || null);
    }

    function render(container, preselectedProjectId) {
        let token = ++renderToken;

        projectState = {};

        $(container).load(pageTemplate, function () {
            document.title = pageTitle;

            pageHelper.setActivePage(pageID);

            let baseMap = loadBaseMap();

            map.init({ target: 'map', baseMap: baseMap });
            map.onChange(renderLegend);

            renderBaseMapOptions(baseMap);
            renderLegend();

            $('#project-filter').on('input', function () {
                filterProjects(this.value);
            });

            authService.requireUser().then(function (user) {
                if (token !== renderToken) {
                    return;
                }

                if (!user.canRead && !user.isAdmin) {
                    $('#project-tree').html('<div class="alert alert-warning small mb-0">Нямате права за четене на обекти. Обърнете се към администратор.</div>');

                    return;
                }

                return projectService.getProjects().then(function (projects) {
                    if (token !== renderToken) {
                        return;
                    }

                    renderProjectTree(projects, token);

                    if (preselectedProjectId) {
                        let checkbox = $('#prj-' + cssId(preselectedProjectId));

                        if (checkbox.length) {
                            checkbox.prop('checked', true);
                            toggleProject(preselectedProjectId, true, true, token);
                        } else {
                            toastr.error('Няма такъв обект!');
                        }
                    }
                });
            }).catch(function (error) {
                $('#project-tree').html($('<div class="alert alert-danger small mb-0"></div>').text(error.message));
            });
        });
    }

    // ------------------------------------------------------------------ base map

    function loadBaseMap() {
        try {
            let saved = window.localStorage.getItem(baseMapStorageKey);

            if (map.BASE_MAPS.some(b => b.id === saved)) {
                return saved;
            }
        } catch (e) { }

        return 'osm';
    }

    function renderBaseMapOptions(selected) {
        let group = $('#base-map-options');

        map.BASE_MAPS.forEach(function (baseMap) {
            let id = 'base-map-' + baseMap.id;

            let input = $('<input type="radio" class="btn-check" name="base-map" autocomplete="off" />')
                .attr('id', id).val(baseMap.id).prop('checked', baseMap.id === selected);
            let label = $('<label class="btn btn-neutral"></label>').attr('for', id).attr('title', baseMap.title).text(baseMap.label);

            group.append(input, label);
        });

        group.on('change', 'input', function () {
            map.setBaseMap(this.value);

            try {
                window.localStorage.setItem(baseMapStorageKey, this.value);
            } catch (e) { }
        });
    }

    // ------------------------------------------------------------------ project tree

    function cssId(id) {
        return String(id).replace(/[^a-zA-Z0-9_-]/g, '_');
    }

    function renderProjectTree(projects, token) {
        let tree = $('#project-tree').empty();

        if (projects.length === 0) {
            tree.html('<div class="text-body-secondary small py-2">Няма създадени обекти.</div>');

            return;
        }

        projects.forEach(function (project) {
            let domId = cssId(project.id);

            let checkbox = $('<input class="form-check-input project-toggle" type="checkbox" />').attr('id', 'prj-' + domId);
            let label = $('<label class="form-check-label project-name text-truncate"></label>').attr('for', 'prj-' + domId).text(project.name);
            let year = $('<span class="badge text-bg-secondary"></span>').text(project.year);
            let zoom = $('<button type="button" class="btn btn-sm btn-link project-zoom" title="Приближи до обекта" aria-label="Приближи до обекта" disabled><span class="fa">&#xf05b;</span></button>');

            let row = $('<div class="project-row"></div>').append(checkbox, label, year, zoom);
            let layerList = $('<ul class="layer-list list-unstyled hidden"></ul>');

            let item = $('<div class="project-item"></div>')
                .attr('data-id', project.id)
                .attr('data-name', project.name.toLowerCase())
                .append(row, layerList);

            checkbox.on('change', function () {
                toggleProject(project.id, this.checked, true, token);
            });

            zoom.on('click', function () {
                let ids = zoomableLayerIds(projectState[project.id]);

                if (!map.zoomToLayers(ids)) {
                    toastr.info('Обектът няма данни за показване.');
                }
            });

            tree.append(item);
        });
    }

    function filterProjects(query) {
        query = query.trim().toLowerCase();

        $('#project-tree .project-item').each(function () {
            $(this).toggleClass('hidden', query !== '' && this.getAttribute('data-name').indexOf(query) === -1);
        });
    }

    function projectItem(projectId) {
        return $('#project-tree .project-item').filter(function () {
            return this.getAttribute('data-id') === projectId;
        });
    }

    function toggleProject(projectId, visible, zoomAfterLoad, token) {
        let state = projectState[projectId] || (projectState[projectId] = { loaded: false, loading: false, layers: [] });
        let item = projectItem(projectId);

        if (state.loaded) {
            state.layers.forEach(layer => map.setLayerVisible(layer.id, visible));
            item.find('.layer-toggle').prop('checked', visible);
            item.find('.project-toggle').prop('indeterminate', false);

            return;
        }

        if (!visible || state.loading) {
            return;
        }

        state.loading = true;

        let spinner = $('<li class="text-body-secondary small"><span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>Зареждане…</li>');
        item.find('.layer-list').removeClass('hidden').append(spinner);

        projectService.getProjectData(projectId).then(function (layers) {
            if (token !== renderToken) {
                return;
            }

            state.loading = false;
            state.loaded = true;
            spinner.remove();

            layers.forEach(function (layer) {
                try {
                    let geojson = JSON.parse(layer.content);
                    let crs = map.unsupportedCrs(geojson);

                    map.addLayer(layer.id, layer.title, geojson);
                    state.layers.push({ id: layer.id, title: layer.title, unsupportedCrs: crs });

                    if (crs) {
                        toastr.warning('Файлът „' + layer.title + '“ е в координатна система ' + crs + ', която не се поддържа. Може да се покаже на грешно място.');
                    }
                } catch (e) {
                    toastr.warning('Файлът „' + layer.title + '“ не може да бъде показан.');
                }
            });

            renderLayerList(projectId, item);

            // The user may have unchecked the project while it was loading.
            let visibleNow = item.find('.project-toggle').prop('checked');
            state.layers.forEach(layer => map.setLayerVisible(layer.id, visibleNow));
            item.find('.layer-toggle').prop('checked', visibleNow);

            if (visibleNow && zoomAfterLoad) {
                map.zoomToLayers(zoomableLayerIds(state));
            }
        }, function (error) {
            state.loading = false;
            spinner.remove();
            item.find('.project-toggle').prop('checked', false);

            toastr.error(error.message);
        });
    }

    // Layers in an unsupported CRS would stretch the extent to the wrong place.
    function zoomableLayerIds(state) {
        return (state ? state.layers : []).filter(l => !l.unsupportedCrs).map(l => l.id);
    }

    function renderLayerList(projectId, item) {
        let state = projectState[projectId];
        let list = item.find('.layer-list').empty().removeClass('hidden');

        item.find('.project-zoom').prop('disabled', state.layers.length === 0);

        if (state.layers.length === 0) {
            list.append('<li class="text-body-secondary small">Няма качени файлове.</li>');

            return;
        }

        state.layers.forEach(function (layer) {
            let domId = 'lyr-' + cssId(layer.id);
            let count = map.getFeatureCount(layer.id);

            let checkbox = $('<input class="form-check-input layer-toggle" type="checkbox" checked />').attr('id', domId);
            let label = $('<label class="form-check-label text-truncate"></label>').attr('for', domId).attr('title', layer.title).text(layer.title);
            let meta = $('<span class="layer-count"></span>').text(count);
            let zoom = $('<button type="button" class="btn btn-sm btn-link" title="Приближи до слоя" aria-label="Приближи до слоя"><span class="fa">&#xf05b;</span></button>');

            checkbox.on('change', function () {
                map.setLayerVisible(layer.id, this.checked);
                syncProjectCheckbox(item);
            });

            zoom.on('click', function () {
                if (!map.zoomToLayers([layer.id])) {
                    toastr.info('Слоят няма обекти.');
                }
            });

            let row = $('<li class="layer-row"></li>').append(checkbox, label);

            if (layer.unsupportedCrs) {
                row.append($('<span class="fa text-warning layer-warning" role="img">&#xf071;</span>')
                    .attr('title', 'Непозната координатна система: ' + layer.unsupportedCrs)
                    .attr('aria-label', 'Непозната координатна система: ' + layer.unsupportedCrs));
            }

            list.append(row.append(meta, zoom));
        });
    }

    function syncProjectCheckbox(item) {
        let toggles = item.find('.layer-toggle');
        let checked = toggles.filter(':checked').length;

        item.find('.project-toggle')
            .prop('checked', checked > 0)
            .prop('indeterminate', checked > 0 && checked < toggles.length);
    }

    // ------------------------------------------------------------------ legend

    function renderLegend() {
        let legend = $('#map-legend').empty();
        let entries = map.getLegend();

        if (entries.length === 0) {
            legend.append('<li class="text-body-secondary small">Включете обект, за да видите легендата.</li>');

            return;
        }

        entries.forEach(function (entry) {
            legend.append($('<li class="legend-row"></li>').append(
                $('<span class="legend-swatch"></span>').html(entry.swatch),
                $('<span class="legend-label"></span>').text(entry.label),
                $('<span class="layer-count"></span>').text(entry.count)
            ));
        });
    }

    return {
        init: initPage,
        view: viewProject
    };
}());
