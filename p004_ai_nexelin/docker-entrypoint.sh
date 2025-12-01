#!/bin/bash
set -e

echo "🚀 Запуск entrypoint скрипта..."

# Очікуємо готовності PostgreSQL
echo "⏳ Очікую готовності PostgreSQL..."
RETRIES=30
until PGPASSWORD="${DB_PASS:-admin_pass}" psql -h "${DB_HOST:-postgres}" -U "${DB_USER:-admin_user}" -d "${DB_NAME:-admin_db}" -c '\q' 2>/dev/null || [ $RETRIES -eq 0 ]; do
  echo "⏳ PostgreSQL ще не готовий, залишилось спроб: $RETRIES"
  RETRIES=$((RETRIES-1))
  sleep 2
done

if [ $RETRIES -eq 0 ]; then
  echo "❌ Не вдалося підключитися до PostgreSQL!"
  exit 1
fi

echo "✓ PostgreSQL готовий!"

# Створюємо розширення pgvector через psql
echo "🔍 Перевіряю наявність розширення pgvector через psql..."
PGPASSWORD="${DB_PASS:-admin_pass}" psql -h "${DB_HOST:-postgres}" -U "${DB_USER:-admin_user}" -d "${DB_NAME:-admin_db}" <<-EOSQL || true
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
            CREATE EXTENSION IF NOT EXISTS vector;
            RAISE NOTICE 'Розширення vector успішно створено';
        ELSE
            RAISE NOTICE 'Розширення vector вже існує';
        END IF;
    END
    \$\$;
EOSQL

if [ $? -eq 0 ]; then
    echo "✓ Перевірка/створення pgvector через psql завершено!"
else
    echo "⚠️ Не вдалося створити розширення через psql, спробую через Python..."
fi

# Виконуємо Python скрипт як backup для перевірки
echo "🐍 Запускаю Python скрипт для фінальної перевірки..."
python ensure_pgvector.py || {
    echo "⚠️ Python скрипт не вдалося виконати, але продовжую..."
}


# Збираємо статичні файли
echo "📁 Збираю статичні файли..."
python manage.py collectstatic --no-input --clear || {
    echo "⚠️ Попередження: не вдалося зібрати статичні файли, продовжую..."
}

# Запускаємо команду, передану як аргументи
echo "🚀 Запускаю команду: $@"
exec "$@"
