'use strict';

// Sammy 0.7.6 (the last release) still calls helpers that jQuery 4 removed.
// Restore only those two, using the native equivalents.
(function ($) {
    if (typeof $.trim !== 'function') {
        $.trim = function (text) {
            return text == null ? '' : String(text).trim();
        };
    }

    if (typeof $.parseJSON !== 'function') {
        $.parseJSON = JSON.parse;
    }
}(jQuery));
