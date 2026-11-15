'use strict';

let userController = (function () {

    let pageID = 'user';

    function initials(user) {
        let source = (user.displayName || user.email || '?').trim();
        let parts = source.split(/[\s@._-]+/).filter(Boolean);
        let letters = parts.length > 1 ? parts[0][0] + parts[1][0] : source.slice(0, 2);

        return letters.toUpperCase();
    }

    function isHttpUrl(value) {
        return /^https?:\/\/\S+$/i.test(value);
    }

    // Shows the photo if it loads, otherwise keeps the initials.
    function renderAvatar(element, user) {
        element.text(initials(user));

        if (user.photoURL && isHttpUrl(user.photoURL)) {
            let img = new Image();

            img.alt = '';
            img.onload = () => element.empty().append(img);
            img.src = user.photoURL;
        }
    }

    function initPage(container) {
        pageHelper.setActivePage(pageID);

        authService.requireUser().then(function (user) {
            templates.get('user').then(function (template) {
                $(container).html(template({
                    user: user,
                    initials: initials(user),
                    hasAnyRights: user.canRead || user.canWrite || user.isAdmin
                }));

                document.title = (user.displayName || user.email) + ' – nGIS';

                renderAvatar($('#profile-avatar'), user);

                $('#ux-btn-copy-uid').on('click', function () {
                    pageHelper.copyText(user.uid, 'ID е копиран.');
                });

                // Returning false keeps the browser from submitting (and reloading) the page.
                $('#profile-form').on('submit', function () {
                    save();

                    return false;
                });

                $('#password-form').on('submit', function () {
                    changePassword();

                    return false;
                });
            });
        });
    }

    function save() {
        let displayName = $('#displayName').val().trim();
        let photoURL = $('#photoURL').val().trim();
        let invalidPhoto = photoURL !== '' && !isHttpUrl(photoURL);

        $('#photoURL').toggleClass('is-invalid', invalidPhoto);

        if (invalidPhoto) {
            $('#photoURL').trigger('focus');

            return;
        }

        let button = $('#ux-btn-save').prop('disabled', true);

        authService.updateProfile(displayName, photoURL).then(function (user) {
            $('#titleName').text(user.displayName || user.email);
            renderAvatar($('#profile-avatar'), user);

            toastr.success('Данните бяха записани.');
        }, function (error) {
            toastr.error(error.message || 'Възникнала е грешка при записването на данните!');
        }).then(function () {
            button.prop('disabled', false);
        });
    }

    function fieldError(selector, message) {
        $(selector).toggleClass('is-invalid', !!message);
        $(selector + '-error').text(message || '');

        return !!message;
    }

    function changePassword() {
        let current = $('#current-password').val();
        let next = $('#new-password').val();
        let repeat = $('#new-password-repeat').val();

        let invalid = fieldError('#current-password', current ? null : 'Въведете текущата парола.');
        invalid = fieldError('#new-password', next.length < 10 ? 'Паролата трябва да е поне 10 символа.'
            : next === current ? 'Новата парола съвпада с текущата.' : null) || invalid;
        invalid = fieldError('#new-password-repeat', repeat !== next ? 'Паролите не съвпадат.' : null) || invalid;

        if (invalid) {
            $('#password-form .is-invalid').first().trigger('focus');

            return;
        }

        let button = $('#ux-btn-change-password').prop('disabled', true);

        authService.changePassword(current, next).then(function () {
            $('#password-form')[0].reset();
            toastr.success('Паролата беше сменена.');
        }, function (error) {
            if (error.status === 400 && /текущата/i.test(error.message)) {
                fieldError('#current-password', error.message);
                $('#current-password').trigger('focus');
            } else {
                toastr.error(error.message);
            }
        }).then(function () {
            button.prop('disabled', false);
        });
    }

    return {
        init: initPage
    };
}());
