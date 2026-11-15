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

    authService.getCurrentUser().then(function (user) {
        updateNavigation(user);

        if (!user) {
            window.location.href = '#/auth';
        }
    }, function (error) {
        toastr.error(error.message);
    });

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

    router.get('#/map', function () {
        mapController.init(container);
    });

    router.get('#/map/:id', function (context) {
        mapController.view(context, container);
    });

    router.get('#/auth', function () {
        authController.init(container);
    });

    router.get('#/admin', function () {
        adminController.init(container);
    });

    router.get('#/user', function () {
        userController.init(container);
    });

    router.get('#/projects', function () {
        projectController.init(container);
    });

    router.get('#/project/view/:name/:id', function (context) {
        projectController.view(context, container);
    });

    router.get('#/project/edit/:name/:pid/layer/:fid', function (context) {
        projectController.edit(context, container);
    });

    router.get('#/project/add/:name/:id', function (context) {
        projectController.add(context, container);
    });

    router.get('#/logout', function (context) {
        authService.signOut().then(function () {
            context.redirect('#/auth');
        }, function (error) {
            toastr.error(error.message);
        });
    });

    router.notFound(function () {
        mapController.init(container);
    });

    $(function () {
        router.start('#/');
    });
}());
