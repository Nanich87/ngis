'use strict';

// Thin JSON client for the nGIS backend (replaces the Firebase SDK).
let api = (function () {

    function request(method, url, data) {
        let options = {
            method: method,
            credentials: 'same-origin',
            headers: { 'Accept': 'application/json' }
        };

        if (data !== undefined) {
            options.headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(data);
        }

        return fetch(url, options).then(function (response) {
            return response.json().catch(function () {
                return {};
            }).then(function (body) {
                if (!response.ok) {
                    let error = new Error(body.error || ('HTTP ' + response.status));
                    error.status = response.status;

                    throw error;
                }

                return body;
            });
        });
    }

    return {
        get: url => request('GET', url),
        post: (url, data) => request('POST', url, data === undefined ? {} : data),
        patch: (url, data) => request('PATCH', url, data),
        delete: url => request('DELETE', url)
    };
}());
