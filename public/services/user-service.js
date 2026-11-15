'use strict';

let userService = (function () {

    // [{ uid, email, displayName, isAdmin, canRead, canWrite, createdAt, hasPassword }]
    function listUsers() {
        return api.get('/api/admin/users');
    }

    // changes: any of { canRead, canWrite, isAdmin }
    function updateUser(userID, changes) {
        return api.patch('/api/admin/users/' + encodeURIComponent(userID), changes);
    }

    // Returns { user, password }; the generated password is shown once.
    function createUser(data) {
        return api.post('/api/admin/users', data);
    }

    // Returns { password }; signs the user out everywhere.
    function resetPassword(userID) {
        return api.post('/api/admin/users/' + encodeURIComponent(userID) + '/password');
    }

    function deleteUser(userID) {
        return api.delete('/api/admin/users/' + encodeURIComponent(userID));
    }

    return {
        listUsers: listUsers,
        updateUser: updateUser,
        createUser: createUser,
        resetPassword: resetPassword,
        deleteUser: deleteUser
    };
}());
