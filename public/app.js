'use strict';

(function () {
    let container = '#content';

    function updateNavigation(user) {
        if (user) {
            $('#ux-btn-profile').html('<span class="fa">&#xf007;</span> ').append(document.createTextNode(user.email)).attr('href', '/#/user').removeClass('hidden');
            $('#ux-btn-auth').html('<span class="fa">&#xf08b;</span> Изход').attr('href', '/#/logout');
        } else {
            $('#ux-btn-profile').html('').attr('href', '#').addClass('hidden');
            $('#ux-btn-auth').html('<span class="fa">&#xf090;</span> Вход').attr('href', '/#/auth');
        }
    }

    authService.onAuthStateChanged(updateNavigation);

    authService.getCurrentUser().then(function (user) {
        updateNavigation(user);

        if (!user) {
            window.location.href = '#/auth';
        }
    }, function (error) {
        toastr.error(error.message);
    });

    let app = Sammy(container, function () {
        // Reset per-page layout state; the map controller re-enables it.
        this.before(function () {
            $('body').removeClass('page-map');

            let menu = document.getElementById('app-navbar-menu');

            if (menu && menu.classList.contains('show')) {
                bootstrap.Collapse.getOrCreateInstance(menu).hide();
            }
        });

        this.get('#/', function () {
            this.redirect('#/map');
        });

        this.get('#/map', function () {
            mapController.init(container);
        });

        this.get('#/map/:id', function (context) {
            mapController.view(context, container);
        });

        this.get('#/auth', function () {
            authController.init(container);
        });

        this.get('#/admin', function (context) {
            adminController.init(container);
        });

        this.get('#/user', function (context) {
            userController.init(container);
        });

        this.get('#/projects', function () {
            projectController.init(container);
        });

        this.get('#/project/view/:name/:id', function (context) {
            projectController.view(context, container);
        });

        this.get('#/project/edit/:name/:pid/layer/:fid', function (context) {
            projectController.edit(context, container);
        });

        this.get('#/project/add/:name/:id', function (context) {
            projectController.add(context, container);
        });

        this.get('#/logout', function () {
            let context = this;

            authService.signOut().then(function () {
                context.redirect('#/auth');
            }, function (error) {
                toastr.error(error.message);
            });
        });

        this.notFound = function () {
            mapController.init(container);
        };
    });

    $(function () {
        app.run('#/');
    });
}());