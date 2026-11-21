'use strict';

let authController = (function () {

    let pageID = 'auth';

    function initPage(container) {
        pageHelper.setActivePage(pageID);

        authService.getCurrentUser().then(function (user) {
            if (user) {
                window.location.href = '#/map';
            } else {
                render(container);
            }
        }, function () {
            render(container);
        });
    }

    function render(container) {
        templates.get('auth').then(function (template) {
            $(container).html(template({}));

            document.title = i18n.t('Вход') + ' – nGIS';

            // Returning false keeps the browser from submitting (and reloading) the page.
            $('#ux-form-auth').on('submit', function () {
                submit();

                return false;
            });
        });
    }

    function submit() {
        let email = $('#email').val().trim();
        let password = $('#password').val();

        if (!validationHelper.validateEmail(email) || email.indexOf('@') === -1) {
            toastr.error(i18n.t('Въведете валиден имейл адрес.'));
            $('#email').trigger('focus');

            return;
        }

        if (!validationHelper.validatePassword(password)) {
            toastr.error(i18n.t('Въведете паролата си.'));
            $('#password').trigger('focus');

            return;
        }

        let button = $('#ux-btn-submit').prop('disabled', true);

        authService.signIn(email, password).then(function () {
            toastr.success(i18n.t('Влязохте успешно.'));

            window.location.href = '#/map';
        }, function (error) {
            toastr.error(error.message);
        }).then(function () {
            button.prop('disabled', false);
        });
    }

    return {
        init: initPage
    };
}());
