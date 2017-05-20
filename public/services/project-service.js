'use strict';

let projectService = (function () {

    function createProject(name, year) {
        let projectRef = firebase.app().database().ref();
        let projects = projectRef.child('projects');

        return projects.push({
            name: name,
            year: year
        });
    }

    function deleteProject(id) {
        let ref = firebase.app().database().ref();
        let projects = ref.child('projects');

        return projects.child(id).remove();
    }

    function deleteProjectData(id) {
        let ref = firebase.app().database().ref();
        let projects = ref.child('project-data');

        return projects.child(id).remove();
    }

    function getProjects() {
        return firebase.database().ref('/projects').once('value');
    }

    function getProjectById(id) {
        return firebase.database().ref('/projects/' + id).once('value');
    }

    function getProjectData(id) {
        return firebase.database().ref('/project-data/' + id + '/data').once('value');
    }

    function getProjectDataByFileId(pid, fid) {
        return firebase.database().ref('/project-data/' + pid + '/data/' + fid).once('value');
    }

    function removeProjectDataByFileId(pid, fid) {
        return firebase.database().ref('/project-data/' + pid + '/data/' + fid).remove();
    }

    function removeProjectDataReferenceByFileId(pid, fid) {
        return firebase.database().ref('/projects/' + pid + '/data/' + fid).remove();
    }

    function addProjectData(id, title, content) {
        return firebase.database().ref('/project-data/' + id + '/data').push({ title: title, content: content });
    }

    function addProjectDataReference(id, key, title) {
        return firebase.database().ref('/projects/' + id + '/data/' + key).set(title);
    }

    function uploadFile(project, file) {
        let storageRef = firebase.storage().ref(project);
        let fileRef = storageRef.child(file.name);

        return fileRef.put(file);
    }

    return {
        createProject: createProject,
        deleteProject: deleteProject,
        deleteProjectData: deleteProjectData,
        getProjects: getProjects,
        getProjectById: getProjectById,
        getProjectData: getProjectData,
        uploadFile: uploadFile,
        addProjectData: addProjectData,
        addProjectDataReference: addProjectDataReference,
        getProjectDataByFileId: getProjectDataByFileId,
        removeProjectDataByFileId: removeProjectDataByFileId,
        removeProjectDataReferenceByFileId: removeProjectDataReferenceByFileId
    };
}());