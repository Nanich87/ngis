var templates = function () {
    var handlebars = window.handlebars || window.Handlebars,
        Handlebars = window.handlebars || window.Handlebars,
        cache = {};

    handlebars.registerHelper('bytes', value => pageHelper.formatBytes(value));
    handlebars.registerHelper('count', (value, one, many) => pageHelper.formatCount(value, one, many));
    // {{t "Текст с {name}" name=value}}; the result is escaped by Handlebars like any other value.
    handlebars.registerHelper('t', (text, options) => i18n.t(text, options.hash));
    handlebars.registerHelper('date', value => pageHelper.formatDate(value));
    handlebars.registerHelper('slug', value => pageHelper.slug(value));

    function get(name) {
        var promise = new Promise(function (resolve, reject) {
            if (cache[name]) {
                resolve(cache[name]);
                return;
            }

            var url = './views/' + name + '.handlebars';
            $.get(url, function (html) {
                var template = handlebars.compile(html);
                cache[name] = template;
                resolve(template);
            });
        });
        return promise;
    }

    return {
        get: get
    };
}();
