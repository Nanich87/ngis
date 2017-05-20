'use strict';

let authController = (function () {

    let pageID = 'auth';
    let pageTitle = 'Вход / Регистрация';
    let pageTemplate = './views/auth.html';

    function initPage(container) {
        document.title = pageTitle;

        pageHelper.setActivePage(pageID);

        $(container).load(pageTemplate, function () {
            $('#ux-btn-sign-in').click(signIn);
            $('#ux-btn-sign-up').click(signUp);
        });
    }

    function signUp() {
        let email = $('#email').val();
        let password = $('#password').val();

        if (!validationHelper.validateEmail(email)) {
            toastr.error('Невалиден Email адрес!');

            return;
        }

        if (!validationHelper.validatePassword(password)) {
            toastr.error('Невалидна парола!');

            return;
        }

        authService.signUp(email, password).then(function (user) {
            toastr.success('Успешна регистрация');

            login(email, password);
        }, function (error) {
            toastr.error(error.message);
        });
    }

    function signIn() {
        let email = $('#email').val();
        let password = $('#password').val();

        if (!validationHelper.validateEmail(email)) {
            toastr.error('Невалиден Email адрес!');

            return;
        }

        if (!validationHelper.validatePassword(password)) {
            toastr.error('Невалидна парола!');

            return;
        }

        login(email, password);
    }

    function login(email, password) {
        authService.signIn(email, password).then(function (user) {
            toastr.success('Успешен вход');

            window.location.href = '#/map';
        }, function (error) {
            toastr.error(error.message);
        });
    }

    return {
        init: initPage
    };
}());