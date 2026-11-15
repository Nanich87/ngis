'use strict';

let userService = (function () {

    // rights: 'read' | 'write' | 'both'; userID may be a UID or an email address
    function changeRights(userID, rights, grant) {
        return api.post('/api/admin/users/' + encodeURIComponent(userID) + '/rights', {
            rights: rights,
            grant: grant
        });
    }

    function addRights(userID, rights) {
        return changeRights(userID, rights, true);
    }

    function removeRights(userID, rights) {
        return changeRights(userID, rights, false);
    }

    return {
        addRights: addRights,
        removeRights: removeRights
    };
}());
