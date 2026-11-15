'use strict';

let authController = (function () {

    let pageID = 'auth';
    let pageTemplate = './views/auth.html';

    const MODES = {
        signIn: {
            title: 'Вход',
            subtitle: 'Влезте в nGIS с вашия email и парола.',
            submit: 'Вход',
            switchText: 'Нямате акаунт?',
            switchLink: 'Регистрация'
        },
        signUp: {
            title: 'Регистрация',
            subtitle: 'Създайте акаунт. След това администратор ще ви даде права за достъп.',
            submit: 'Създаване на акаунт',
            switchText: 'Вече имате акаунт?',
            switchLink: 'Вход'
        }
    };

    let mode = 'signIn';

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
        $(container).load(pageTemplate, function () {
            setMode('signIn');

            $('#ux-btn-switch-mode').on('click', function () {
                setMode(mode === 'signIn' ? 'signUp' : 'signIn');
                $('#email').trigger('focus');
            });

            // Returning false also stops Sammy from treating the submit as a route change.
            $('#ux-form-auth').on('submit', function () {
                submit();

                return false;
            });
        });
    }

    function setMode(newMode) {
        mode = newMode;

        let text = MODES[mode];
        let signUp = mode === 'signUp';

        document.title = text.title + ' – nGIS';

        $('#auth-title').text(text.title);
        $('#auth-subtitle').text(text.subtitle);
        $('#ux-btn-submit').text(text.submit);
        $('#auth-switch-text').text(text.switchText);
        $('#ux-btn-switch-mode').text(text.switchLink);

        $('#password').attr('autocomplete', signUp ? 'new-password' : 'current-password');
        $('#password-help').toggleClass('hidden', !signUp);
        $('#password-repeat-group').toggleClass('hidden', !signUp);
        $('#password-repeat').val('');
    }

    function submit() {
        let email = $('#email').val().trim();
        let password = $('#password').val();

        if (!validationHelper.validateEmail(email) || email.indexOf('@') === -1) {
            toastr.error('Невалиден Email адрес!');
            $('#email').trigger('focus');

            return;
        }

        if (!validationHelper.validatePassword(password)) {
            toastr.error('Въведете парола!');
            $('#password').trigger('focus');

            return;
        }

        if (mode === 'signUp') {
            if (password.length < 6) {
                toastr.error('Паролата трябва да е поне 6 символа!');
                $('#password').trigger('focus');

                return;
            }

            if (password !== $('#password-repeat').val()) {
                toastr.error('Паролите не съвпадат!');
                $('#password-repeat').trigger('focus');

                return;
            }
        }

        let button = $('#ux-btn-submit').prop('disabled', true);
        let action = mode === 'signUp'
            ? authService.signUp(email, password).then(function () {
                toastr.success('Успешна регистрация');

                return login(email, password);
            })
            : login(email, password);

        action.catch(function (error) {
            toastr.error(error.message);
        }).then(function () {
            button.prop('disabled', false);
        });
    }

    function login(email, password) {
        return authService.signIn(email, password).then(function () {
            toastr.success('Успешен вход');

            window.location.href = '#/map';
        });
    }

    return {
        init: initPage
    };
}());
