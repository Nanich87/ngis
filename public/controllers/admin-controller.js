'use strict';

let adminController = (function () {

    let pageID = 'user';

    function initPage(container) {
        pageHelper.setActivePage(pageID);

        authService.requireUser().then(function (user) {
            if (!user.isAdmin) {
                window.location.href = '#/auth';

                return;
            }

            templates.get('admin').then(function (template) {
                $(container).html(template({}));

                document.title = 'Контролен панел';

                $('#ux-btn-add-rights').click(function () {
                    changeRights(userService.addRights, 'Правата бяха добавени успешно!');
                });

                $('#ux-btn-remove-rights').click(function () {
                    changeRights(userService.removeRights, 'Правата бяха премахнати успешно!');
                });
            });
        });
    }

    function changeRights(action, successMessage) {
        let userID = $('#user-id').val().trim();
        let rights = $('input[name=rights]:checked', '#user-rights').val();

        if (userID.length === 0) {
            toastr.error('Няма въведен UID на потребител!');

            return;
        }

        action(userID, rights).then(function () {
            toastr.success(successMessage);
        }, function (error) {
            toastr.error(error.message);
        });
    }

    return {
        init: initPage
    };
}());
