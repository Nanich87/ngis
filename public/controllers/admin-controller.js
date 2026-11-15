'use strict';

let adminController = (function () {

    let pageID = 'admin';

    const RIGHTS = [
        { key: 'canRead', label: 'Четене' },
        { key: 'canWrite', label: 'Запис' },
        { key: 'isAdmin', label: 'Админ' }
    ];

    function initPage(container) {
        pageHelper.setActivePage(pageID);

        authService.requireUser().then(function (currentUser) {
            if (!currentUser.isAdmin) {
                window.location.href = '#/map';

                return;
            }

            templates.get('admin').then(function (template) {
                $(container).html(template({}));

                document.title = 'Потребители – nGIS';

                $('#user-search').on('input', function () {
                    filterUsers(this.value);
                });

                userService.listUsers().then(function (users) {
                    renderUsers(users, currentUser);
                }, function (error) {
                    toastr.error(error.message);
                });
            });
        });
    }

    function renderUsers(users, currentUser) {
        let tbody = $('#users tbody').empty();

        users.forEach(function (user) {
            let who = $('<div class="min-w-0"></div>').append(
                $('<div class="fw-medium text-break"></div>').text(user.displayName ? user.displayName + ' · ' + user.email : user.email),
                $('<div class="small text-body-secondary font-monospace text-break"></div>').text(user.uid)
            );

            if (!user.hasPassword) {
                who.append('<span class="badge text-bg-warning mt-1">Без парола</span>');
            }

            if (user.uid === currentUser.uid) {
                who.find('.fw-medium').append(' <span class="badge text-bg-secondary">Вие</span>');
            }

            let row = $('<tr></tr>')
                .attr('data-search', [user.email, user.displayName || '', user.uid].join(' ').toLowerCase())
                .append($('<td></td>').append(who))
                .append($('<td class="text-nowrap small"></td>').text(pageHelper.formatDate(user.createdAt)));

            RIGHTS.forEach(function (right) {
                let id = 'right-' + right.key + '-' + user.uid.replace(/[^a-zA-Z0-9_-]/g, '_');
                let input = $('<input class="form-check-input" type="checkbox" role="switch" />')
                    .attr('id', id)
                    .attr('aria-label', right.label + ' – ' + user.email)
                    .prop('checked', user[right.key]);

                if (right.key === 'isAdmin' && user.uid === currentUser.uid) {
                    input.prop('disabled', true).attr('title', 'Не можете да премахнете собствените си администраторски права');
                }

                input.on('change', function () {
                    let checked = this.checked;
                    let changes = {};
                    changes[right.key] = checked;

                    input.prop('disabled', true);

                    userService.updateUser(user.uid, changes).then(function (updated) {
                        Object.assign(user, updated);
                        toastr.success('Правата на ' + user.email + ' са обновени.');
                    }, function (error) {
                        input.prop('checked', !checked);
                        toastr.error(error.message);
                    }).then(function () {
                        input.prop('disabled', false);
                    });
                });

                row.append($('<td class="text-center"></td>').append(
                    $('<div class="form-check form-switch d-inline-block m-0"></div>').append(input)));
            });

            tbody.append(row);
        });

        $('#users-summary').text(pageHelper.formatCount(users.length, 'потребител', 'потребители'));
        $('.loading-indicator').addClass('hidden');
        $('#users').removeClass('hidden');
    }

    function filterUsers(query) {
        query = query.trim().toLowerCase();

        $('#users tbody tr').each(function () {
            $(this).toggleClass('hidden', query !== '' && this.getAttribute('data-search').indexOf(query) === -1);
        });
    }

    return {
        init: initPage
    };
}());
