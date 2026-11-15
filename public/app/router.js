'use strict';

// Minimal hash router (replaces Sammy.js).
//
//   router.get('#/project/view/:name/:id', function (context) { context.params.id ... });
//   router.before(function (context) { ... });   // runs before every route
//   router.notFound(function (context) { ... });
//   router.start('#/');
//
// Handlers receive a context { path, params, redirect(hash) }, also bound as `this`.
let router = (function () {

    let routes = [];
    let beforeHooks = [];
    let notFoundHandler = null;

    function escapeRegExp(text) {
        return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    // '#/project/view/:name/:id' -> { regex, keys: ['name', 'id'] }
    function compile(pattern) {
        let keys = [];
        let source = pattern.replace(/^#/, '').split('/').map(function (segment) {
            if (segment.charAt(0) === ':') {
                keys.push(segment.slice(1));

                return '([^/]+)';
            }

            return escapeRegExp(segment);
        }).join('/');

        return { regex: new RegExp('^' + source + '/?$'), keys: keys };
    }

    function decode(value) {
        try {
            return decodeURIComponent(value);
        } catch (e) {
            return value;   // malformed %-escape: keep it as typed
        }
    }

    function currentPath() {
        // '#/map/abc?x=1' -> '/map/abc'
        return (window.location.hash.slice(1) || '/').split('?')[0];
    }

    // Replaces the current history entry (so "Back" skips routes that only redirect).
    function redirect(hash) {
        if (window.location.hash === hash) {
            dispatch();
        } else {
            window.location.replace(hash);   // fires hashchange -> dispatch
        }
    }

    function dispatch() {
        let path = currentPath();
        let context = { path: path, params: {}, redirect: redirect };

        for (let i = 0; i < routes.length; i++) {
            let match = routes[i].regex.exec(path);

            if (match) {
                routes[i].keys.forEach(function (key, index) {
                    context.params[key] = decode(match[index + 1]);
                });

                beforeHooks.forEach(hook => hook.call(context, context));
                routes[i].handler.call(context, context);

                return;
            }
        }

        beforeHooks.forEach(hook => hook.call(context, context));

        if (notFoundHandler) {
            notFoundHandler.call(context, context);
        }
    }

    function start(defaultHash) {
        window.addEventListener('hashchange', dispatch);

        if (!window.location.hash || window.location.hash === '#') {
            // Replace instead of push, so "Back" does not return to the bare URL.
            window.history.replaceState(null, '', defaultHash);
        }

        dispatch();
    }

    return {
        get: function (pattern, handler) {
            routes.push(Object.assign(compile(pattern), { handler: handler }));
        },
        before: function (hook) {
            beforeHooks.push(hook);
        },
        notFound: function (handler) {
            notFoundHandler = handler;
        },
        redirect: redirect,
        start: start
    };
}());
