"""Tests for the Bulgarian / English localization.

    python3 -m unittest discover -s tests -v

Strings are written in Bulgarian and translated by looking them up in public/locales/en.js
(frontend) and server/i18n.py (API messages). These tests find every Bulgarian string in the code
and fail if one has no English translation or is shown without going through the translator.
"""
import json
import os
import re
import unittest

from support import ROOT, ServerTestCase

import i18n  # server/i18n.py

PUBLIC = os.path.join(ROOT, 'public')
CYRILLIC = re.compile('[А-Яа-я]')
PLACEHOLDER = re.compile(r'\{(\w+)\}')


def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def js_strings(source):
    """String literals of a JavaScript file, comments and regular expression literals skipped."""
    strings, i, n = [], 0, len(source)
    while i < n:
        c = source[i]
        before = source[:i].rstrip()[-1:]
        if c == '/' and before in tuple('(,=:[!&|?{};') and not source.startswith('//', i) and not source.startswith('/*', i):
            j, in_class = i + 1, False
            while in_class or source[j] != '/':
                if source[j] == '\\':
                    j += 1
                elif source[j] in '[]':
                    in_class = source[j] == '['
                j += 1
            i = j + 1
        elif source.startswith('//', i):
            i = source.find('\n', i)
            i = n if i == -1 else i
        elif source.startswith('/*', i):
            i = source.index('*/', i) + 2
        elif c in '\'"`':
            j, value = i + 1, []
            while source[j] != c:
                if source[j] == '\\':
                    value.append({'n': '\n', 't': '\t'}.get(source[j + 1], source[j + 1]))
                    j += 2
                else:
                    value.append(source[j])
                    j += 1
            strings.append(''.join(value))
            i = j + 1
        else:
            i += 1
    return strings


def app_js_files():
    for folder in ('app', 'controllers', 'helpers', 'services'):
        for name in sorted(os.listdir(os.path.join(PUBLIC, folder))):
            if name.endswith('.js'):
                yield os.path.join(PUBLIC, folder, name)
    yield os.path.join(PUBLIC, 'app.js')


def template_files():
    views = os.path.join(PUBLIC, 'views')
    return [os.path.join(views, name) for name in sorted(os.listdir(views))] + [os.path.join(PUBLIC, 'index.html')]


TEMPLATE_STRING = re.compile(r'\{\{(?:t|count \S+) ("[^"]*")(?: ("[^"]*"))?')
DATA_I18N = re.compile(r'\bdata-i18n(?:-[\w-]+)?="([^"]*)"')


def template_strings(source):
    found = [json.loads(s) for m in TEMPLATE_STRING.finditer(source) for s in m.groups() if s]
    return found + DATA_I18N.findall(source)


def frontend_strings():
    """{Bulgarian string: [files]} for everything the frontend shows."""
    result = {}
    for path in app_js_files():
        if path.endswith('i18n.js'):
            continue
        for s in js_strings(read(path)):
            if CYRILLIC.search(s):
                result.setdefault(s, []).append(os.path.relpath(path, ROOT))
    for path in template_files():
        for s in template_strings(read(path)):
            result.setdefault(s, []).append(os.path.relpath(path, ROOT))
    return result


def frontend_catalog():
    source = read(os.path.join(PUBLIC, 'locales', 'en.js'))
    return json.loads(source[source.index('{'):source.rindex('}') + 1])


SERVER_MSGID = re.compile(r"""\b_\(\s*'((?:[^'\\]|\\.)*)'""")


def server_strings():
    result = {}
    for name in ('app.py', 'cad.py', 'gpx.py'):
        source = read(os.path.join(ROOT, 'server', name))
        for msgid in SERVER_MSGID.findall(source):
            result.setdefault(msgid, []).append('server/' + name)
        # The CAD record messages are chosen from a table.
        for msgid in re.findall(r"^\s+'[PST]': '([^']*)'", source, re.M):
            result.setdefault(msgid, []).append('server/' + name)
    return result


