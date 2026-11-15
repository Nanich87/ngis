'use strict';

let authService = (function () {

    let currentUserPromise = null;
    let listeners = [];

    function setUser(user) {
        currentUserPromise = Promise.resolve(user);

        listeners.forEach(listener => listener(user));

        return user;
    }

    // Resolves with the logged-in user or null.
    function getCurrentUser() {
        if (currentUserPromise === null) {
            currentUserPromise = api.get('/api/me').catch(function (error) {
                if (error.status === 401) {
                    return null;
                }

                currentUserPromise = null;

                throw error;
            });
        }

        return currentUserPromise;
    }

    // Resolves with the logged-in user; otherwise redirects to the login page and never resolves.
    function requireUser() {
        return getCurrentUser().then(function (user) {
            if (!user) {
                window.location.href = '#/auth';

                return new Promise(function () { });
            }

            return user;
        }, function (error) {
            toastr.error(error.message);

            return new Promise(function () { });
        });
    }

    function onAuthStateChanged(listener) {
        listeners.push(listener);
    }

    function signIn(email, password) {
        return api.post('/api/auth/login', { email: email, password: password }).then(setUser);
    }

    function signOut() {
        return api.post('/api/auth/logout').then(function () {
            setUser(null);
        });
    }

    function updateProfile(displayName, photoURL) {
        return api.patch('/api/me', { displayName: displayName, photoURL: photoURL }).then(setUser);
    }

    function changePassword(currentPassword, newPassword) {
        return api.post('/api/me/password', { currentPassword: currentPassword, newPassword: newPassword });
    }

    return {
        changePassword: changePassword,
        getCurrentUser: getCurrentUser,
        requireUser: requireUser,
        onAuthStateChanged: onAuthStateChanged,
        signIn: signIn,
        signOut: signOut,
        updateProfile: updateProfile
    };
}());
