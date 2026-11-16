'use strict';

let projectService = (function () {

    function url(...parts) {
        return '/api/projects' + parts.map(p => '/' + encodeURIComponent(p)).join('');
    }

    function createProject(name, year) {
        return api.post(url(), { name: name, year: year });
    }

    // Also deletes all of the project's files (ON DELETE CASCADE).
    function deleteProject(id) {
        return api.delete(url(id));
    }

    function getProjects() {
        return api.get(url());
    }

    // { id, name, year, data: { fileId: title } }
    function getProjectById(id) {
        return api.get(url(id));
    }

    // [{ id, title, content }]
    function getProjectData(id) {
        return api.get(url(id, 'layers'));
    }

    function getProjectDataByFileId(pid, fid) {
        return api.get(url(pid, 'layers', fid));
    }

    function removeProjectDataByFileId(pid, fid) {
        return api.delete(url(pid, 'layers', fid));
    }

    function addProjectData(id, title, content) {
        return api.post(url(id, 'layers'), { title: title, content: content });
    }

    // data: the CAD file as base64; the server converts it to GeoJSON.
    function addCadFile(id, title, data) {
        return api.post(url(id, 'layers', 'cad'), { title: title, data: data });
    }

    return {
        addCadFile: addCadFile,
        createProject: createProject,
        deleteProject: deleteProject,
        getProjects: getProjects,
        getProjectById: getProjectById,
        getProjectData: getProjectData,
        addProjectData: addProjectData,
        getProjectDataByFileId: getProjectDataByFileId,
        removeProjectDataByFileId: removeProjectDataByFileId
    };
}());
