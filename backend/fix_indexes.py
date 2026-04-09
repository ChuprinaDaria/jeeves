#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MASTER.settings')
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    print("Починаємо оновлення індексів...")
    
    # Видаляємо старі індекси
    print("Видалення старих індексів...")
    cursor.execute("DROP INDEX IF EXISTS clients_clientembedding_vector_idx;")
    cursor.execute("DROP INDEX IF EXISTS branches_branchembedding_vector_idx;")
    cursor.execute("DROP INDEX IF EXISTS specializations_specializationembedding_vector_idx;")

    # Створюємо нові індекси типу IVFFlat
    print("Створення нових IVFFlat індексів...")
    try:
        cursor.execute("CREATE INDEX clients_clientembedding_vector_idx ON clients_clientembedding USING ivfflat (vector vector_cosine_ops) WITH (lists = 100);")
        print("- Індекс для clients_clientembedding створено")
    except Exception as e:
        print(f"Помилка при створенні індексу clients_clientembedding: {e}")
    
    try:
        cursor.execute("CREATE INDEX branches_branchembedding_vector_idx ON branches_branchembedding USING ivfflat (vector vector_cosine_ops) WITH (lists = 100);")
        print("- Індекс для branches_branchembedding створено")
    except Exception as e:
        print(f"Помилка при створенні індексу branches_branchembedding: {e}")
    
    try:
        cursor.execute("CREATE INDEX specializations_specializationembedding_vector_idx ON specializations_specializationembedding USING ivfflat (vector vector_cosine_ops) WITH (lists = 100);")
        print("- Індекс для specializations_specializationembedding створено")
    except Exception as e:
        print(f"Помилка при створенні індексу specializations_specializationembedding: {e}")
    
    print("Оновлення індексів завершено!")
