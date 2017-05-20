'use strict';

let pageHelper = (function () {

    function setActivePage(page) {
        $('.nav').find('li.active').removeClass('active');
        $('.nav li[data-id="' + page + '"]').addClass('active');
    }

    return {
        setActivePage: setActivePage
    };
}());