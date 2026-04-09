#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MASTER.settings')
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    print("Починаємо зменшення розмірності векторів...")
    
    # Видаляємо старі індекси
    print("Видалення старих індексів...")
    cursor.execute("DROP INDEX IF EXISTS clients_clientembedding_vector_idx;")
    cursor.execute("DROP INDEX IF EXISTS branches_branchembedding_vector_idx;")
    cursor.execute("DROP INDEX IF EXISTS specializations_specializationembedding_vector_idx;")
    
    # Змінюємо розмірність векторів
    print("Зміна розмірності векторів...")
    try:
        cursor.execute("ALTER TABLE clients_clientembedding ALTER COLUMN vector TYPE vector(1536);")
        print("- Розмірність clients_clientembedding змінена на 1536")
    except Exception as e:
        print(f"Помилка при зміні розмірності clients_clientembedding: {e}")
    
    try:
        cursor.execute("ALTER TABLE branches_branchembedding ALTER COLUMN vector TYPE vector(1536);")
        print("- Розмірність branches_branchembedding змінена на 1536")
    except Exception as e:
        print(f"Помилка при зміні розмірності branches_branchembedding: {e}")
    
    try:
        cursor.execute("ALTER TABLE specializations_specializationembedding ALTER COLUMN vector TYPE vector(1536);")
        print("- Розмірність specializations_specializationembedding змінена на 1536")
    except Exception as e:
        print(f"Помилка при зміні розмірності specializations_specializationembedding: {e}")
    
    # Створюємо нові індекси
    print("Створення нових індексів...")
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
    
    print("Зміна розмірності векторів завершена!")
