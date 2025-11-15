#!/usr/bin/env python3
"""
Скрипт для налаштування LLM моделі для клієнта.
Використання:
    python scripts/setup_client_llm.py <client_tag> <llm_provider> <model_name>

Приклад:
    python scripts/setup_client_llm.py srtyh ollama_main qwen2.5:7b
    python scripts/setup_client_llm.py srtyh ollama_light qwen2.5:7b

LLM Providers:
    - openai: OpenAI GPT models (gpt-4o-mini, gpt-4o)
    - ollama_main: Ollama Main Server (192.168.0.51:11434)
    - ollama_light: Ollama Light Server (192.168.0.52:11434)
    - kimi: Kimi Moonshot AI
"""

import os
import sys
import django

# Налаштування Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MASTER.settings')
django.setup()

from MASTER.clients.models import Client


def setup_client_llm(client_tag, llm_provider, model_name):
    """Налаштувати LLM модель для клієнта."""
    try:
        client = Client.objects.get(tag=client_tag, is_active=True)
    except Client.DoesNotExist:
        print(f"❌ Client з tag '{client_tag}' не знайдено!")
        return False
    
    # Валідація provider
    valid_providers = ['openai', 'ollama_main', 'ollama_light', 'kimi']
    if llm_provider not in valid_providers:
        print(f"❌ Невалідний provider '{llm_provider}'!")
        print(f"   Доступні: {', '.join(valid_providers)}")
        return False
    
    # Оновлюємо налаштування
    client.llm_provider = llm_provider
    client.llm_model_name = model_name
    client.save(update_fields=['llm_provider', 'llm_model_name'])
    
    print(f"✅ Успішно налаштовано LLM для клієнта '{client.company_name or client.tag}':")
    print(f"   Provider: {llm_provider}")
    print(f"   Model: {model_name}")
    
    # Показуємо endpoint
    if llm_provider == 'ollama_main':
        print(f"   Endpoint: http://192.168.0.51:11434")
    elif llm_provider == 'ollama_light':
        print(f"   Endpoint: http://192.168.0.52:11434")
    
    return True


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    
    client_tag = sys.argv[1]
    llm_provider = sys.argv[2]
    model_name = sys.argv[3]
    
    success = setup_client_llm(client_tag, llm_provider, model_name)
    sys.exit(0 if success else 1)

