# Виправлення помилки pgvector "type vector does not exist"

## Проблема
Якщо при запуску контейнера виникає помилка:
```
django.db.utils.ProgrammingError: type "vector" does not exist
```

Це означає, що розширення `pgvector` не встановлено в базі даних PostgreSQL.

## Автоматичне виправлення (рекомендовано)

При запуску через `docker-compose up`, система автоматично:
1. ✅ Виконає init скрипт PostgreSQL для нових баз (`init__db.sql`)
2. ✅ Entrypoint скрипт (`docker-entrypoint.sh`) створить розширення через psql
3. ✅ Python скрипт (`ensure_pgvector.py`) перевірить та створить як backup

**Всі перевірки відбуваються при білді та запуску контейнера!**

Якщо база вже існує і скрипт не спрацював, виконайте вручну:

```bash
docker compose exec web python ensure_pgvector.py
```

## Ручне виправлення

### Крок 1: Підключіться до PostgreSQL контейнера

```bash
docker compose exec postgres psql -U admin_user -d admin_db
```

Якщо використовуєте інші credentials, замініть:
- `admin_user` на ваш `DB_USER`
- `admin_db` на ваш `DB_NAME`

### Крок 2: Створіть розширення

У консолі psql виконайте:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Повинно з'явитися повідомлення:
```
CREATE EXTENSION
```

### Крок 3: Перевірте

Перевірте, що розширення створено:

```sql
\dx
```

У списку має бути `vector`.

### Крок 4: Вийдіть з psql

```sql
\q
```

### Крок 5: Перезапустіть веб-контейнер

```bash
docker compose restart web
```

## Поточна конфігурація

У `docker-compose.yml` вже налаштовано:
1. ✅ Використання образу `pgvector/pgvector:pg16`
2. ✅ Автоматичний init скрипт (`init__db.sql`) для нових баз
3. ✅ Скрипт `ensure_pgvector.py` для перевірки перед міграціями

## Для нових розгортань

Якщо розгортаєте з нуля, просто запустіть:

```bash
docker compose down -v  # Видалити всі дані
docker compose up -d    # Створити заново
```

Розширення `vector` буде створено автоматично.

## Перебілд образу після змін

Якщо ви змінили Dockerfile або entrypoint скрипт, потрібно перебудувати образ:

```bash
# Перебудувати образ
docker compose build web

# Або з форсом (якщо кеш заважає)
docker compose build --no-cache web

# Перезапустити контейнери
docker compose up -d
```

Це гарантує, що всі зміни будуть застосовані.
