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
                    copyText(user.uid);
                });

                // Returning false also stops Sammy from treating the submit as a route change.
                $('#profile-form').on('submit', function () {
                    save();

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

    function copyText(text) {
        let done = () => toastr.success('ID е копиран.');

        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(text).then(done, () => fallbackCopy(text, done));
        } else {
            fallbackCopy(text, done);
        }
    }

    // navigator.clipboard needs HTTPS; plain-HTTP LAN access falls back to execCommand.
    function fallbackCopy(text, done) {
        let input = $('<textarea class="visually-hidden"></textarea>').val(text).appendTo('body');

        input[0].select();

        try {
            if (document.execCommand('copy')) {
                done();
            } else {
                throw new Error();
            }
        } catch (e) {
            toastr.info('Копирайте ID ръчно: ' + text);
        }

        input.remove();
    }

    return {
        init: initPage
    };
}());