class CatalogTests(unittest.TestCase):

    def assertComplete(self, strings, catalog):
        missing = sorted(s for s in strings if s not in catalog)
        self.assertEqual(missing, [], 'no English translation:\n' + '\n'.join(
            '  {!r}  ({})'.format(s, ', '.join(sorted(set(strings[s])))) for s in missing))
        for s in strings:
            with self.subTest(string=s):
                self.assertEqual(sorted(PLACEHOLDER.findall(s)), sorted(PLACEHOLDER.findall(catalog[s])),
                                 'placeholders differ')
                self.assertFalse(CYRILLIC.search(catalog[s]), 'translation is not English')

    def test_frontend_strings_are_translated(self):
        self.assertComplete(frontend_strings(), frontend_catalog())

    def test_frontend_catalog_has_no_unused_entries(self):
        unused = sorted(set(frontend_catalog()) - set(frontend_strings()))
        self.assertEqual(unused, [])

    def test_server_messages_are_translated(self):
        self.assertComplete(server_strings(), i18n.EN)

    def test_server_catalog_has_no_unused_entries(self):
        self.assertEqual(sorted(set(i18n.EN) - set(server_strings())), [])

    def test_templates_have_no_untranslated_text(self):
        for path in template_files():
            source = read(path)
            # Text inside an element with data-i18n is only the Bulgarian fallback.
            stripped = re.sub(r'data-i18n="[^"]*"[^>]*>[^<]*<', '', source)
            stripped = DATA_I18N.sub('', TEMPLATE_STRING.sub('', stripped))
            for line in stripped.splitlines():
                with self.subTest(file=os.path.relpath(path, ROOT)):
                    self.assertIsNone(CYRILLIC.search(line), line.strip())

    def test_server_messages_go_through_the_translator(self):
        """Bulgarian text in a raise or a warning must be wrapped in _()."""
        for name in ('app.py', 'cad.py', 'gpx.py'):
            for number, line in enumerate(read(os.path.join(ROOT, 'server', name)).splitlines(), 1):
                code = line.split('#')[0]
                if re.search(r'raise |warnings\.append|ApiError\(', code) and CYRILLIC.search(code):
                    with self.subTest(file=name, line=number):
                        self.assertIn('_(', code)


class ServerTranslationTests(unittest.TestCase):

    def test_message_keeps_bulgarian_text(self):
        message = i18n._('Липсва поле: {name}', name='title')
        self.assertEqual(message, 'Липсва поле: title')
        self.assertEqual(i18n.translate(message, 'bg'), 'Липсва поле: title')
        self.assertEqual(i18n.translate(message, 'en'), 'Missing field: title')

    def test_nested_parameters_are_translated(self):
        message = i18n._('Невалидно число „{text}“ ({where}).', text='x', where=i18n._('ред {line}', line=5))
        self.assertEqual(i18n.translate(message, 'en'), 'Invalid number “x” (line 5).')

    def test_language_from_header(self):
        cases = {
            None: 'bg', '': 'bg', 'en': 'en', 'bg': 'bg', 'en-US,en;q=0.9': 'en', 'de-DE, en;q=0.5': 'en',
            'de, fr': 'bg', 'bg;q=0.4, en;q=0.8': 'en', 'en;q=abc, bg': 'bg', 'EN-gb': 'en',
        }
        for header, lang in cases.items():
            with self.subTest(header=header):
                self.assertEqual(i18n.from_header(header), lang)


class ApiLanguageTests(ServerTestCase):

    def test_errors_follow_accept_language(self):
        writer = self.client('writer@test.bg')
        for lang, text in ((None, 'Нямате администраторски права!'), ('bg', 'Нямате администраторски права!'),
                           ('en', 'You do not have administrator rights!')):
            with self.subTest(lang=lang):
                headers = {'Accept-Language': lang} if lang else {}
                r = writer.request('POST', '/api/projects', body={'name': 'Lang-test', 'year': '2024'}, headers=headers)
                self.assertEqual(r.status, 403)
                self.assertEqual(r.json['error'], text)

    def test_wrong_current_password_names_the_field(self):
        r = self.client('reader@test.bg').request('POST', '/api/me/password', headers={'Accept-Language': 'en'},
                                                  body={'currentPassword': 'wrong-password', 'newPassword': 'new-password-1'})
        self.assertEqual(r.status, 400)
        self.assertEqual(r.json, {'error': 'The current password is wrong!', 'field': 'currentPassword'})

    def test_upload_warnings_are_translated(self):
        import base64
        gpx = b'<gpx><wpt lat="99" lon="1"/><wpt lat="42" lon="23"/></gpx>'
        r = self.client('writer@test.bg').request('POST', '/api/projects/p-alpha/layers/gpx', headers={'Accept-Language': 'en'},
                                                  body={'title': 'x.gpx', 'data': base64.b64encode(gpx).decode()})
        self.assertEqual(r.status, 201, r.text)
        self.assertEqual(r.json['warnings'], ['1 point with missing or invalid coordinates was skipped.'])


if __name__ == '__main__':
    unittest.main()
