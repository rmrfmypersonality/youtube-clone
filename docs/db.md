# База данных

PostgreSQL 16, расширения `citext` (регистронезависимые email, username и handle) и `pg_trgm`
(поиск по названию). Схема создаётся миграциями Alembic (`backend/migrations/versions/`).

## ER-диаграмма

```mermaid
erDiagram
    users ||--|| channels : "владеет"
    users ||--o{ refresh_tokens : "сессии"
    users ||--o{ videos : "загружает"
    categories ||--o{ videos : "категория"
    videos ||--o{ jobs : "обработка"
    videos ||--o{ video_shares : "доступ"
    users ||--o{ video_shares : "получает доступ"
    users ||--o{ likes : "ставит"
    videos ||--o{ likes : "получает"
    videos ||--o{ comments : "под видео"
    users ||--o{ comments : "пишет"
    comments ||--o{ comments : "ответ"
    users ||--o{ subscriptions : "подписчик"
    channels ||--o{ subscriptions : "на канал"
    users ||--o{ playlists : "владеет"
    playlists ||--o{ playlist_items : "содержит"
    videos ||--o{ playlist_items : "входит"
    users ||--o{ watch_history : "смотрел"
    videos ||--o{ watch_history : "просмотрено"
    users ||--o{ reports : "автор жалобы"
    users |o--o{ reports : "обработал"
    videos |o--o{ reports : "цель"
    comments |o--o{ reports : "цель"
    users |o--o{ audit_log : "действие"

    users {
        int id PK
        citext email UK
        citext username UK
        string password_hash
        string role
        bool is_active
        datetime notifications_seen_at
        datetime created_at
    }
    channels {
        int id PK
        int owner_id FK
        citext handle UK
        string name
        string description
        string avatar_path
        bool is_hidden
        datetime created_at
    }
    refresh_tokens {
        int id PK
        int user_id FK
        uuid family_id
        string token_hash UK
        datetime expires_at
        datetime revoked_at
    }
    categories {
        int id PK
        string slug UK
        string name
        int sort_order
    }
    videos {
        int id PK
        int owner_id FK
        int category_id FK
        string title
        string description
        string status
        string visibility
        bool hidden_by_moderation
        string original_path
        string path_720
        string path_360
        string thumbnail_path
        float duration_seconds
        bigint views_count
        datetime created_at
        datetime published_at
    }
    jobs {
        int id PK
        int video_id FK
        string status
        int attempts
        datetime locked_at
        text error
        datetime created_at
    }
    video_shares {
        int video_id PK
        int user_id PK
        datetime created_at
    }
    likes {
        int user_id PK
        int video_id PK
        smallint value
        datetime created_at
    }
    comments {
        int id PK
        int video_id FK
        int user_id FK
        int parent_id FK
        string text
        bool hidden_by_moderation
        datetime created_at
    }
    subscriptions {
        int subscriber_id PK
        int channel_id PK
        datetime created_at
    }
    playlists {
        int id PK
        int owner_id FK
        string title
        string description
        bool is_public
        string kind
        datetime created_at
    }
    playlist_items {
        int id PK
        int playlist_id FK
        int video_id FK
        datetime created_at
    }
    watch_history {
        int id PK
        int user_id FK
        int video_id FK
        datetime watched_at
    }
    reports {
        int id PK
        int video_id FK
        int comment_id FK
        int reporter_id FK
        string reason
        string details
        string status
        int handled_by_id FK
        datetime handled_at
        datetime created_at
    }
    audit_log {
        int id PK
        int actor_id FK
        string action
        string target_type
        int target_id
        jsonb details
        datetime created_at
    }
```

## Ограничения целостности

| Таблица | Ограничение |
|---|---|
| `users` | роль `user`/`moderator`/`admin` (CHECK); email и username уникальны без учёта регистра |
| `channels` | один канал на пользователя (`owner_id` уникален); handle уникален без учёта регистра |
| `videos` | CHECK на `status` и `visibility`; FK на `categories` без каскада |
| `jobs` | CHECK на `status` |
| `likes` | CHECK `value IN (1, -1)`; ключ `(user_id, video_id)` |
| `reports` | CHECK `num_nonnulls(video_id, comment_id) = 1` (цель ровно одна); частичные уникальные индексы: одна открытая жалоба пользователя на одну цель |
| `playlists` | CHECK `kind <> 'watch_later' OR is_public IS FALSE`; частичный уникальный индекс: один «Смотреть позже» на пользователя |
| `playlist_items`, `watch_history` | уникальны пары `(playlist_id, video_id)` и `(user_id, video_id)` |
| `audit_log` | `target_id` без FK: запись остаётся после удаления цели, снимок данных лежит в `details` |

Удаление каскадом: пользователь → канал, видео, комментарии, лайки, плейлисты, подписки, сессии, историю;
видео → комментарии, лайки, шеры, задачи, жалобы, элементы плейлистов, историю; комментарий → ответы и жалобы.
Файлы на диске удаляет код после коммита.

## Индексы

Внешние ключи индексированы. Дополнительно: GIN `ix_videos_title_trgm` (`gin_trgm_ops`) для поиска
по подстроке, `ix_jobs_status` для выборки очереди.

## Справочник категорий

`categories` наполняется миграцией, через API не меняется. Список правится в миграции
`backend/migrations/versions/*_categories.py`. Тесты не очищают эту таблицу.

## Очередь

Воркер берёт задачу так: `SELECT ... WHERE status = 'queued' ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED`,
сразу переводит её в `running` и коммитит; ffmpeg работает вне транзакции.