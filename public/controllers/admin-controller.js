'use strict';

let adminController = (function () {

    let pageID = 'user';

    function initPage(container) {
        pageHelper.setActivePage(pageID);

        firebase.auth().onAuthStateChanged(function (user) {
            if (user) {
                userService.isAdmin(user.uid).then(function (snapshot) {
                    if (snapshot.val() !== null) {
                        templates.get('admin').then(function (template) {
                            $(container).html(template({}));

                            document.title = 'Контролен панел';

                            $('#ux-btn-add-rights').click(function () {
                                let userID = $('#user-id').val();
                                let rights = $('input[name=rights]:checked', '#user-rights').val();

                                if (userID.length === 0) {
                                    toastr.error('Няма въведен UID на потребител!');

                                    return;
                                }

                                userService.addRights(userID, rights).then(values => {
                                    toastr.success('Правата бяха добавени успешно!');
                                }, reason => {
                                    toastr.error('Възникнала е грешка при добавянето на правата!');
                                });;
                            });

                            $('#ux-btn-remove-rights').click(function () {
                                let userID = $('#user-id').val();
                                let rights = $('input[name=rights]:checked', '#user-rights').val();

                                if (userID.length === 0) {
                                    toastr.error('Няма въведен UID на потребител!');

                                    return;
                                }

                                userService.removeRights(userID, rights).then(values => {
                                    toastr.success('Правата бяха премахнати успешно!');
                                }, reason => {
                                    toastr.error('Възникнала е грешка при премахването на правата!');
                                });;
                            });
                        });
                    } else {
                        window.location.href = '#/auth';
                    }
                });
            } else {
                window.location.href = '#/auth';
            }
        });
    }

    return {
        init: initPage
    };
}());