'use strict';

let userController = (function () {

    let pageID = 'user';

    function initPage(container) {
        pageHelper.setActivePage(pageID);

        firebase.auth().onAuthStateChanged(function (user) {
            if (user) {
                templates.get('user').then(function (template) {
                    userService.isAdmin(user.uid).then(function (snapshot) {
                        let data = {
                            isAdmin: snapshot.val() !== null ? true : false,
                            user: user,
                            notAuthorized: false,
                        };

                        $(container).html(template(data));

                        document.title = user.displayName !== null ? user.displayName : user.email;

                        $('#ux-btn-save').click(function () {
                            let displayName = $('#displayName').val();
                            let photoURL = $('#photoURL').val();

                            user.updateProfile({
                                displayName: displayName,
                                photoURL: photoURL
                            }).then(function () {
                                $('#titleName').text(displayName);
                                toastr.success('Данните бяха записани успешно!');
                            }, function (error) {
                                toastr.error('Възникнала е грешка при записването на данните!');
                            });
                        });
                    }, function (error) {
                        let data = {
                            isAdmin: false,
                            user: null,
                            notAuthorized: true,
                        };

                        $(container).html(template(data));

                        document.title = 'Access Denided';
                    });
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