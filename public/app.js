'use strict';

(function () {
    let container = '#content';

    function updateNavigation(user) {
        if (user) {
            $('#ux-btn-profile').html('<span class="fa">&#xf007;</span> ').append(document.createTextNode(user.email)).attr('href', '/#/user').removeClass('hidden');
            $('#ux-btn-auth').html('<span class="fa">&#xf08b;</span> Изход').attr('href', '/#/logout');
            $('#ux-btn-admin').toggleClass('hidden', !user.isAdmin);
        } else {
            $('#ux-btn-admin').addClass('hidden');
            $('#ux-btn-profile').html('').attr('href', '#').addClass('hidden');
            $('#ux-btn-auth').html('<span class="fa">&#xf090;</span> Вход').attr('href', '/#/auth');
        }
    }

    authService.onAuthStateChanged(updateNavigation);

    $('#footer-year').text(new Date().getFullYear());

    // Messages can contain user-supplied text (file names, server errors).
    toastr.options.escapeHtml = true;
    toastr.options.positionClass = 'toast-bottom-right';
    toastr.options.newestOnTop = false;

    authService.getCurrentUser().then(updateNavigation, function (error) {
        toastr.error(error.message);
    });

    // Wraps a route that needs a signed-in user: the session is checked first and the page is
    // rendered only for a signed-in user, so nothing flashes before the redirect to #/auth.
    // The user is cached after the first request, so the check is instant afterwards.
    function authenticated(handler) {
        return function (context) {
            authService.getCurrentUser().then(function (user) {
                if (router.currentPath() !== context.path) {
                    return;   // the user navigated elsewhere while we were checking
                }

                if (user) {
                    handler.call(context, context);
                } else {
                    context.redirect('#/auth');
                }
            }, function (error) {
                toastr.error(error.message);
            });
        };
    }

    // Reset per-page layout state; the map controller re-enables it.
    router.before(function () {
        $('body').removeClass('page-map');

        let menu = document.getElementById('app-navbar-menu');

        if (menu && menu.classList.contains('show')) {
            bootstrap.Collapse.getOrCreateInstance(menu).hide();
        }
    });

    router.get('#/', function (context) {
        context.redirect('#/map');
    });

    router.get('#/map', authenticated(function () {
        mapController.init(container);
    }));

    router.get('#/map/:id', authenticated(function (context) {
        mapController.view(context, container);
    }));

    router.get('#/auth', function () {
        authController.init(container);
    });

    router.get('#/admin', authenticated(function () {
        adminController.init(container);
    }));

    router.get('#/user', authenticated(function () {
        userController.init(container);
    }));

    router.get('#/projects', authenticated(function () {
        projectController.init(container);
    }));

    router.get('#/project/view/:name/:id', authenticated(function (context) {
        projectController.view(context, container);
    }));

    router.get('#/project/edit/:name/:pid/layer/:fid', authenticated(function (context) {
        projectController.edit(context, container);
    }));

    router.get('#/project/add/:name/:id', authenticated(function (context) {
        projectController.add(context, container);
    }));

    router.get('#/logout', function (context) {
        authService.signOut().then(function () {
            context.redirect('#/auth');
        }, function (error) {
            toastr.error(error.message);
        });
    });

    router.notFound(authenticated(function () {
        mapController.init(container);
    }));

    $(function () {
        router.start('#/');
    });
}());
