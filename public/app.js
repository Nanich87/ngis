'use strict';

(function () {
    let container = '#content';

    firebase.initializeApp({
        apiKey: "AIzaSyDmtrzJpvAlkb-MH74ghT95bSzm5sq94kE",
        authDomain: "tg-gis.firebaseapp.com",
        databaseURL: "https://tg-gis.firebaseio.com",
        storageBucket: "tg-gis.appspot.com",
        messagingSenderId: "686997522597"
    });

    firebase.auth().onAuthStateChanged(function (user) {
        if (user) {
            $('#ux-btn-profile').html('<span class="fa">&#xf007;</span> ' + firebase.auth().currentUser.email).attr('href', '/#/user').removeClass('hidden');
            $('#ux-btn-auth').html('<span class="fa">&#xf08b;</span> Изход').attr('href', '/#/logout');
        } else {
            $('#ux-btn-profile').html('').attr('href', '#').addClass('hidden');
            $('#ux-btn-auth').html('<span class="fa">&#xf090;</span> Вход').attr('href', '/#/auth');

            window.location.href = '#/auth';
        }
    });

    let app = Sammy(container, function () {
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

        this.get('#/project/delete/:id', function (context) {
            projectController.delete(context, container);
        });

        this.get('#/project/add/:name/:id', function (context) {
            projectController.add(context, container);
        });

        this.get('#/logout', function () {
            firebase.auth().signOut();

            this.redirect('#/auth');
        });

        this.notFound = function () {
            mapController.init(container);
        };
    });

    $(function () {
        app.run('#/');
    });
}());