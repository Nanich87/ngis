'use strict';

let projectController = (function () {

    let pageID = 'projects';
    let pageTitle = 'Обекти';
    let projectsTemplate = './views/projects.html';

    let isAdmin = false;

    function initPage(container) {
        document.title = pageTitle;

        pageHelper.setActivePage(pageID);

        firebase.auth().onAuthStateChanged(function (user) {
            if (user) {
                templates.get('projects').then(function (template) {
                    userService.isAdmin(user.uid).then(function (snapshot) {
                        if (snapshot.val() !== null) {
                            isAdmin = true;
                        } else {
                            isAdmin = false;
                        }

                        let data = {
                            isAdmin: isAdmin,
                            notAuthorized: false
                        };

                        $(container).html(template(data));

                        projectService.getProjects().then(function (snapshot) {
                            snapshot.forEach(function (project) {
                                addProjectToList('#projects', project.key, project.val().name);
                            });

                            $('.loading-indicator').removeClass('visible').addClass('hidden');

                            $('#projects').removeClass('hidden');
                        }, function (error) {
                            toastr.error('Не може да намери обекти!');
                        });

                        $('#ux-btn-create-project').click(createProject);
                    }, function (error) {
                        let data = {
                            isAdmin: isAdmin,
                            notAuthorized: true
                        };

                        $(container).html(template(data));

                        document.title = 'Access Denided';
                    });
                });
            } else {
                window.location.href = '#/auth';
            }
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

        firebase.auth().onAuthStateChanged(function (user) {
            if (user) {
                templates.get('view-project').then(function (template) {
                    projectService.getProjectById(id).then(function (snapshot) {
                        let data = {
                            name: snapshot.val().name.toLowerCase(),
                            year: snapshot.val().year,
                            data: snapshot.val().data,
                            id: id,
                            displayName: snapshot.val().name
                        };

                        $(container).html(template(data));

                        document.title = snapshot.val().name;

                        pageHelper.setActivePage(pageID);

                        $('#ux-btn-upload-file').click(function () {
                            let file = $('#file')[0].files[0];

                            saveFileContent(id, file);
                        });
                    });
                });
            } else {
                window.location.href = '#/auth';
            }
        });
    }

    function editProject(context, container) {
        let pid = context.params.pid || null;
        let fid = context.params.fid || null;
        let name = context.params.name || null;

        if (pid === null || fid === null || name === null) {
            window.location.href = '#/';
        }

        firebase.auth().onAuthStateChanged(function (user) {
            if (user) {
                templates.get('edit-project').then(function (template) {
                    projectService.getProjectDataByFileId(pid, fid).then(function (snapshot) {
                        let data = {
                            project: {
                                id: pid,
                                name: name.toLowerCase(),
                                displayName: name
                            },
                            file: {
                                title: snapshot.val().title,
                                content: snapshot.val().content
                            }
                        };

                        $(container).html(template(data));

                        document.title = data.file.title;

                        pageHelper.setActivePage(pageID);

                        $('#ux-btn-save').click(function () {

                        });

                        $('#ux-btn-delete').click(function () {
                            let removeProjectDataByFileIdPromise = projectService.removeProjectDataByFileId(pid, fid);
                            let removeProjectDataReferenceByFileIdPromise = projectService.removeProjectDataReferenceByFileId(pid, fid);

                            Promise.all([removeProjectDataByFileIdPromise, removeProjectDataReferenceByFileIdPromise]).then(values => {
                                toastr.success('Файлът беше изтрит успешно!');

                                window.location.href = '/#/project/view/' + name.toLowerCase() + '/' + pid;
                            }, reason => {
                                toastr.error('Възникнала е грешка при изтриването на файла!');
                            });
                        });
                    });
                });
            } else {
                window.location.href = '#/auth';
            }
        });
    }

    function addProjectData(context, container) {
        let id = context.params.id || null;
        let name = context.params.name || null;

        if (id === null || name === null) {
            window.location.href = '#/';
        }

        firebase.auth().onAuthStateChanged(function (user) {
            if (user) {
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

                        saveFileContent(id, file);
                    });
                });
            } else {
                window.location.href = '#/auth';
            }
        });
    }

    function saveFileContent(projectID, file) {
        let reader = new FileReader();
        reader.readAsText(file, 'UTF-8');
        reader.onload = function (e) {
            projectService.addProjectData(projectID, file.name, e.target.result).then(function (result) {
                toastr.success('Данните бяха добавени успешно!');

                projectService.addProjectDataReference(projectID, result.key, file.name).then(function () {
                    toastr.success('Проектът беше обновен!');

                    window.location.href = '#/projects';
                }, function () {
                    toastr.error('Възникнала е грешка при добавянето на данните!');
                });
            }, function () {
                toastr.error('Възникнала е грешка при добавянето на данните!');
            });
        }
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
            addProjectToList('#projects', project.key, name);

            toastr.success('Обектът беше създаден успешно!');
        }, function (error) {
            console.log(error);
            toastr.error('Възникнала е грешка при създаването на обекта!');
        });
    }

    function deleteProject(context) {
        let projectID = context.params.id || null;

        let deleteProjectPromise = projectService.deleteProject(projectID);
        let deleteProjectDataPromise = projectService.deleteProjectData(projectID);

        Promise.all([deleteProjectPromise, deleteProjectDataPromise]).then(values => {
            toastr.success('Обектът беше изтрит успешно от базата данни!');

            window.location.href = '/#/projects';
        }, reason => {
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