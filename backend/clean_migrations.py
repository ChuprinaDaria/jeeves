#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MASTER.settings')
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    print("Очищення записів про міграції...")
    
    # Видаляємо записи про проблемні міграції з django_migrations
    cursor.execute("DELETE FROM django_migrations WHERE app = 'EmbeddingModel' AND name = '0002_reduce_vector_dimensions';")
    cursor.execute("DELETE FROM django_migrations WHERE app = 'EmbeddingModel' AND name = '0003_fix_vector_indexes';")
    
    # Якщо є інші проблемні міграції, можна також їх видалити
    
    print("Очищення завершено. Тепер видаліть файли міграцій і створіть нову.")
