# YouTube Clone

Клон YouTube на Python (FastAPI) и Vue 3. Весь код написан с помощью ИИ, диалоги и обвязка лежат в
[`docs/prompts/`](docs/prompts/), описание процесса в [`docs/ai-workflow.md`](docs/ai-workflow.md).

Что есть: регистрация и вход, загрузка видео с прогрессом и фоновой обработкой (720p, 360p, превью),
просмотр с лайками и комментариями (с ответами), каналы, подписки, плейлисты, «Смотреть позже»,
история, уведомления, поиск, категории, жалобы, панели модератора и администратора, журнал действий.

## Быстрый старт

Нужна чистая Ubuntu 24.04 (Я тестил через WSL2) и права root:

```bash
git clone <адрес репозитория>
cd youtube-clone
sudo ./install.sh
```

Скрипт ставит Docker (если его нет), создаёт `.env` со случайными секретами, собирает образы,
применяет миграции, создаёт администратора и наполняет базу демо-данными. В конце печатает адрес
приложения и пароль администратора. Приложение открывается на `http://<ip сервера>/`, локально на `http://localhost/`

Скрипт идемпотентный: повторный запуск ничего не ломает и не дублирует данные.

| Параметр | Что делает |
|---|---|
| `--no-seed` | не загружать демо-данные |
| `--port N` | внешний порт вместо 80 |
| `--help` | справка |

## Демо-аккаунты

Пароль у всех демо-пользователей: `DemoPass123`.

| Email | Роль |
|---|---|
| `moderator@example.com` | модератор |
| `alice@example.com` | пользователь (музыка, закрытое видео для друзей) |
| `bob@example.com` | пользователь (подписан на alice и carol, есть уведомления) |
| `carol@example.com` | пользователь |
| `dave@example.com` | пользователь (скрытое модерацией видео) |

Администратор: email и пароль печатаются в конце `install.sh` и хранятся в `.env`
(`ADMIN_EMAIL`, `ADMIN_PASSWORD`).

Демо-данные берутся из видеофайлов в `seed_assets/`. Сид можно запустить отдельно:
`sudo docker compose exec api python -m scripts.seed`.

## Основной сценарий для проверки

1. Зарегистрируйся на `/register`.
2. «Создать» → выбери файл, заполни название, категорию, доступ → дождись обработки.
3. Открой видео: плеер, переключатель 720p/360p, лайк, комментарий и ответ на него.
4. Swagger: `/docs`.

## Разработка (Windows, PowerShell, Docker Desktop)

Всё запускается только в Docker.

```powershell
Copy-Item .env.example .env
Add-Content .env "`nCOMPOSE_FILE=docker-compose.yml;docker-compose.dev.yml"
docker compose up -d --build
docker compose exec api alembic upgrade head
docker compose exec api python -m scripts.create_admin --email admin@example.com --username admin
docker compose exec api python -m scripts.seed
```

| Адрес | Что |
|---|---|
| `http://localhost:5173/` | фронт, dev-сервер Vite (запросы к API идут через nginx) |
| `http://localhost/` | прод-сборка фронта через nginx |
| `http://localhost/docs` | Swagger |
| `localhost:5432` | PostgreSQL для DBeaver |

Тесты (отдельная БД `<имя>_test`, рабочая не затрагивается):

```powershell
docker compose exec api pytest -v
```

Миграции: `docker compose exec api alembic revision --autogenerate -m "..."`, затем `alembic upgrade head`.

Зависимости Python: правишь `backend/requirements.txt`, затем
`docker compose exec api pip install -r requirements.txt`, затем
`docker compose exec api sh -c "pip freeze > requirements.lock.txt"` и пересборка образа
(образ ставит пакеты из `requirements.lock.txt`).

## Настройки (`.env`)

| Переменная | Назначение |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | база (пароль только из букв и цифр) |
| `APP_ENV` | `dev` или `prod`; в `prod` обязателен длинный случайный `SECRET_KEY` |
| `SECRET_KEY` | подпись JWT |
| `COOKIE_SECURE` | `true` только при HTTPS; на сервере по HTTP должно быть `false` |
| `HTTP_PORT` | внешний порт nginx |
| `ADMIN_EMAIL`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` | администратор, создаваемый `install.sh` |
| `ALLOWED_ORIGINS` | дополнительные источники для проверки Origin (обычно пусто) |
| `MAX_UPLOAD_MB` | лимит файла (держать равным `client_max_body_size` в `nginx/nginx.conf`) |
| `JOB_MAX_ATTEMPTS`, `JOB_STALE_SECONDS`, `FFMPEG_STEP_TIMEOUT_SECONDS` | очередь обработки |
| `PENDING_TTL_HOURS` | через сколько часов удаляются записи видео без файла |
| `ACCESS_TOKEN_TTL_MINUTES`, `REFRESH_TOKEN_TTL_DAYS` | время жизни токенов |
| `COMPOSE_PROJECT_NAME` | имя проекта Docker Compose |

## Структура

```
backend/app/        routers → services → repositories → models, core/, policies/, storage/
backend/worker/     фоновая обработка видео (ffmpeg, очередь в PostgreSQL)
backend/scripts/    create_admin, seed
backend/tests/      pytest
frontend/src/       Vue 3: views, components, composables, api, router
nginx/              конфиг, лимиты, заголовки безопасности
seed_assets/        видео для демо-данных
docs/               документация и промпты
install.sh          установка одной командой
```

## Документация

- [Архитектура](docs/architecture.md)
- [База данных и ER-диаграмма](docs/db.md)
- [Безопасность](docs/security.md)
- [Работа с ИИ](docs/prompts/ai-workflow.md)

## Ограничения

Не делались по заданию: рекомендации, live, shorts, монетизация, субтитры, мобильное приложение, HLS.
Приложение работает по HTTP: для публичного использования поставьте перед ним TLS-терминатор
и включите `COOKIE_SECURE=true`. Подробнее об ограничениях в [docs/security.md](docs/security.md).