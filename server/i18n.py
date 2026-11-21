"""Translation of the messages the API returns to the user (errors and upload warnings).

Messages are written in Bulgarian and wrapped in _(), which keeps the Bulgarian text and its
parameters so they can be rendered again in the language of the request:

    raise ApiError(HTTPStatus.BAD_REQUEST, _('Липсва поле: {name}', name=name))

_() returns a Message, a str subclass holding the Bulgarian rendering, so code and tests that
treat messages as plain strings keep working. The frontend asks for a language with the
Accept-Language header; Bulgarian is the default.
"""

LANGUAGES = ('bg', 'en')
DEFAULT = 'bg'


class Message(str):
    """Bulgarian text of a message, plus what is needed to translate it."""

    def __new__(cls, msgid, params):
        self = super().__new__(cls, msgid.format(**params) if params else msgid)
        self.msgid = msgid
        self.params = params
        return self


def _(msgid, **params):
    return Message(msgid, params)


def translate(text, lang):
    """A Message (or a plain catalog string) in the given language; other text is returned as is."""
    if lang == DEFAULT or not isinstance(text, str):
        return text
    catalog = CATALOGS.get(lang, {})
    if isinstance(text, Message):
        params = {k: translate(v, lang) for k, v in text.params.items()}
        return catalog.get(text.msgid, text.msgid).format(**params) if params else catalog.get(text.msgid, text.msgid)
    return catalog.get(text, text)


def from_header(value):
    """Language from an Accept-Language header: the first supported one, in order of preference."""
    choices = []
    for index, part in enumerate((value or '').split(',')):
        tag, _sep, rest = part.strip().partition(';')
        quality = 1.0
        if rest.strip().startswith('q='):
            try:
                quality = float(rest.strip()[2:])
            except ValueError:
                quality = 0.0
        choices.append((-quality, index, tag.strip().lower().split('-')[0]))
    for _q, _i, lang in sorted(choices):
        if lang in LANGUAGES:
            return lang
    return DEFAULT


EN = {
    # app.py: requests, sessions and rights
    'Твърде много неуспешни опити. Опитайте отново след {minutes} мин.':
        'Too many failed attempts. Try again in {minutes} min.',
    'Не сте влезли в системата!': 'You are not signed in!',
    'Нямате права за четене!': 'You do not have read access!',
    'Нямате права за запис!': 'You do not have write access!',
    'Нямате администраторски права!': 'You do not have administrator rights!',
    'Липсва поле: {name}': 'Missing field: {name}',
    'Невалидна стойност: {name}': 'Invalid value: {name}',
    'Твърде дълга стойност: {name}': 'Value too long: {name}',
    'Грешен Email адрес или парола!': 'Wrong email address or password!',
    'Адресът на снимката трябва да започва с http:// или https://':
        'The photo address must start with http:// or https://',
    'Текущата парола е грешна!': 'The current password is wrong!',
    'Новата парола трябва да е поне {min} символа!': 'The new password must be at least {min} characters long!',
    'Новата парола съвпада с текущата!': 'The new password is the same as the current one!',
    'Няма такъв потребител!': 'No such user!',
    'Правата трябва да са true или false!': 'Rights must be true or false!',
    'Невалиден Email адрес!': 'Invalid email address!',
    'Вече съществува потребител с този Email адрес!': 'A user with this email address already exists!',
    'Не можете да изтриете собствения си акаунт!': 'You cannot delete your own account!',
    'Няма промени!': 'Nothing to change!',
    'Не можете да премахнете собствените си администраторски права!':
        'You cannot remove your own administrator rights!',
    'Няма такъв обект!': 'No such project!',
    'Невалидно име на обект!': 'Invalid project name!',
    'Невалидна година!': 'Invalid year!',
    'Файлът не е валиден GeoJSON!': 'The file is not valid GeoJSON!',
    'Няма такъв файл!': 'No such file!',
    'Вътрешна грешка на сървъра!': 'Internal server error!',
    'Очаква се application/json': 'application/json expected',
    'Невалиден Content-Length': 'Invalid Content-Length',
    'Файлът е твърде голям!': 'The file is too large!',
    'Невалиден JSON': 'Invalid JSON',

    # cad.py
    'МИК': 'MIK',
    'Невалидно число „{text}“ ({where}).': 'Invalid number “{text}” ({where}).',
    'ред {line}': 'line {line}',
    'площ на {contour}': 'area of {contour}',
    'Невалиден запис за линия на ред {line}.': 'Invalid line record on line {line}.',
    'Файлът съдържа твърде много точки.': 'The file contains too many points.',
    'Невалиден запис за контур на ред {line}.': 'Invalid contour record on line {line}.',
    'Файлът не е във формат CAD (липсва HEADER).': 'The file is not in CAD format (HEADER is missing).',
    'Във файла липсва координатна система (COORDTYPE).': 'The file has no coordinate system (COORDTYPE).',
    'Координатна система „{system}“ не се поддържа. Поддържа се само БГС2005 (COORDTYPE 2005).':
        'Coordinate system “{system}” is not supported. Only BGS2005 (COORDTYPE 2005) is supported.',
    'Невалиден REFERENCE в заглавната част.': 'Invalid REFERENCE in the header.',
    '{count} контура в слой {layer} не могат да бъдат затворени и са пропуснати: {list}':
        '{count} contours in layer {layer} cannot be closed and were skipped: {list}',
    '{count} контура в слой {layer} се различават от официалната площ: {list}':
        '{count} contours in layer {layer} differ from the official area: {list}',
    'Пропуснати точки: {count} (още не се поддържат).': 'Skipped points: {count} (not supported yet).',
    'Пропуснати символи: {count} (още не се поддържат).': 'Skipped symbols: {count} (not supported yet).',
    'Пропуснати текстове: {count} (още не се поддържат).': 'Skipped texts: {count} (not supported yet).',
    'Пропуснати записи „{record}“: {count} (още не се поддържат).':
        'Skipped “{record}” records: {count} (not supported yet).',
    'Таблиците с атрибути (TABLE) още не се поддържат.': 'Attribute tables (TABLE) are not supported yet.',
    'Във файла няма контури, които да могат да бъдат показани.': 'The file has no contours that can be shown.',

    # gpx.py
    'Файлът е празен.': 'The file is empty.',
    'GPX файлът съдържа DOCTYPE декларация, която не се поддържа.':
        'The GPX file contains a DOCTYPE declaration, which is not supported.',
    'Файлът не е валиден XML ({error}).': 'The file is not valid XML ({error}).',
    'Файлът не е валиден XML.': 'The file is not valid XML.',
    'Файлът не е GPX (основният елемент трябва да е <gpx>).': 'The file is not GPX (the root element must be <gpx>).',
    'Файлът има повече от {max} точки.': 'The file has more than {max} points.',
    'Трасето „{name}“ няма сегмент с поне 2 точки и е пропуснато.':
        'Track “{name}” has no segment with at least 2 points and was skipped.',
    'Маршрутът „{name}“ има по-малко от 2 точки и е пропуснат.':
        'Route “{name}” has fewer than 2 points and was skipped.',
    'Пропусната е 1 точка с липсващи или невалидни координати.':
        '1 point with missing or invalid coordinates was skipped.',
    'Пропуснати са {count} точки с липсващи или невалидни координати.':
        '{count} points with missing or invalid coordinates were skipped.',
    'Файлът не съдържа точки, маршрути или трасета.': 'The file contains no waypoints, routes or tracks.',
}

CATALOGS = {'en': EN}
