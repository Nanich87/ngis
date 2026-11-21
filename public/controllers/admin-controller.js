'use strict';

let adminController = (function () {

    let pageID = 'admin';

    const RIGHTS = [
        { key: 'canRead', label: 'Четене' },      // translated where shown
        { key: 'canWrite', label: 'право|Запис' },
        { key: 'isAdmin', label: 'Админ' }
    ];

    let currentUser = null;

    function initPage(container) {
        pageHelper.setActivePage(pageID);

        authService.requireUser().then(function (user) {
            if (!user.isAdmin) {
                window.location.href = '#/map';

                return;
            }

            currentUser = user;

            templates.get('admin').then(function (template) {
                $(container).html(template({}));

                document.title = i18n.t('Потребители') + ' – nGIS';

                $('#user-search').on('input', function () {
                    filterUsers(this.value);
                });

                initCreateUserModal();

                $('#ux-btn-copy-password').on('click', function () {
                    pageHelper.copyText($('#password-modal-value').val(), i18n.t('Паролата е копирана.'));
                });

                userService.listUsers().then(function (users) {
                    let tbody = $('#users tbody').empty();

                    users.forEach(user => tbody.append(userRow(user)));

                    updateSummary();
                    $('.loading-indicator').addClass('hidden');
                    $('#users').removeClass('hidden');
                }, function (error) {
                    toastr.error(error.message);
                });
            });
        });
    }

    // ------------------------------------------------------------------ table

    function userRow(user) {
        let isSelf = user.uid === currentUser.uid;

        let name = $('<div class="fw-medium text-break"></div>').text(user.displayName ? user.displayName + ' · ' + user.email : user.email);

        if (isSelf) {
            name.append(' ', $('<span class="badge text-bg-secondary"></span>').text(i18n.t('Вие')));
        }

        let who = $('<div class="min-w-0"></div>').append(
            name,
            $('<div class="small text-body-secondary font-monospace text-break"></div>').text(user.uid)
        );

        if (user.hasPassword === false) {
            who.append($('<span class="badge text-bg-warning mt-1 no-password-badge"></span>').text(i18n.t('Без парола')));
        }

        let row = $('<tr></tr>')
            .attr('data-search', [user.email, user.displayName || '', user.uid].join(' ').toLowerCase())
            .append($('<td></td>').append(who))
            .append($('<td class="text-nowrap small"></td>').text(pageHelper.formatDate(user.createdAt)));

        RIGHTS.forEach(function (right) {
            let input = $('<input class="form-check-input" type="checkbox" role="switch" />')
                .attr('id', 'right-' + right.key + '-' + user.uid.replace(/[^a-zA-Z0-9_-]/g, '_'))
                .attr('aria-label', i18n.t(right.label) + ' – ' + user.email)
                .prop('checked', user[right.key]);

            let locked = right.key === 'isAdmin' && isSelf;

            if (locked) {
                input.prop('disabled', true).attr('title', i18n.t('Не можете да премахнете собствените си администраторски права'));
            }

            input.on('change', function () {
                let checked = this.checked;
                let changes = {};
                changes[right.key] = checked;

                input.prop('disabled', true);

                userService.updateUser(user.uid, changes).then(function (updated) {
                    Object.assign(user, updated);
                    toastr.success(i18n.t('Правата на {email} са обновени.', { email: user.email }));
                }, function (error) {
                    input.prop('checked', !checked);
                    toastr.error(error.message);
                }).then(function () {
                    input.prop('disabled', locked);
                });
            });

            row.append($('<td class="text-center"></td>').append(
                $('<div class="form-check form-switch d-inline-block m-0"></div>').append(input)));
        });

        let resetButton = $('<button type="button" class="btn btn-sm btn-neutral text-nowrap"><span class="fa">&#xf084;</span> </button>')
            .append(document.createTextNode(i18n.t('Нова парола')))
            .attr('aria-label', i18n.t('Нова парола за {email}', { email: user.email }));
        let actions = $('<div class="d-inline-flex gap-2"></div>').append(resetButton);

        resetButton.on('click', function () {
            resetPassword(user, row);
        });

        if (!isSelf) {
            let deleteButton = $('<button type="button" class="btn btn-sm btn-outline-danger"><span class="fa">&#xf1f8;</span></button>')
                .attr('aria-label', i18n.t('Изтриване на {name}', { name: user.email }))
                .attr('title', i18n.t('Изтриване'));

            deleteButton.on('click', function () {
                deleteUser(user, row);
            });

            actions.append(deleteButton);
        }

        return row.append($('<td class="text-end"></td>').append(actions));
    }

    function updateSummary() {
        $('#users-summary').text(pageHelper.formatCount($('#users tbody tr').length, 'потребител', 'потребители'));
    }

    function filterUsers(query) {
        query = query.trim().toLowerCase();

        $('#users tbody tr').each(function () {
            $(this).toggleClass('hidden', query !== '' && this.getAttribute('data-search').indexOf(query) === -1);
        });
    }

    // ------------------------------------------------------------------ actions

    function showPassword(email, password) {
        $('#password-modal-email').text(email);
        $('#password-modal-value').val(password);

        let modal = document.getElementById('password-modal');

        $(modal).one('shown.bs.modal', function () {
            $('#password-modal-value').trigger('focus').trigger('select');
        });
        // Do not leave the password in the DOM after the dialog is closed.
        $(modal).one('hidden.bs.modal', function () {
            $('#password-modal-value').val('');
        });

        bootstrap.Modal.getOrCreateInstance(modal).show();
    }

    function initCreateUserModal() {
        let modal = $('#create-user-modal');

        modal.on('show.bs.modal', function () {
            $('#create-user-form')[0].reset();
            $('#create-user-form .is-invalid').removeClass('is-invalid');
        });

        modal.on('shown.bs.modal', function () {
            $('#new-user-email').trigger('focus');
        });

        // Admin implies read and write.
        $('#new-user-admin').on('change', function () {
            if (this.checked) {
                $('#new-user-read, #new-user-write').prop('checked', true);
            }
        });

        // Returning false keeps the browser from submitting (and reloading) the page.
        $('#create-user-form').on('submit', function () {
            createUser();

            return false;
        });
    }

    function createUser() {
        let email = $('#new-user-email').val().trim();
        let valid = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email);

        $('#new-user-email').toggleClass('is-invalid', !valid);
        $('#new-user-email-error').text(valid ? '' : i18n.t('Въведете валиден email адрес.'));

        if (!valid) {
            $('#new-user-email').trigger('focus');

            return;
        }

        let button = $('#ux-btn-create-user').prop('disabled', true);

        userService.createUser({
            email: email,
            displayName: $('#new-user-name').val().trim(),
            canRead: $('#new-user-read').prop('checked'),
            canWrite: $('#new-user-write').prop('checked'),
            isAdmin: $('#new-user-admin').prop('checked')
        }).then(function (result) {
            let user = Object.assign({ createdAt: null, hasPassword: true }, result.user);

            $('#users tbody').append(userRow(user));
            updateSummary();

            bootstrap.Modal.getInstance(document.getElementById('create-user-modal')).hide();
            $('#create-user-modal').one('hidden.bs.modal', function () {
                showPassword(user.email, result.password);
            });
        }, function (error) {
            if (error.status === 409) {
                $('#new-user-email').addClass('is-invalid');
                $('#new-user-email-error').text(error.message);
            } else {
                toastr.error(error.message);
            }
        }).then(function () {
            button.prop('disabled', false);
        });
    }

    function resetPassword(user, row) {
        let self = user.uid === currentUser.uid;

        pageHelper.confirm({
            title: i18n.t('Нова парола'),
            body: i18n.t(self
                ? 'Ще бъде генерирана нова парола за {email}. Старата спира да важи и потребителят излиза от всички устройства, включително от това.'
                : 'Ще бъде генерирана нова парола за {email}. Старата спира да важи и потребителят излиза от всички устройства.', { email: user.email }),
            confirmText: i18n.t('Генериране')
        }).then(function (confirmed) {
            if (!confirmed) {
                return;
            }

            userService.resetPassword(user.uid).then(function (result) {
                row.find('.no-password-badge').remove();
                showPassword(user.email, result.password);

                if (self) {
                    // Our own session was ended on the server; sign in again with the new password.
                    $('#password-modal').one('hidden.bs.modal', function () {
                        window.location.href = '#/logout';
                    });
                }
            }, function (error) {
                toastr.error(error.message);
            });
        });
    }

    function deleteUser(user, row) {
        pageHelper.confirm({
            title: i18n.t('Изтриване на потребител'),
            body: i18n.t('Акаунтът {email} ще бъде изтрит безвъзвратно. Обектите и файловете остават.', { email: user.email }),
            confirmText: i18n.t('Изтриване'),
            danger: true
        }).then(function (confirmed) {
            if (!confirmed) {
                return;
            }

            userService.deleteUser(user.uid).then(function () {
                row.remove();
                updateSummary();
                toastr.success(i18n.t('Потребителят {email} беше изтрит.', { email: user.email }));
            }, function (error) {
                toastr.error(error.message);
            });
        });
    }

    return {
        init: initPage
    };
}());
