#!/usr/bin/env python3
"""
Інтерактивний скрипт для швидкого налаштування Zero для клієнта.

Використання:
    python scripts/setup_zero_for_client.py
"""
import os
import sys
import django
import secrets

# Налаштування Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MASTER.settings')
django.setup()

from MASTER.clients.models import Client, ClientZeroConfig
from MASTER.accounts.models import User, Roles


def generate_secret(length: int = 32) -> str:
    """Генерує безпечний секрет."""
    return secrets.token_hex(length)


def print_header(text: str):
    """Друкує красивий заголовок."""
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70)


def select_client() -> Client:
    """Дозволяє вибрати клієнта зі списку."""
    print_header("КРОК 1: Вибір клієнта")
    
    clients = Client.objects.select_related('user', 'specialization').all()
    
    if not clients:
        print("❌ Немає жодного клієнта в системі!")
        print("💡 Створіть клієнта через Django Admin:")
        print("   http://localhost:8001/admin/clients/client/add/")
        sys.exit(1)
    
    print("\nДоступні клієнти:")
    for i, client in enumerate(clients, 1):
        status = "✓" if client.is_active else "✗"
        zero_status = "Configured" if hasattr(client, 'zero_config') else "Not configured"
        print(f"  {i}. {client.user.username} - {client.company_name or 'No company'} [{status}] - Zero: {zero_status}")
    
    while True:
        try:
            choice = input(f"\nВиберіть клієнта (1-{len(clients)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(clients):
                return clients[idx]
            print("❌ Невірний вибір, спробуйте ще раз")
        except (ValueError, KeyboardInterrupt):
            print("\n❌ Скасовано")
            sys.exit(0)


def get_google_credentials() -> tuple[str, str]:
    """Отримати Google OAuth credentials від користувача."""
    print_header("КРОК 2: Google OAuth Credentials")
    
    print("\n📋 Для роботи з Gmail потрібні Google OAuth credentials.")
    print("   Інструкція: docs/ZERO_REAL_SETUP.md (Крок 1)")
    print("   Або: https://console.cloud.google.com/apis/credentials")
    
    print("\n💡 Якщо ви ще не створили credentials, зробіть це зараз і поверніться.")
    proceed = input("   Продовжити? (y/n): ").strip().lower()
    
    if proceed != 'y':
        print("❌ Скасовано")
        sys.exit(0)
    
    print("\n1. Google Client ID (схоже на: 123456...apps.googleusercontent.com)")
    client_id = input("   Client ID: ").strip()
    
    print("\n2. Google Client Secret (схоже на: GOCSPX-...)")
    client_secret = input("   Client Secret: ").strip()
    
    if not client_id or not client_secret:
        print("❌ Client ID та Secret є обов'язковими!")
        sys.exit(1)
    
    return client_id, client_secret


def get_database_config() -> dict:
    """Отримати налаштування БД від користувача."""
    print_header("КРОК 3: PostgreSQL Database")
    
    print("\n📋 Кожен Zero контейнер потребує окрему БД.")
    print("   Рекомендовано створити нову БД через:")
    print("   docker exec -it <postgres_container> psql -U postgres")
    print("   CREATE DATABASE zero_client_X;")
    
    use_defaults = input("\n💡 Використати стандартні налаштування для тесту? (y/n): ").strip().lower()
    
    if use_defaults == 'y':
        return {
            'db_name': 'zerodotemail',
            'db_user': 'postgres',
            'db_password': 'postgres',
            'db_host': 'postgres',
            'db_port': 5432,
        }
    
    print("\nВведіть налаштування БД:")
    db_name = input("  DB Name [zero_client_1]: ").strip() or 'zero_client_1'
    db_user = input("  DB User [postgres]: ").strip() or 'postgres'
    db_password = input("  DB Password [postgres]: ").strip() or 'postgres'
    db_host = input("  DB Host [postgres]: ").strip() or 'postgres'
    db_port = input("  DB Port [5432]: ").strip() or '5432'
    
    return {
        'db_name': db_name,
        'db_user': db_user,
        'db_password': db_password,
        'db_host': db_host,
        'db_port': int(db_port),
    }


def get_docker_image() -> str:
    """Отримати назву Docker image."""
    print_header("КРОК 4: Docker Image")
    
    print("\n📋 Виберіть джерело Zero image:")
    print("   1. Локальний build (zero-production:latest)")
    print("   2. Офіційний staging (ghcr.io/mail-0/zero:staging)")
    print("   3. Тестовий mock (zero-test:latest)")
    print("   4. Інший (вказати вручну)")
    
    choice = input("\nВибір (1-4) [1]: ").strip() or '1'
    
    images = {
        '1': 'zero-production:latest',
        '2': 'ghcr.io/mail-0/zero:staging',
        '3': 'zero-test:latest',
    }
    
    if choice in images:
        return images[choice]
    elif choice == '4':
        return input("Image name: ").strip()
    else:
        return 'zero-production:latest'


def create_or_update_config(client: Client, google_client_id: str, google_client_secret: str, 
                            db_config: dict, image: str) -> ClientZeroConfig:
    """Створити або оновити Zero config."""
    print_header("КРОК 5: Створення конфігурації")
    
    # Генерувати секрети
    better_auth_secret = generate_secret(32)
    autumn_secret_key = secrets.token_urlsafe(32)
    
    # Створити або оновити
    config, created = ClientZeroConfig.objects.get_or_create(
        client=client,
        defaults={
            'enabled': True,
            'status': ClientZeroConfig.STATUS_DISABLED,
            'repo_url': 'https://github.com/Mail-0/Zero',
            'repo_branch': 'staging',
            'image': image,
            'container_name': f'zero_client_{client.pk}',
            
            # Database
            'db_name': db_config['db_name'],
            'db_user': db_config['db_user'],
            'db_password': db_config['db_password'],
            'db_host': db_config['db_host'],
            'db_port': db_config['db_port'],
            
            # Secrets
            'better_auth_secret': better_auth_secret,
            'google_client_id': google_client_id,
            'google_client_secret': google_client_secret,
            'autumn_secret_key': autumn_secret_key,
            
            # Sync settings
            'thread_sync_max_count': 500,
            'thread_sync_loop': True,
            'drop_agent_tables': False,
        }
    )
    
    if not created:
        # Оновити існуючу конфігурацію
        config.enabled = True
        config.image = image
        config.google_client_id = google_client_id
        config.google_client_secret = google_client_secret
        
        # Оновити БД якщо потрібно
        if db_config['db_name'] != 'zerodotemail':  # Не дефолтна БД
            config.db_name = db_config['db_name']
            config.db_user = db_config['db_user']
            config.db_password = db_config['db_password']
            config.db_host = db_config['db_host']
            config.db_port = db_config['db_port']
        
        # Згенерувати нові секрети якщо пусті
        if not config.better_auth_secret:
            config.better_auth_secret = better_auth_secret
        if not config.autumn_secret_key:
            config.autumn_secret_key = autumn_secret_key
        
        config.save()
        print("✅ Оновлено існуючу конфігурацію")
    else:
        print("✅ Створено нову конфігурацію")
    
    return config


def print_summary(client: Client, config: ClientZeroConfig):
    """Вивести підсумок налаштування."""
    print_header("ПІДСУМОК")
    
    print(f"\n✅ Zero налаштовано для клієнта: {client.user.username}")
    print(f"   Company: {client.company_name or 'N/A'}")
    print(f"   Container: {config.container_name}")
    print(f"   Image: {config.image}")
    print(f"   Database: {config.db_name}")
    print(f"   Status: {config.get_status_display()}")  # type: ignore[attr-defined]
    print(f"   Enabled: {'✓' if config.enabled else '✗'}")
    
    print_header("НАСТУПНІ КРОКИ")
    
    print("\n1️⃣  Переконайтеся що Docker image існує:")
    print(f"     docker images | grep {config.image.split(':')[0]}")
    
    if config.image == 'zero-production:latest':
        print("\n     Якщо image не знайдено, побудуйте його:")
        print("     cd /tmp && git clone https://github.com/Mail-0/Zero")
        print("     cd Zero && docker build -t zero-production:latest .")
    
    print("\n2️⃣  Налаштуйте Google OAuth redirect URI:")
    print("     https://console.cloud.google.com/apis/credentials")
    print("     Додайте:")
    print(f"     http://localhost:{{PORT}}/api/auth/callback/google")
    print("     (PORT буде призначений автоматично при запуску)")
    
    print("\n3️⃣  Запустіть Zero контейнер через Django Admin:")
    print("     http://localhost:8001/admin/clients/client/")
    print("     Виберіть клієнта → Action: '🚀 Start Zero Service'")
    
    print("\n4️⃣  Або запустіть зараз через Celery:")
    start_now = input("\n     Запустити Zero контейнер зараз? (y/n): ").strip().lower()
    
    if start_now == 'y':
        from MASTER.clients.tasks import start_zero_container_task
        print(f"\n     🚀 Запускаю контейнер...")
        task = start_zero_container_task.delay(config.pk)
        print(f"     ✅ Task ID: {task.id}")
        print(f"     💡 Перевірте статус через 10-15 секунд:")
        print(f"        docker ps | grep {config.container_name}")
        print(f"        docker logs {config.container_name}")
    
    print("\n5️⃣  Після запуску, перевірте Zero web interface:")
    print("     docker ps | grep zero  # знайти PORT")
    print("     http://localhost:{{PORT}}/")
    
    print("\n6️⃣  Підключіть Gmail через 'Sign in with Google'")
    
    print("\n" + "="*70)
    print("📚 Повна документація: docs/ZERO_REAL_SETUP.md")
    print("="*70 + "\n")


def main():
    """Головна функція."""
    print("\n" + "🚀 " * 35)
    print("НАЛАШТУВАННЯ ZERO EMAIL SERVICE ДЛЯ КЛІЄНТА")
    print("🚀 " * 35)
    
    try:
        # Крок 1: Вибрати клієнта
        client = select_client()
        
        # Крок 2: Google credentials
        google_client_id, google_client_secret = get_google_credentials()
        
        # Крок 3: Database config
        db_config = get_database_config()
        
        # Крок 4: Docker image
        image = get_docker_image()
        
        # Крок 5: Створити config
        config = create_or_update_config(client, google_client_id, google_client_secret, 
                                        db_config, image)
        
        # Підсумок
        print_summary(client, config)
        
    except KeyboardInterrupt:
        print("\n\n❌ Скасовано користувачем")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Помилка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

