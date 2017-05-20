'use strict';

let userService = (function () {

    function getUserInfo(id) {

    }

    function isAdmin(userID) {
        return firebase.database().ref('/groups/admins/').child(userID).once('value');
    }

    function addRights(userID, rights) {
        switch (rights) {
            case 'read':
                return firebase.database().ref('/access/read/' + userID).set(true);
            case 'write':
                return firebase.database().ref('/access/write/' + userID).set(true);
            case 'both':
                let addReadAccessPromise = firebase.database().ref('/access/read/' + userID).set(true);
                let addWriteAccessPromise = firebase.database().ref('/access/write/' + userID).set(true);

                return Promise.all([addReadAccessPromise, addWriteAccessPromise]);
        }
    }

    function removeRights(userID, rights) {
        switch (rights) {
            case 'read':
                return firebase.database().ref('/access/read/' + userID).remove();
            case 'write':
                return firebase.database().ref('/access/write/' + userID).remove();
            case 'both':
                let removeReadAccessPromise = firebase.database().ref('/access/read/' + userID).remove();
                let removeWriteAccessPromise = firebase.database().ref('/access/write/' + userID).remove();

                return Promise.all([removeReadAccessPromise, removeWriteAccessPromise]);
        }
    }

    return {
        getUserInfo: getUserInfo,
        addRights: addRights,
        removeRights: removeRights,
        isAdmin: isAdmin
    };
}());