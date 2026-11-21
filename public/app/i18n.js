'use strict';

// User interface language. Strings are written in Bulgarian in the code and the templates and are
// looked up by that text in the catalog of the current language (gettext style); Bulgarian needs
// no catalog. Missing translations fall back to the Bulgarian text.
//
//   i18n.t('Файлът „{name}“ беше изтрит.', { name: file.title })
//
// A word with two meanings gets a context before "|": 'право|Запис' (the right to write, "Write")
// and 'Запис' (the button, "Save"); the context is not shown.
//
// Catalogs are registered by public/locales/<lang>.js, loaded right after this file.
let i18n = (function () {

    const LANGUAGES = [
        { code: 'bg', label: 'BG', name: 'Български', locale: 'bg-BG', dateFormat: 'DD.MM.YYYY' },
        { code: 'en', label: 'EN', name: 'English', locale: 'en-GB', dateFormat: 'D MMM YYYY' }
    ];
    const DEFAULT = 'bg';
    const STORAGE_KEY = 'ngis.lang';

    let catalogs = {};
    let current = LANGUAGES.find(l => l.code === load()) || LANGUAGES.find(l => l.code === DEFAULT);

    function load() {
        try {
            return window.localStorage.getItem(STORAGE_KEY) || DEFAULT;
        } catch (e) {
            return DEFAULT;
        }
    }

    function register(code, catalog) {
        catalogs[code] = catalog;
    }

    function format(text, params) {
        if (!params) {
            return text;
        }

        return text.replace(/\{(\w+)\}/g, (match, key) => Object.prototype.hasOwnProperty.call(params, key) ? String(params[key]) : match);
    }

    function t(text, params) {
        let catalog = catalogs[current.code];
        let translated = catalog && Object.prototype.hasOwnProperty.call(catalog, text)
            ? catalog[text]
            : text.slice(text.indexOf('|') + 1);

        return format(translated, params);
    }

    // Saves the choice and reloads, so that every page, the map and cached templates are rebuilt.
    function setLanguage(code) {
        if (code === current.code || !LANGUAGES.some(l => l.code === code)) {
            return;
        }

        try {
            window.localStorage.setItem(STORAGE_KEY, code);
        } catch (e) { }

        window.location.reload();
    }

    // Static markup (index.html): data-i18n translates the text, data-i18n-<attribute> an attribute.
    function translateDom(root) {
        $(root).find('*').each(function () {
            let element = this;

            Array.from(element.attributes).forEach(function (attribute) {
                if (attribute.name === 'data-i18n') {
                    element.textContent = t(attribute.value);
                } else if (attribute.name.indexOf('data-i18n-') === 0) {
                    element.setAttribute(attribute.name.slice('data-i18n-'.length), t(attribute.value));
                }
            });
        });
    }

    document.documentElement.lang = current.code;

    return {
        LANGUAGES: LANGUAGES,
        get lang() { return current.code; },
        get locale() { return current.locale; },
        get dateFormat() { return current.dateFormat; },
        register: register,
        t: t,
        setLanguage: setLanguage,
        translateDom: translateDom
    };
}());
