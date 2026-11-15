'use strict';

let projectController = (function () {

    let pageID = 'projects';
    let pageTitle = 'Обекти';

    let isAdmin = false;

    function initPage(container) {
        document.title = pageTitle;

        pageHelper.setActivePage(pageID);

        authService.requireUser().then(function (user) {
            templates.get('projects').then(function (template) {
                isAdmin = user.isAdmin;

                if (!user.canRead && !user.isAdmin) {
                    $(container).html(template({ isAdmin: false, notAuthorized: true }));

                    document.title = 'Access Denided';

                    return;
                }

                $(container).html(template({ isAdmin: isAdmin, notAuthorized: false }));

                projectService.getProjects().then(function (projects) {
                    projects.forEach(function (project) {
                        addProjectToList('#projects', project.id, project.name);
                    });

                    $('.loading-indicator').removeClass('visible').addClass('hidden');

                    $('#projects').removeClass('hidden');
                }, function (error) {
                    toastr.error('Не може да намери обекти!');
                });

                $('#ux-btn-create-project').click(createProject);
            });
        });
    }

    function addProjectToList(listSelector, projectID, projectName) {
        let actionLink1 = $(document.createElement('a')).text('Карта').attr('class', 'btn btn-success btn-xs').attr('href', '/#/map/' + projectID);
        let actionLink2 = $(document.createElement('a')).text('Изтриване').attr('class', 'btn btn-danger btn-xs').attr('href', '/#/project/delete/' + projectID);

        let actionLinkGroup = $(document.createElement('div')).attr('class', 'btn-group btn-group-justified').append(actionLink1);

        if (isAdmin) {
            actionLinkGroup.append(actionLink2);
        }

        let title = $(document.createElement('a')).text(projectName).attr('class', 'btn btn-link').attr('href', '/#/project/view/' + projectName.toLowerCase() + '/' + projectID);

        let tableData1 = $(document.createElement('td')).append(title);
        let tableData2 = $(document.createElement('td')).css('vertical-align', 'middle').append(actionLinkGroup);
        let tableRow = $(document.createElement('tr')).append(tableData1).append(tableData2);

        $(listSelector).append(tableRow);
    }

    function viewProject(context, container) {
        let id = context.params.id || null;

        authService.requireUser().then(function () {
            templates.get('view-project').then(function (template) {
                projectService.getProjectById(id).then(function (project) {
                    let data = {
                        name: project.name.toLowerCase(),
                        year: project.year,
                        data: project.data,
                        id: id,
                        displayName: project.name
                    };

                    $(container).html(template(data));

                    document.title = project.name;

                    pageHelper.setActivePage(pageID);
                }, function (error) {
                    toastr.error(error.message);
                });
            });
        });
    }

    function editProject(context, container) {
        let pid = context.params.pid || null;
        let fid = context.params.fid || null;
        let name = context.params.name || null;

        if (pid === null || fid === null || name === null) {
            window.location.href = '#/';

            return;
        }

        authService.requireUser().then(function () {
            templates.get('edit-project').then(function (template) {
                projectService.getProjectDataByFileId(pid, fid).then(function (layer) {
                    let data = {
                        project: {
                            id: pid,
                            name: name.toLowerCase(),
                            displayName: name
                        },
                        file: {
                            title: layer.title,
                            content: layer.content
                        }
                    };

                    $(container).html(template(data));

                    document.title = data.file.title;

                    pageHelper.setActivePage(pageID);

                    $('#ux-btn-save').click(function () {

                    });

                    $('#ux-btn-delete').click(function () {
                        projectService.removeProjectDataByFileId(pid, fid).then(function () {
                            toastr.success('Файлът беше изтрит успешно!');

                            window.location.href = '/#/project/view/' + name.toLowerCase() + '/' + pid;
                        }, function (error) {
                            toastr.error('Възникнала е грешка при изтриването на файла!');
                        });
                    });
                }, function (error) {
                    toastr.error(error.message);
                });
            });
        });
    }

    function addProjectData(context, container) {
        let id = context.params.id || null;
        let name = context.params.name || null;

        if (id === null || name === null) {
            window.location.href = '#/';

            return;
        }

        authService.requireUser().then(function () {
            templates.get('add-project-data').then(function (template) {
                let data = {
                    name: name.toLowerCase(),
                    id: id,
                    displayName: name
                };

                $(container).html(template(data));

                document.title = name;

                $('#ux-btn-upload-file').click(function () {
                    let file = $('#file')[0].files[0];

                    if (!file) {
                        toastr.error('Не е избран файл!');

                        return;
                    }

                    saveFileContent(id, file);
                });
            });
        });
    }

    function saveFileContent(projectID, file) {
        let reader = new FileReader();
        reader.readAsText(file, 'UTF-8');
        reader.onload = function (e) {
            projectService.addProjectData(projectID, file.name, e.target.result).then(function () {
                toastr.success('Данните бяха добавени успешно!');

                window.location.href = '#/projects';
            }, function (error) {
                toastr.error(error.message || 'Възникнала е грешка при добавянето на данните!');
            });
        };
    }

    function createProject() {
        let name = $('#name').val().trim();
        let year = $('#year').val().trim();

        let errors = false;

        if (name.length < 3) {
            errors = true;

            toastr.error('Името на обекта не може да съдържа по малко от 3 символа!');
        }

        if (name.length > 20) {
            errors = true;

            toastr.error('Името на обекта не може да да съдържа повече от 20 символа!');
        }

        let namePattern = /^[a-z0-9-]{3,20}$/i;

        if (!namePattern.test(name)) {
            errors = true;

            toastr.error('Името на обекта съдържа забранени символи!');
        }

        if (year.length !== 4) {
            errors = true;

            toastr.error('Годината трябва да съдържа 4 символа!');
        }

        let yearPattern = /^(19|20)[0-9]{2}$/;

        if (!yearPattern.test(year)) {
            errors = true;

            toastr.error('Невалидна година!');
        }

        if (errors) {
            return;
        }

        projectService.createProject(name, year).then(function (project) {
            addProjectToList('#projects', project.id, name);

            toastr.success('Обектът беше създаден успешно!');
        }, function (error) {
            toastr.error(error.message || 'Възникнала е грешка при създаването на обекта!');
        });
    }

    function deleteProject(context) {
        let projectID = context.params.id || null;

        projectService.deleteProject(projectID).then(function () {
            toastr.success('Обектът беше изтрит успешно от базата данни!');

            window.location.href = '/#/projects';
        }, function (error) {
            toastr.error('Възникнала е грешка при изтриването на обекта от базата данни!');
        });
    }

    return {
        init: initPage,
        view: viewProject,
        edit: editProject,
        delete: deleteProject,
        add: addProjectData
    };
}());
