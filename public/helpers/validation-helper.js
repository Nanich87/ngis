'use strict';

let validationHelper = (function () {

    function validateEmail(email) {
        if (typeof email === 'string' && email.length > 0) {
            return true;
        }

        return false;
    }

    function validatePassword(password) {
        if (typeof password === 'string' && password.length > 0) {
            return true;
        }

        return false;
    }

    return {
        validateEmail: validateEmail,
        validatePassword: validatePassword
    };
}());