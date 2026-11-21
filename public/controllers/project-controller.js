'use strict';

let projectController = (function () {

    let pageID = 'projects';

    const NAME_PATTERN = /^[a-z0-9-]{3,20}$/i;
    const YEAR_PATTERN = /^(19|20)[0-9]{2}$/;
    const MAX_ATTRIBUTE_ROWS = 500;

    function projectUrl(project) {
        return '/#/project/view/' + pageHelper.slug(project.name) + '/' + project.id;
    }

    function canWrite(user) {
        return user.canWrite || user.isAdmin;
    }

    // ------------------------------------------------------------------ project list

    function initPage(container) {
        document.title = i18n.t('Обекти') + ' – nGIS';

        pageHelper.setActivePage(pageID);

        authService.requireUser().then(function (user) {
            templates.get('projects').then(function (template) {
                if (!user.canRead && !user.isAdmin) {
                    $(container).html(template({ notAuthorized: true }));

                    return;
                }

                $(container).html(template({ isAdmin: user.isAdmin }));

                $('#project-search').on('input', function () {
                    filterProjects(this.value);
                });

                if (user.isAdmin) {
                    initCreateProjectModal();
                    initRenameProjectModal();
                }

                projectService.getProjects().then(function (projects) {
                    renderProjects(projects, user);
                }, function (error) {
                    $('.loading-indicator').addClass('hidden');
                    toastr.error(error.message);
                });
            });
        });
    }

    function renderProjects(projects, user) {
        let tbody = $('#projects tbody').empty();

        // Newest year first (years are always 4 digits); within a year, the most recently created first.
        projects = projects.slice().sort((a, b) =>
            String(b.year).localeCompare(String(a.year)) || String(b.created_at).localeCompare(String(a.created_at)));

        projects.forEach(project => tbody.append(projectRow(project, user)));

        $('.loading-indicator').addClass('hidden');
        $('#projects').toggleClass('hidden', projects.length === 0);
        $('#projects-empty').toggleClass('hidden', projects.length !== 0);

        updateProjectsSummary();
    }

    function projectRow(project, user) {
        let name = $('<a class="fw-medium"></a>').attr('href', projectUrl(project)).text(project.name);
        let files = project.layer_count
            ? pageHelper.formatCount(project.layer_count, 'файл', 'файла')
            : $('<span class="text-body-secondary">—</span>');

        let actions = $('<div class="d-inline-flex gap-2"></div>').append(
            $('<a class="btn btn-sm btn-neutral text-nowrap"><span class="fa">&#xf279;</span> </a>')
                .append(document.createTextNode(i18n.t('Карта'))).attr('href', '/#/map/' + project.id)
        );

        if (user.isAdmin) {
            let rename = $('<button type="button" class="btn btn-sm btn-neutral"><span class="fa">&#xf040;</span></button>')
                .attr('aria-label', i18n.t('Преименуване на {name}', { name: project.name }))
                .attr('title', i18n.t('Преименуване'));

            rename.on('click', () => openRenameModal(project, row, user));

            actions.append(rename);

            let remove = $('<button type="button" class="btn btn-sm btn-outline-danger"><span class="fa">&#xf1f8;</span></button>')
                .attr('aria-label', i18n.t('Изтриване на {name}', { name: project.name }))
                .attr('title', i18n.t('Изтриване'));

            remove.on('click', function () {
                deleteProject(project).then(function (deleted) {
                    if (deleted) {
                        row.remove();

                        let empty = $('#projects tbody tr').length === 0;
                        $('#projects').toggleClass('hidden', empty);
                        $('#projects-empty').toggleClass('hidden', !empty);

                        updateProjectsSummary();
                    }
                });
            });

            actions.append(remove);
        }

        let row = $('<tr></tr>')
            .attr('data-search', (project.name + ' ' + project.year).toLowerCase())
            .append($('<td></td>').append(name))
            .append($('<td></td>').text(project.year))
            .append($('<td class="text-nowrap"></td>').append(files))
            .append($('<td class="text-end"></td>').append(actions));

        return row;
    }

    function updateProjectsSummary() {
        let count = $('#projects tbody tr').length;

        $('#projects-summary').text(count ? pageHelper.formatCount(count, 'обект', 'обекта') : ' ');
    }

    function filterProjects(query) {
        query = query.trim().toLowerCase();

        let rows = $('#projects tbody tr');
        let visible = 0;

        rows.each(function () {
            let match = query === '' || this.getAttribute('data-search').indexOf(query) !== -1;

            $(this).toggleClass('hidden', !match);
            visible += match ? 1 : 0;
        });

        $('#projects-no-match').toggleClass('hidden', rows.length === 0 || visible > 0);
    }

    function initCreateProjectModal() {
        let modal = $('#create-project-modal');

        modal.on('show.bs.modal', function () {
            $('#create-project-form')[0].reset();
            $('#create-project-form .is-invalid').removeClass('is-invalid');
            $('#year').val(new Date().getFullYear());
        });

        modal.on('shown.bs.modal', function () {
            $('#name').trigger('focus');
        });

        // Returning false keeps the browser from submitting (and reloading) the page.
        $('#create-project-form').on('submit', function () {
            createProject();

            return false;
        });
    }

    function fieldError(selector, message) {
        $(selector).toggleClass('is-invalid', !!message);
        $(selector + '-error').text(message || '');

        return !!message;
    }

    function projectNameError(name) {
        return name.length < 3 ? i18n.t('Името трябва да е поне 3 символа.')
            : name.length > 20 ? i18n.t('Името може да е най-много 20 символа.')
                : !NAME_PATTERN.test(name) ? i18n.t('Разрешени са само латински букви, цифри и тире.')
                    : null;
    }

    // The modal is shared by all rows; renaming is the current target.
    let renaming = null;

    function initRenameProjectModal() {
        let modal = $('#rename-project-modal');

        modal.on('shown.bs.modal', function () {
            $('#rename-name').trigger('focus').trigger('select');
        });

        modal.on('hidden.bs.modal', function () {
            renaming = null;
        });

        $('#rename-project-form').on('submit', function () {
            renameProject();

            return false;
        });
    }

    function openRenameModal(project, row, user) {
        renaming = { project: project, row: row, user: user };

        fieldError('#rename-name', null);
        $('#rename-name').val(project.name);

        bootstrap.Modal.getOrCreateInstance(document.getElementById('rename-project-modal')).show();
    }

    function renameProject() {
        if (renaming === null) {
            return;
        }

        let target = renaming;
        let name = $('#rename-name').val().trim();

        if (fieldError('#rename-name', projectNameError(name))) {
            $('#rename-name').trigger('focus');

            return;
        }

        if (name === target.project.name) {
            bootstrap.Modal.getInstance(document.getElementById('rename-project-modal')).hide();

            return;
        }

        let button = $('#ux-btn-rename-project').prop('disabled', true);

        projectService.renameProject(target.project.id, name).then(function () {
            toastr.success(i18n.t('Обектът беше преименуван.'));

            let project = Object.assign({}, target.project, { name: name });
            let row = projectRow(project, target.user);

            target.row.replaceWith(row);
            filterProjects($('#project-search').val() || '');

            bootstrap.Modal.getInstance(document.getElementById('rename-project-modal')).hide();
        }, function (error) {
            toastr.error(error.message);
        }).then(function () {
            button.prop('disabled', false);
        });
    }

    function createProject() {
        let name = $('#name').val().trim();
        let year = $('#year').val().trim();

        let nameError = projectNameError(name);
        let yearError = !YEAR_PATTERN.test(year) ? i18n.t('Въведете година между 1900 и 2099.') : null;

        let invalid = fieldError('#name', nameError);
        invalid = fieldError('#year', yearError) || invalid;

        if (invalid) {
            $('#create-project-form .is-invalid').first().trigger('focus');

            return;
        }

        let button = $('#ux-btn-create-project').prop('disabled', true);

        projectService.createProject(name, year).then(function (project) {
            toastr.success(i18n.t('Обектът беше създаден.'));

            bootstrap.Modal.getInstance(document.getElementById('create-project-modal')).hide();

            // Next step is usually uploading files.
            window.location.href = projectUrl(project);
        }, function (error) {
            toastr.error(error.message);
        }).then(function () {
            button.prop('disabled', false);
        });
    }

    function deleteProject(project) {
        return pageHelper.confirm({
            title: i18n.t('Изтриване на обект'),
            body: i18n.t('Обектът „{name}“ и всички негови файлове ще бъдат изтрити безвъзвратно.', { name: project.name }),
            confirmText: i18n.t('Изтриване'),
            danger: true
        }).then(function (confirmed) {
            if (!confirmed) {
                return false;
            }

            return projectService.deleteProject(project.id).then(function () {
                toastr.success(i18n.t('Обектът беше изтрит.'));

                return true;
            }, function (error) {
                toastr.error(error.message);

                return false;
            });
        });
    }

    // ------------------------------------------------------------------ project page

    // preservedStatus: upload result rows to show again after re-rendering.
    function viewProject(context, container, preservedStatus) {
        let id = context.params.id || null;

        authService.requireUser().then(function (user) {
            Promise.all([templates.get('view-project'), projectService.getProjectById(id)]).then(function (results) {
                let template = results[0];
                let project = results[1];

                let featureCount = project.layers.reduce((sum, layer) => sum + (layer.feature_count || 0), 0);

                $(container).html(template({
                    project: project,
                    layerCount: project.layers.length,
                    featureCount: featureCount,
                    isAdmin: user.isAdmin,
                    canWrite: canWrite(user)
                }));

                document.title = project.name + ' – nGIS';

                pageHelper.setActivePage(pageID);

                $('#ux-btn-delete-project').on('click', function () {
                    deleteProject(project).then(function (deleted) {
                        if (deleted) {
                            window.location.href = '/#/projects';
                        }
                    });
                });

                $('.ux-btn-delete-file').on('click', function () {
                    let layer = { id: $(this).attr('data-id'), title: $(this).attr('data-title') };

                    deleteFile(project, layer).then(function (deleted) {
                        if (deleted) {
                            viewProject(context, container);
                        }
                    });
                });

                initUpload(project, function (status) {
                    viewProject(context, container, status);
                });

                if (preservedStatus) {
                    $('#upload-status').append(preservedStatus);
                }
            }, function (error) {
                toastr.error(error.message);

                window.location.href = '/#/projects';
            });
        });
    }

    function initUpload(project, onDone) {
        let dropzone = $('#dropzone');

        if (dropzone.length === 0) {
            return;
        }

        $('#file').on('change', function () {
            uploadFiles(project, Array.from(this.files), onDone);
            this.value = '';
        });

        dropzone.on('dragenter dragover', function (e) {
            e.preventDefault();
            dropzone.addClass('is-dragover');
        });

        dropzone.on('dragleave dragend drop', function (e) {
            e.preventDefault();
            dropzone.removeClass('is-dragover');
        });

        dropzone.on('drop', function (e) {
            uploadFiles(project, Array.from(e.originalEvent.dataTransfer.files), onDone);
        });
    }

    function readFile(file) {
        return new Promise(function (resolve, reject) {
            let reader = new FileReader();

            reader.onload = () => resolve(reader.result);
            reader.onerror = () => reject(new Error(i18n.t('Файлът не може да бъде прочетен.')));
            reader.readAsText(file, 'UTF-8');
        });
    }

    function readFileBase64(file) {
        return new Promise(function (resolve, reject) {
            let reader = new FileReader();

            // "data:application/octet-stream;base64,AAAA" -> "AAAA"
            reader.onload = () => resolve(reader.result.slice(reader.result.indexOf(',') + 1));
            reader.onerror = () => reject(new Error(i18n.t('Файлът не може да бъде прочетен.')));
            reader.readAsDataURL(file);
        });
    }

    // CAD and GPX files are converted to GeoJSON on the server (CAD files are usually in MIK,
    // which browsers cannot decode; GPX files declare their encoding in the XML header).
    function uploadFile(project, file) {
        if (/\.cad$/i.test(file.name)) {
            return readFileBase64(file).then(data => projectService.addCadFile(project.id, file.name, data));
        }

        if (/\.gpx$/i.test(file.name)) {
            return readFileBase64(file).then(data => projectService.addGpxFile(project.id, file.name, data));
        }

        return readFile(file).then(content => projectService.addProjectData(project.id, file.name, content));
    }

    function uploadFiles(project, files, onDone) {
        if (files.length === 0) {
            return;
        }

        let status = $('#upload-status').empty();
        let uploaded = 0;
        let warned = false;

        // Upload one at a time to keep request sizes reasonable.
        files.reduce(function (previous, file) {
            let item = $('<li class="upload-item"></li>')
                .append('<span class="spinner-border spinner-border-sm" aria-hidden="true"></span>')
                .append($('<span class="text-break"></span>').text(file.name));

            status.append(item);

            return previous.then(function () {
                return uploadFile(project, file).then(function (result) {
                    uploaded++;
                    item.find('.spinner-border').replaceWith($('<span class="fa text-success">&#xf00c;</span>').attr('aria-label', i18n.t('Качен')));

                    if (result && Array.isArray(result.warnings) && result.warnings.length > 0) {
                        warned = true;
                        result.warnings.forEach(function (warning) {
                            item.append($('<div class="text-warning ms-4"></div>').text(warning));
                        });
                    }
                }, function (error) {
                    item.find('.spinner-border').replaceWith($('<span class="fa text-danger">&#xf00d;</span>').attr('aria-label', i18n.t('Грешка')));
                    item.append($('<span class="text-danger"></span>').text('– ' + error.message));
                });
            });
        }, Promise.resolve()).then(function () {
            if (uploaded > 0) {
                toastr.success(pageHelper.formatCount(uploaded, 'файл беше качен.', 'файла бяха качени.'));

                // Re-render the file list; keep the result rows only if something failed.
                onDone(uploaded === files.length && !warned ? null : status.children().detach());
            }
        });
    }

    function deleteFile(project, layer) {
        return pageHelper.confirm({
            title: i18n.t('Изтриване на файл'),
            body: i18n.t('Файлът „{file}“ ще бъде изтрит от обект „{project}“.', { file: layer.title, project: project.name }),
            confirmText: i18n.t('Изтриване'),
            danger: true
        }).then(function (confirmed) {
            if (!confirmed) {
                return false;
            }

            return projectService.removeProjectDataByFileId(project.id, layer.id).then(function () {
                toastr.success(i18n.t('Файлът беше изтрит.'));

                return true;
            }, function (error) {
                toastr.error(error.message);

                return false;
            });
        });
    }

    // ------------------------------------------------------------------ file page

    function editProject(context, container) {
        let pid = context.params.pid || null;
        let fid = context.params.fid || null;

        if (pid === null || fid === null) {
            window.location.href = '#/projects';

            return;
        }

        authService.requireUser().then(function (user) {
            Promise.all([
                templates.get('edit-project'),
                projectService.getProjectById(pid),
                projectService.getProjectDataByFileId(pid, fid)
            ]).then(function (results) {
                let template = results[0];
                let project = results[1];
                let file = results[2];

                let geojson = null;

                try {
                    geojson = JSON.parse(file.content);
                } catch (e) { }

                let stats = {
                    valid: geojson !== null && typeof geojson === 'object',
                    size: new Blob([file.content]).size,
                    featureCount: geojson && Array.isArray(geojson.features) ? geojson.features.length : (geojson && geojson.type === 'Feature' ? 1 : 0)
                };

                $(container).html(template({
                    project: project,
                    file: file,
                    stats: stats,
                    canWrite: canWrite(user)
                }));

                document.title = file.title + ' – nGIS';

                pageHelper.setActivePage(pageID);

                renderRawJson(file.content);

                if (stats.valid) {
                    let crs = map.unsupportedCrs(geojson);

                    $('#projection-info').text(crs
                        ? i18n.t('Непозната координатна система: {crs}', { crs: crs })
                        : map.projectionLabel(map.detectProjection(geojson)));

                    if (crs) {
                        $('#crs-warning').removeClass('hidden').find('.crs-name').text(crs);
                    }

                    try {
                        renderFilePreview(geojson);
                    } catch (e) {
                        $('#file-preview-map').html($('<div class="p-4 text-danger"></div>').text(i18n.t('Файлът не може да бъде показан на картата.')));
                    }
                }

                $('#ux-btn-download').on('click', function () {
                    download(file.title, file.content);
                });

                $('#ux-btn-delete').on('click', function () {
                    deleteFile(project, file).then(function (deleted) {
                        if (deleted) {
                            window.location.href = projectUrl(project);
                        }
                    });
                });
            }, function (error) {
                toastr.error(error.message);

                window.location.href = '/#/projects';
            });
        });
    }

    function renderRawJson(content) {
        let pretty = content;

        try {
            pretty = JSON.stringify(JSON.parse(content), null, 2);
        } catch (e) { }

        let limit = 200000;

        $('#raw-json').text(pretty.length > limit
            ? pretty.slice(0, limit) + '\n\n… (' + i18n.t('показани са първите {size}; изтеглете файла за пълното съдържание', { size: pageHelper.formatBytes(limit) }) + ')'
            : pretty);
    }

    function renderFilePreview(geojson) {
        let preview = map.createPreview('file-preview-map', geojson);

        // Legend / content summary; some types appear only when zoomed in.
        function renderLegend() {
            let legend = $('#file-legend').empty();
            let entries = preview.getLegend();

            if (entries.length === 0) {
                legend.append($('<li class="list-group-item text-body-secondary"></li>').text(i18n.t('Файлът няма геообекти.')));
            }

            entries.forEach(function (entry) {
                legend.append(pageHelper.legendRow(entry, 'list-group-item legend-row'));
            });
        }

        renderLegend();
        preview.onChange(renderLegend);

        renderAttributeTable(preview);
    }

    function renderAttributeTable(preview) {
        let features = preview.features;
        let keys = [];

        features.forEach(function (feature) {
            Object.keys(feature.getProperties()).forEach(function (key) {
                let value = feature.get(key);

                if (key !== feature.getGeometryName() && keys.indexOf(key) === -1 && (value === null || typeof value !== 'object')) {
                    keys.push(key);
                }
            });
        });

        // Most useful columns first.
        let preferred = ['name', 'type', 'intersection_number', 'railroad_station', 'text'];
        keys.sort((a, b) => {
            let ia = preferred.indexOf(a), ib = preferred.indexOf(b);

            return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib) || a.localeCompare(b);
        });

        let table = $('#attribute-table').empty();
        let head = $('<tr><th class="text-body-secondary">#</th></tr>').append($('<th></th>').text(i18n.t('Геометрия')));

        keys.forEach(key => head.append($('<th></th>').text(key)));
        table.append($('<thead></thead>').append(head));

        let tbody = $('<tbody></tbody>');

        features.slice(0, MAX_ATTRIBUTE_ROWS).forEach(function (feature, index) {
            let geometry = feature.getGeometry();
            let typeLabel = map.typeLabel(feature);
            let row = $('<tr class="attribute-row" tabindex="0"></tr>')
                .attr('title', i18n.t('Покажи на картата'))
                .append($('<td class="text-body-secondary"></td>').text(index + 1))
                .append($('<td class="text-nowrap"></td>').text((typeLabel || '') + (geometry ? ' (' + geometry.getType() + ')' : '')));

            let search = [];

            keys.forEach(function (key) {
                let value = feature.get(key);
                let text = value === null || value === undefined ? '' : String(value);

                search.push(text);
                row.append($('<td></td>').text(text));
            });

            row.attr('data-search', search.join(' ').toLowerCase());

            row.on('click keydown', function (e) {
                if (e.type === 'keydown' && e.key !== 'Enter') {
                    return;
                }

                $('#attribute-table .table-active').removeClass('table-active');
                row.addClass('table-active');

                preview.zoomToFeature(feature);

                document.getElementById('file-preview-map').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            });

            tbody.append(row);
        });

        table.append(tbody);

        let footer = pageHelper.formatCount(features.length, 'геообект', 'геообекта');

        if (features.length > MAX_ATTRIBUTE_ROWS) {
            footer += ' · ' + i18n.t('показани са първите {count}', { count: MAX_ATTRIBUTE_ROWS });
        }

        $('#attribute-footer').text(footer + ' · ' + i18n.t('кликнете ред, за да го покажете на картата'));

        $('#attribute-search').on('input', function () {
            let query = this.value.trim().toLowerCase();

            tbody.find('tr').each(function () {
                $(this).toggleClass('hidden', query !== '' && this.getAttribute('data-search').indexOf(query) === -1);
            });
        });
    }

    function download(filename, content) {
        // Converted CAD and GPX files are stored as GeoJSON.
        if (!/\.(geo)?json$/i.test(filename)) {
            filename = filename.replace(/\.(cad|gpx)$/i, '') + '.geojson';
        }

        let blob = new Blob([content], { type: 'application/geo+json' });
        let url = URL.createObjectURL(blob);
        let link = document.createElement('a');

        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();

        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    // ------------------------------------------------------------------ legacy route

    // The separate "add data" page was merged into the project page.
    function addProjectData(context) {
        window.location.replace('/#/project/view/' + (context.params.name || 'project') + '/' + context.params.id);
    }

    return {
        init: initPage,
        view: viewProject,
        edit: editProject,
        add: addProjectData
    };
}());
