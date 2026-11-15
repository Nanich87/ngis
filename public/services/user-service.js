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

    return {
        listUsers: listUsers,
        updateUser: updateUser
    };
}());
