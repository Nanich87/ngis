'use strict';

let pageHelper = (function () {

    function setActivePage(page) {
        $('#app-navbar .nav-link').removeClass('active').removeAttr('aria-current');
        $('#app-navbar .nav-link[data-id="' + page + '"]').addClass('active').attr('aria-current', 'page');

        // The map page is full-bleed (no container, no footer).
        $('body').toggleClass('page-map', page === 'map');
    }

    return {
        setActivePage: setActivePage
    };
}());
