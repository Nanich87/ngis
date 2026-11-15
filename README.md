# nGIS

nGIS е малка уеб ГИС система за управление на данни от проучване и проектиране, организирани по
обекти. Всеки обект съдържа GeoJSON файлове: оси на пътища, сгради, граници на имоти, надлези и
подлези на железопътни линии и други слоеве. Те се разглеждат на интерактивна карта, може да се
преглеждат атрибутите им и да се управлява кой има право да ги чете и променя.

Интерфейсът е на български, а приложението поддържа използваните в България координатни системи
(BGS2005, UTM, ETRS89), както и WGS84 и Web Mercator.

## Функционалност

- **Карта:** карта на цял екран с подложки OpenStreetMap, сателитна и хибридна и странично меню с
  всички обекти и файлове:
  - включване и изключване на слоеве и приближаване до обект или файл;
  - легенда само с типовете геообекти, които се виждат в момента;
  - при клик върху геообект изскача прозорец с всичките му атрибути.
- **Обекти:** списък с търсене, година и брой файлове. Администраторите създават обекти (с проверка
  на въведеното директно във формата) и ги изтриват (след потвърждение).
- **Страница на обект:** файлове с брой геообекти, размер и дата на качване. Може да се качват
  няколко GeoJSON файла наведнъж чрез влачене или избор от компютъра, с резултат за всеки файл.
- **Страница на файл:** карта за преглед с легенда на съдържанието и таблица с атрибути с филтър.
  Клик върху ред приближава картата до съответния геообект. Показва се и разпознатата координатна
  система, файлът може да се изтегли, а GeoJSON кодът може да се види.
