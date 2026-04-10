#!/usr/bin/env python
"""Скрипт для перевірки та створення розширення pgvector в PostgreSQL"""
import os
import sys
import time
import django
from django.core.exceptions import ImproperlyConfigured

# Налаштування Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Jeeves.settings')

try:
    django.setup()
except ImproperlyConfigured as e:
    print(f"⚠️ Django налаштування не готові, намагаюсь все одно підключитися до БД...", file=sys.stderr)

from django.db import connection
from django.db.utils import OperationalError, DatabaseError

def wait_for_db(max_retries=30, delay=2):
    """Чекаємо, поки база даних стане доступною"""
    for attempt in range(max_retries):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return True
        except (OperationalError, DatabaseError) as e:
            if attempt < max_retries - 1:
                print(f"⏳ Очікую підключення до БД (спроба {attempt + 1}/{max_retries})...")
                time.sleep(delay)
            else:
                print(f"❌ Не вдалося підключитися до БД після {max_retries} спроб", file=sys.stderr)
                raise
    return False

def ensure_pgvector():
    """Створює розширення vector в базі даних, якщо його немає"""
    print("🔍 Перевіряю наявність розширення pgvector...")
    
    # Чекаємо на підключення до БД
    wait_for_db()
    
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            with connection.cursor() as cursor:
                # Перевіряємо, чи існує розширення
                cursor.execute("""
                    SELECT EXISTS(
                        SELECT 1 FROM pg_extension WHERE extname = 'vector'
                    );
                """)
                exists = cursor.fetchone()[0]
                
                if exists:
                    print("✓ Розширення 'vector' вже існує")
                    return True
                
                # Створюємо розширення
                print("🔧 Створюю розширення 'vector'...")
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                connection.commit()
                
                # Перевіряємо, що розширення створилось
                cursor.execute("""
                    SELECT EXISTS(
                        SELECT 1 FROM pg_extension WHERE extname = 'vector'
                    );
                """)
                created = cursor.fetchone()[0]
                
                if created:
                    print("✓ Розширення 'vector' успішно створено!")
                    return True
                else:
                    raise Exception("Розширення не створилось після команди CREATE EXTENSION")
                    
        except Exception as e:
            if attempt < max_attempts - 1:
                wait_time = (attempt + 1) * 2
                print(f"⚠️ Помилка (спроба {attempt + 1}/{max_attempts}): {e}")
                print(f"⏳ Чекаю {wait_time} секунд перед повторною спробою...")
                time.sleep(wait_time)
                # Перезапускаємо підключення
                connection.close()
            else:
                print(f"❌ Не вдалося створити розширення vector після {max_attempts} спроб", file=sys.stderr)
                print(f"❌ Остання помилка: {e}", file=sys.stderr)
                sys.exit(1)
    
    return False

if __name__ == '__main__':
    ensure_pgvector()
