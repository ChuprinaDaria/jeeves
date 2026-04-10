#!/usr/bin/env python
"""
Скрипт для видалення промптів
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MASTER.settings')
django.setup()

from MASTER.clients.models import Prompt, PromptVote

def delete_all_prompts():
    """Видалити всі промпти"""
    prompts_count = Prompt.objects.count()
    votes_count = PromptVote.objects.count()
    
    print("=" * 80)
    print("ВИДАЛЕННЯ ПРОМПТІВ")
    print("=" * 80)
    print(f"Знайдено промптів: {prompts_count}")
    print(f"Знайдено голосів: {votes_count}")
    print()
    
    if prompts_count == 0:
        print("✅ Промпти не знайдені, нічого видаляти")
        return
    
    # Видаляємо спочатку голоси (через foreign key)
    if votes_count > 0:
        deleted_votes = PromptVote.objects.all().delete()
        print(f"✅ Видалено голосів: {deleted_votes[0]}")
    
    # Видаляємо промпти
    deleted = Prompt.objects.all().delete()
    print(f"✅ Видалено промптів: {deleted[0]}")
    print()
    print("=" * 80)
    print("✅ Всі промпти успішно видалено!")
    print("=" * 80)

def delete_prompts_by_category(category):
    """Видалити промпти за категорією"""
    prompts = Prompt.objects.filter(category=category)
    count = prompts.count()
    
    if count == 0:
        print(f"✅ Промпти з категорією '{category}' не знайдені")
        return
    
    # Видаляємо голоси для цих промптів
    prompt_ids = list(prompts.values_list('id', flat=True))
    deleted_votes = PromptVote.objects.filter(prompt_id__in=prompt_ids).delete()
    print(f"✅ Видалено голосів: {deleted_votes[0]}")
    
    # Видаляємо промпти
    deleted = prompts.delete()
    print(f"✅ Видалено промптів з категорією '{category}': {deleted[0]}")
    print()
    print("=" * 80)
    print(f"✅ Промпти категорії '{category}' успішно видалено!")
    print("=" * 80)

def list_prompts():
    """Показати список всіх промптів"""
    prompts = Prompt.objects.all().order_by('-created_at')
    count = prompts.count()
    
    print("=" * 80)
    print(f"СПИСОК ПРОМПТІВ (всього: {count})")
    print("=" * 80)
    
    if count == 0:
        print("Промпти не знайдені")
        return
    
    for prompt in prompts:
        print(f"\nID: {prompt.id}")
        print(f"  Назва: {prompt.title}")
        print(f"  Категорія: {prompt.category}")
        print(f"  Створено: {prompt.created_at}")
        print(f"  Використань: {prompt.usage_count}")
        print(f"  Лайків: {prompt.likes_count}")
        print(f"  Дизлайків: {prompt.dislikes_count}")
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'delete-all':
            confirm = input("⚠️  Ви впевнені, що хочете видалити ВСІ промпти? (yes/no): ")
            if confirm.lower() == 'yes':
                delete_all_prompts()
            else:
                print("❌ Операцію скасовано")
        
        elif command == 'delete-category' and len(sys.argv) > 2:
            category = sys.argv[2]
            confirm = input(f"⚠️  Видалити всі промпти категорії '{category}'? (yes/no): ")
            if confirm.lower() == 'yes':
                delete_prompts_by_category(category)
            else:
                print("❌ Операцію скасовано")
        
        elif command == 'list':
            list_prompts()
        
        else:
            print("Usage:")
            print("  List prompts: python delete_prompts.py list")
            print("  Delete all: python delete_prompts.py delete-all")
            print("  Delete by category: python delete_prompts.py delete-category <category>")
            print("\nCategories: marketing, sales, hr, customer_support, legal, finance, tech, content")
    else:
        print("Usage:")
        print("  List prompts: python delete_prompts.py list")
        print("  Delete all: python delete_prompts.py delete-all")
        print("  Delete by category: python delete_prompts.py delete-category <category>")
        print("\nCategories: marketing, sales, hr, customer_support, legal, finance, tech, content")

