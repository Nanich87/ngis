'use strict';

let userController = (function () {

    let pageID = 'user';

    function initPage(container) {
        pageHelper.setActivePage(pageID);

        authService.requireUser().then(function (user) {
            templates.get('user').then(function (template) {
                let data = {
                    isAdmin: user.isAdmin,
                    user: user,
                    notAuthorized: false
                };

                $(container).html(template(data));

                document.title = user.displayName ? user.displayName : user.email;

                $('#ux-btn-save').click(function () {
                    let displayName = $('#displayName').val();
                    let photoURL = $('#photoURL').val();

                    authService.updateProfile(displayName, photoURL).then(function () {
                        $('#titleName').text(displayName);
                        toastr.success('Данните бяха записани успешно!');
                    }, function (error) {
                        toastr.error('Възникнала е грешка при записването на данните!');
                    });
                });
            });
        });
    }

    return {
        init: initPage
    };
}());