- **Координатни системи:** файловете се преобразуват към проекцията на картата в браузъра (вижте
  [Координатни системи](#координатни-системи)).
- **Потребители:** няма свободна регистрация. Акаунтите се създават от администратор в страницата
  „Потребители“: системата генерира временна парола, която се показва веднъж. Оттам се генерира и
  нова парола при забравена, изтрива се акаунт и се дават права за четене, запис и админ. Всеки
  потребител има профил с име, URL на снимка и смяна на парола.

### Роли

| Роля | Може |
|---|---|
| Без права | Да влезе и да види профила си. Администраторът избира правата при създаване на акаунта и може да ги сменя по всяко време. |
| Четене | Да разглежда обекти, файлове и картата |
| Запис | Всичко от „Четене“, плюс качване и изтриване на файлове |
| Админ | Всичко, плюс създаване и изтриване на обекти и управление на потребителите |

## Технологии

### Фронтенд

Едностранично приложение (SPA) от статични файлове в `public/`, без стъпка за компилиране.

| Библиотека | Версия | За какво се използва |
|---|---|---|
| [OpenLayers](https://openlayers.org/) | 10.11.0 | Изобразяване на картата, четене на GeoJSON, стилове, изскачащи прозорци |
| [proj4js](https://proj4js.org/) | 2.22.0 | Преобразуване на данни в BGS2005 / UTM / ETRS89 |
| [Bootstrap](https://getbootstrap.com/) + [Bootswatch Cyborg](https://bootswatch.com/cyborg/) | 5.3.3 | Оформление, компоненти, тъмна тема |
| [jQuery](https://jquery.com/) | 4.0.0 | Работа с DOM и събития |
| [Handlebars](https://handlebarsjs.com/) | 4.7.10 | HTML шаблони в `public/views/` |
| [toastr](https://github.com/CodeSeven/toastr) | 2.1.4 | Известия |
| [Moment.js](https://momentjs.com/) | 2.31.0 | Форматиране на дати |
| [Font Awesome](https://fontawesome.com/v4/) | 4.7.0 | Икони |
| [Roboto](https://fontsource.org/fonts/roboto) (@fontsource/roboto) | 5.3.0 | Шрифт на темата (латиница и кирилица, 400 и 700) |

Всички библиотеки, стилове и шрифтове са локални, в `public/libs/` (по една папка за библиотека, с
версията в името), така че сайтът не зависи от външни CDN-и. Всеки файл е свален от cdnjs и
проверен срещу публикувания там SRI хеш. Шрифтът е проверен срещу хеша на npm пакета. Единствената
промяна в тях: от темата Bootswatch е махнат `@import` към Google Fonts, защото Roboto се зарежда от
`libs/roboto-5.3.0/roboto.css`.

Маршрутизацията по адреса след `#` (`#/map`, `#/projects`, …) е собствена, в
`public/app/router.js`. Ползва събитието `hashchange` на браузъра.

Подложките са от [OpenStreetMap](https://www.openstreetmap.org/) и
[Esri World Imagery](https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9). Това
е единственото, което се зарежда от интернет. Без връзка интерфейсът и слоевете работят, но
подложката не се вижда.

### Бекенд

- **Python 3** (3.8+), само стандартната библиотека: `http.server` сервира статичните файлове и
  JSON API.
- **SQLite** (`sqlite3`, режим WAL) пази потребителите, сесиите, обектите и файловете. GeoJSON се
  съхранява като текст.
- **Удостоверяване:** паролите се пазят като PBKDF2-SHA256 хешове, а сесиите са в бисквитка с
  `HttpOnly` и `SameSite=Lax`.

Първоначално приложението работеше на Firebase (Realtime Database, Auth и Hosting). Вижте
[Миграция от Firebase](#миграция-от-firebase).

## Структура на проекта

```
public/                  Фронтенд (сервира се както е)
  index.html             Основна страница, навигация, включване на скриптовете
  app.js                 Маршрути и състояние на навигацията
  app/router.js          Маршрутизатор по адреса след # (hashchange)
  app/api.js             Обвивка около fetch за JSON API
  app/map.js             Карта (OpenLayers), стилове, легенда, проекции
  app/templates.js       Зареждане на Handlebars шаблоните и помощни функции
  controllers/           По един контролер за всяка страница
  services/              Заявки към API (вход, обекти, потребители)
  helpers/               Помощни функции (прозорец за потвърждение, форматиране)
  views/                 Handlebars / HTML шаблони
  css/app.css            Стилове на приложението върху Bootstrap
  samples/               Примерен GeoJSON за тестване
server/
  app.py                 HTTP сървър и JSON API
  db.py                  Връзка със SQLite, хеширане на пароли
  schema.sql             Схема на базата данни
  manage.py              Администриране от командния ред, резервни копия, импорт от Firebase
deploy/
  nginx/                 Конфигурация за nginx (HTTPS reverse proxy)
  systemd/               Услуга за сървъра и таймер за резервните копия
tests/                   Тестове за сигурност (API и браузър)
data/ngis.db             База данни (създава се при първо пускане, не е в git)
```

## Пускане

```bash
python3 server/manage.py init
python3 server/manage.py create-user admin@example.com --admin
python3 server/app.py --port 8000          # http://127.0.0.1:8000
```

С `--host 0.0.0.0` (или конкретен адрес) сървърът става достъпен и от други компютри.

| Променлива на средата | Значение |
|---|---|
| `NGIS_DB` | Път до базата данни SQLite (по подразбиране `data/ngis.db`) |
| `NGIS_SECURE_COOKIE=1` | Сесийната бисквитка се маркира като `Secure`. Задайте я, когато сайтът се сервира през HTTPS зад reverse proxy. |
| `NGIS_TRUSTED_PROXIES` | IP адреси на reverse proxy-та (със запетая), от които се вярва на `X-Forwarded-For`, например `127.0.0.1`. Без тях се ползва адресът на самата връзка. |
| `NGIS_BACKUP_DIR` | Папка за резервните копия (по подразбиране `data/backups`). |
| `NGIS_FRAME_ANCESTORS` | Кои сайтове могат да вграждат nGIS в рамка (CSP `frame-ancestors`). По подразбиране `'none'`, тоест никой. |
| `NGIS_CSP_REPORT_URI` | Адрес, на който браузърите да докладват нарушения на Content-Security-Policy (по избор). |
| `NGIS_CSP` | Заменя изцяло Content-Security-Policy. Ползва се само за тестове или специални случаи. |

### Команди за управление

```bash
python3 server/manage.py init                                  # създава базата данни
python3 server/manage.py create-user EMAIL [--admin] [--read] [--write]
python3 server/manage.py set-password EMAIL
python3 server/manage.py import-firebase EXPORT.json [--auth USERS.json]
python3 server/manage.py backup [--dir DIR] [--keep 14]          # резервно копие
```

Паролите, които потребителите избират, трябва да са поне 10 символа. Първият администратор се
създава с `create-user --admin`, а следващите потребители се създават от страницата „Потребители“.

## Резервни копия

`manage.py backup` прави консистентно копие на базата и докато сървърът работи (с вградения backup
API на SQLite), проверява го с `PRAGMA integrity_check`, компресира го (`ngis-ДАТА-ЧАС.db.gz`) и
пази последните N копия.

Възстановяване:

```bash
sudo systemctl stop ngis
gunzip -c /home/h4x0r/ngis-backups/ngis-20261115-033000.db.gz > data/ngis.db
rm -f data/ngis.db-wal data/ngis.db-shm
sudo systemctl start ngis
```

Ежедневно копие в 03:30 с systemd таймер:

```bash
sudo cp deploy/systemd/ngis-backup.service deploy/systemd/ngis-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ngis-backup.timer
systemctl list-timers ngis-backup.timer        # кога е следващото
```

Копията трябва да са на друг диск (или да се синхронизират другаде). Сменете `NGIS_BACKUP_DIR` в
`ngis-backup.service`, ако е нужно.

## Внедряване в интернет

Сървърът слуша само на `127.0.0.1`, а nginx отпред поема HTTPS. Примерът е за домейн
`gis.example.com`, заменете го с вашия.

1. **DNS и рутер:** A запис за домейна към публичния ви IP, а в рутера пренасочване на портове 80 и
   443 към тази машина.
2. **nginx и certbot:**
   ```bash
   sudo apt install nginx certbot python3-certbot-nginx
   sudo cp deploy/nginx/ngis.conf /etc/nginx/sites-available/ngis
   sudo sed -i 's/gis.example.com/ВАШИЯТ.ДОМЕЙН/' /etc/nginx/sites-available/ngis
   sudo ln -s /etc/nginx/sites-available/ngis /etc/nginx/sites-enabled/ngis
   sudo nginx -t && sudo systemctl reload nginx
   sudo certbot --nginx -d ВАШИЯТ.ДОМЕЙН --redirect --hsts
   ```
   certbot взема сертификат от Let's Encrypt, добавя HTTPS, пренасочването от HTTP и HSTS, и сам
   подновява сертификата.
3. **Услугата:** `deploy/systemd/ngis.service` е вариантът за продукция. Слуша на `127.0.0.1`, с
   `NGIS_SECURE_COOKIE=1` и `NGIS_TRUSTED_PROXIES=127.0.0.1`.
   ```bash
   sudo cp deploy/systemd/ngis.service /etc/systemd/system/ngis.service
   sudo systemctl daemon-reload && sudo systemctl restart ngis
   ```
4. **Защитна стена:** отворени трябва да са само 80 и 443 (например
   `sudo ufw allow 'Nginx Full'`). Порт 8000 не трябва да е достъпен отвън.

nginx презаписва `X-Forwarded-For` с адреса на клиента, а приложението вярва на тази заглавка само
от `NGIS_TRUSTED_PROXIES`. Така ограничението на опитите за вход работи по истинския IP и не може да
се заобиколи с подправена заглавка. nginx добавя и свое ограничение: 10 опита за вход в минута от
IP.

Проверка след внедряването:

```bash
curl -sI http://ВАШИЯТ.ДОМЕЙН/  | grep -iE "^HTTP|^location"        # 301 към https://
curl -sI https://ВАШИЯТ.ДОМЕЙН/ | grep -iE "^HTTP|^strict|^content-security"
```

Ако липсва `Strict-Transport-Security` (certbot е пуснат без `--hsts`), добавете в `server` блока
за 443:

```nginx
add_header Strict-Transport-Security "max-age=31536000" always;
```

### Вариант: nginx на друга машина през VPN

Ако nginx е на отделен сървър (например VPS с публичен IP), а приложението е на машина без публичен
адрес, двете се свързват през VPN, например WireGuard. Трафикът между тях минава през криптирания
тунел. В примера VPS-ът е `10.8.0.1`, а машината с nGIS е `10.8.0.2`.

1. **DNS:** A запис за домейна към публичния IP на VPS-а. Пренасочване на портове в домашния рутер
   не е нужно.
2. **nginx на VPS-а:** същият `deploy/nginx/ngis.conf`, но с VPN адреса на приложението и в двата
   `location` блока:
   ```nginx
   proxy_pass http://10.8.0.2:8000;
   ```
   Проверете от VPS-а, че приложението се вижда: `curl -sI http://10.8.0.2:8000/` (трябва да върне
   `Server: nGIS`).
3. **Услугата на машината с nGIS:** в `deploy/systemd/ngis.service` сменете три неща.
   - Сървърът слуша на VPN адреса. Така не се вижда нито от локалната мрежа, нито от интернет:
     ```ini
     ExecStart=/usr/bin/python3 /home/h4x0r/ngis/server/app.py --host 10.8.0.2 --port 8000
     ```
   - Доверява се на `X-Forwarded-For` от адреса, от който nginx се свързва, тоест VPN адреса на
     VPS-а:
     ```ini
     Environment=NGIS_TRUSTED_PROXIES=10.8.0.1
     ```
   - Тръгва след VPN-а, защото без него адресът не съществува. Ако все пак тръгне по-рано,
     `Restart=on-failure` го опитва отново на всеки 5 секунди:
     ```ini
     After=network-online.target wg-quick@wg0.service
     Wants=network-online.target wg-quick@wg0.service
     ```
4. **Защитна стена на машината с nGIS:** другите участници във VPN мрежата също могат да стигнат до
   порт 8000. Ограничете го само до VPS-а:
   ```bash
   sudo ufw allow in on wg0 from 10.8.0.1 to any port 8000 proto tcp
   sudo ufw deny in on wg0 to any port 8000 proto tcp
   ```

Ако на VPS-а има и други сайтове, нов поддомейн без собствен HTTPS блок ще отвори сайта, който
nginx ползва по подразбиране за порт 443, с чужд сертификат. Пуснете certbot за домейна веднага
след като добавите конфигурацията. За да не става това изобщо, може да се добави сървър по
подразбиране, който отказва непознати домейни. Пример за nginx 1.18 (изисква пакета `ssl-cert`; от
nginx 1.19.4 вместо сертификата може да се ползва `ssl_reject_handshake on;`):

```nginx
server {
    listen 443 ssl default_server;
    listen [::]:443 ssl default_server;
    server_name _;
    ssl_certificate     /etc/ssl/certs/ssl-cert-snakeoil.pem;
    ssl_certificate_key /etc/ssl/private/ssl-cert-snakeoil.key;
    return 444;
}
```

## API

Всички endpoint-и са под `/api`, приемат и връщат JSON и разпознават потребителя по сесийната
бисквитка.

| Метод | Път | Достъп |
|---|---|---|
| `POST` | `/api/auth/login`, `/api/auth/logout` | всеки |
| `GET`, `PATCH` | `/api/me` | влязъл потребител |
| `POST` | `/api/me/password` | влязъл потребител |
| `GET` | `/api/projects`, `/api/projects/:id` | четене |
| `POST` | `/api/projects` | админ |
| `DELETE` | `/api/projects/:id` | админ |
| `GET` | `/api/projects/:id/layers`, `/api/projects/:id/layers/:layerId` | четене |
| `POST` | `/api/projects/:id/layers` | запис |
| `DELETE` | `/api/projects/:id/layers/:layerId` | запис |
| `GET`, `POST` | `/api/admin/users` (списък, нов потребител с генерирана парола) | админ |
| `PATCH`, `DELETE` | `/api/admin/users/:uid` (права, изтриване) | админ |
| `POST` | `/api/admin/users/:uid/password` (нова генерирана парола) | админ |

## Координатни системи

Каченият GeoJSON се преобразува в браузъра с proj4js към проекцията на картата (Web Mercator).
Поддържат се:

- WGS84 (EPSG:4326 / CRS84) и Web Mercator (EPSG:3857), които се разпознават автоматично
- BGS2005 / CCS2005 (EPSG:7801), BGS2005 / UTM 34N, 35N, 36N (EPSG:7803–7805)
- WGS84 / UTM 34N, 35N (EPSG:32634, 32635), ETRS89 / UTM 34N, 35N (EPSG:25834, 25835)
- ETRS89 (EPSG:4258), ETRS89 / LAEA Europe (EPSG:3035)

Проекциите, различни от Web Mercator, трябва да са обявени в полето `crs` на файла. QGIS и GDAL го
добавят при експорт. Координатите се четат в реда изток, север.

EPSG:7804 се ползва с UTM зона 35. Регистърът на EPSG го свързва с преобразуването за зона 34, което
противоречи на името и на областта му на приложение.

## Сигурност и тестове

```bash
python3 -m unittest discover -s tests -v
```

Тестовете стартират сървъра с временна база данни и не засягат `data/ngis.db`.

- **`tests/test_security_api.py`** проверява:
  - SQL инжекции във всички полета, адреси и сесийната бисквитка;
  - удостоверяване и сесии, права по роли и достъп до чужди данни (IDOR);
  - управление на потребители (само от админ) и работа зад reverse proxy;
  - CSRF, валидация на входа и злоупотреби с HTTP заглавки;
  - path traversal и защитните HTTP заглавки.
- **`tests/test_security_browser.py`** работи в headless Firefox и се пропуска, ако Firefox не е
  инсталиран. Прави две проверки:
  - отваря всички страници с XSS payload-и във всяко показвано поле и засича дали някой се изпълнява;
  - отваря всички страници под истинската Content-Security-Policy и изисква нула нарушения.

Основни защити:

- **SQL:** всички заявки към базата са параметризирани.
- **Акаунти:** няма свободна регистрация. Акаунтите се създават от администратор, с генерирана
  парола (около 96 бита случайност). Паролите, избрани от потребителите, са поне 10 символа.
- **Вход:** 10 грешни опита за email + IP (или 50 от един IP) заключват входа за 15 минути (HTTP
  429). Същото важи за грешна текуща парола при смяна. Броячите са в паметта на процеса. Зад
  reverse proxy се ползва истинският IP от `X-Forwarded-For` (вижте `NGIS_TRUSTED_PROXIES`).
- **Изброяване на акаунти:** входът отнема еднакво време при несъществуващ email и при грешна
  парола.
- **Валидация:** всички полета имат проверка на типа и дължината. URL-ите на снимки трябва да са
  `http(s)`, а файловете трябва да са GeoJSON.
- **CSRF:** API приема само `application/json`, а бисквитката е `HttpOnly` и `SameSite=Lax`.
- **Content-Security-Policy:** скриптове, стилове и шрифтове се зареждат само от самия сайт
  (`'self'`), без `'unsafe-inline'`, така че вмъкнат HTML не може да изпълни код. `'unsafe-eval'` е
  разрешен, защото Handlebars компилира шаблоните в браузъра. Заявките (`connect-src`) са само към сайта,
  `object-src` е `'none'`, а вграждането в рамка е забранено.
- **HTTP заглавки:** `X-Content-Type-Options`, `X-Frame-Options` и `Referrer-Policy`. Листингът на
  директории е изключен и заглавката `Server` не издава версии.
- **Връзки:** при 30 секунди без активност връзката се затваря, а невалиден `Content-Length` се
  отказва.
- **Страници:** защитените страници се показват само след като е потвърдено, че потребителят е
  влязъл.

## Миграция от Firebase

1. Експортирайте Realtime Database: Firebase console → Realtime Database → ⋮ → *Export JSON*.
2. Експортирайте потребителите: `firebase auth:export users.json --format=json --project tg-gis`.
3. Импортирайте: `python3 server/manage.py import-firebase tg-gis-export.json --auth users.json`
4. Паролите от Firebase не могат да се пренесат, затова задайте нови с
   `python3 server/manage.py set-password EMAIL`.

Идентификаторите на обекти, файлове и потребители се запазват, така че старите линкове продължават
да работят.

## Предстои

- Функционални тестове на интерфейса
- Поддръжка на Координатна система 1970 (няма EPSG код)

## Лиценз

Code by Nanko Geshkov. Copyright 2017 Nanko Geshkov [https://gnnmobile.eu](https://gnnmobile.eu)

## Въпроси, коментари или предложения?

Ако имате предложение за нова функционалност или сте открили грешка, оставете issue на
[страницата с issues](https://github.com/Nanich87/ngis/issues) или изпратете
[pull request](https://github.com/Nanich87/ngis/pulls).
