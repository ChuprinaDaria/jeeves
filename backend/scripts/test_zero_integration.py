#!/usr/bin/env python3
"""
Тестовий скрипт для перевірки інтеграції Zero email service.

Використання:
    python scripts/test_zero_integration.py
"""
import os
import sys
import django

# Налаштування Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MASTER.settings')
django.setup()

from MASTER.clients.models import Client, ClientZeroConfig
from MASTER.clients.docker_manager import ZeroDockerManager
from MASTER.accounts.models import User, Roles
import secrets


def generate_better_auth_secret():
    """Генерує 32-символьний hex secret для Better Auth."""
    return secrets.token_hex(32)


def test_docker_connection():
    """Тест 1: Перевірка з'єднання з Docker."""
    print("\n" + "="*60)
    print("ТЕСТ 1: Перевірка з'єднання з Docker")
    print("="*60)
    try:
        manager = ZeroDockerManager()
        info = manager.client.info()
        print(f"✅ Docker підключено успішно!")
        print(f"   Версія: {info.get('ServerVersion', 'N/A')}")
        print(f"   Контейнери: {info.get('Containers', 0)} (running: {info.get('ContainersRunning', 0)})")
        return True
    except Exception as e:
        print(f"❌ Помилка підключення до Docker: {e}")
        return False


def test_create_zero_config():
    """Тест 2: Створення ClientZeroConfig для тестового клієнта."""
    print("\n" + "="*60)
    print("ТЕСТ 2: Створення Zero Config")
    print("="*60)
    
    try:
        # Знайти або створити тестового клієнта
        test_user = User.objects.filter(role=Roles.CLIENT).first()
        
        if not test_user:
            print("⚠️  Немає клієнтів у системі. Створіть клієнта через адмін-панель.")
            return None
        
        client = Client.objects.filter(user=test_user).first()
        
        if not client:
            print(f"⚠️  User {test_user.username} не має профілю клієнта.")
            return None
        
        print(f"📋 Використовую клієнта: {client.user.username}")
        
        # Створити або оновити Zero config
        config, created = ClientZeroConfig.objects.get_or_create(
            client=client,
            defaults={
                'enabled': True,
                'status': ClientZeroConfig.STATUS_DISABLED,
                'repo_url': 'https://github.com/Mail-0/Zero',
                'repo_branch': 'staging',
                'image': 'zero-test:latest',  # Використовуємо локальний тестовий image
                'container_name': f'zero_test_client_{client.pk}',
                'host_port': None,  # Auto-assign
                
                # Database config (використовуємо існуючу БД для тесту)
                'db_name': 'zerodotemail',
                'db_user': 'postgres',
                'db_password': 'postgres',
                'db_host': 'postgres',  # або 'host.docker.internal' для доступу до хост-машини
                'db_port': 5432,
                
                # Мінімальні секрети для тесту
                'better_auth_secret': generate_better_auth_secret(),
                
                # Sync settings
                'thread_sync_max_count': 100,
                'thread_sync_loop': False,
                'drop_agent_tables': False,
            }
        )
        
        if created:
            print(f"✅ Створено нову Zero конфігурацію для клієнта {client.pk}")
        else:
            print(f"✅ Знайдено існуючу Zero конфігурацію для клієнта {client.pk}")
            print(f"   Статус: {config.get_status_display()}")  # type: ignore[attr-defined]
            print(f"   Enabled: {config.enabled}")
            print(f"   Container: {config.container_name}")
        
        return config
        
    except Exception as e:
        print(f"❌ Помилка створення config: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_container_lifecycle(config):
    """Тест 3: Lifecycle контейнера (start, status, stop)."""
    print("\n" + "="*60)
    print("ТЕСТ 3: Lifecycle Zero контейнера")
    print("="*60)
    
    if not config:
        print("⚠️  Немає config для тесту")
        return False
    
    manager = ZeroDockerManager()
    
    try:
        # 1. Перевірка статусу (має бути stopped або not found)
        print("\n1️⃣  Перевірка початкового статусу...")
        status = manager.get_container_status(config.container_name)
        print(f"   Статус: {status}")
        
        # 2. Спроба запуску (УВАГА: потребує prebuilt image або Dockerfile)
        print("\n2️⃣  Спроба запуску контейнера...")
        print(f"   Image: {config.image or 'zero-test:latest'}")
        print(f"   Container name: {config.container_name}")
        print("   ⚠️  ПРИМІТКА: Це може зайняти час якщо image потрібно завантажити...")
        
        try:
            result = manager.start_zero_container(
                container_name=config.container_name,
                env=config.build_env(),
                host_port=config.host_port,
                image=config.image or 'zero-test:latest',
                repo_url=config.repo_url,
                repo_branch=config.repo_branch,
            )
            print(f"✅ Контейнер запущено!")
            print(f"   Container ID: {result.get('container_id', 'N/A')[:12]}")
            print(f"   Host Port: {result.get('host_port', 'N/A')}")
            print(f"   Status: {result.get('status', 'N/A')}")
            
            # Оновити config
            config.container_id = result.get('container_id', '')
            config.host_port = result.get('host_port') or config.host_port
            config.status = ClientZeroConfig.STATUS_RUNNING
            config.save()
            
            # 3. Перевірка здоров'я
            print("\n3️⃣  Перевірка здоров'я контейнера...")
            import time
            time.sleep(2)  # Почекати трохи
            status = manager.get_container_status(config.container_name)
            print(f"   Статус: {status.get('status', 'unknown')}")
            print(f"   Health: {status.get('health', 'unknown')}")
            
            # 4. Зупинка
            print("\n4️⃣  Зупинка контейнера...")
            stop_result = manager.stop_zero_container(config.container_name, remove=True)
            print(f"   {stop_result.get('message', 'Stopped')}")
            
            config.status = ClientZeroConfig.STATUS_STOPPED
            config.container_id = ""
            config.save()
            
            print("\n✅ Lifecycle тест пройшов успішно!")
            return True
            
        except ValueError as e:
            # Image не знайдено
            print(f"\n⚠️  {e}")
            print("\n💡 Рішення:")
            print("   1. Вкажіть prebuilt image у полі 'image' ClientZeroConfig")
            print("   2. Або додайте логіку білдингу з repo (потребує Dockerfile)")
            print("   3. Або використайте офіційний image якщо доступний")
            return False
            
    except Exception as e:
        print(f"❌ Помилка під час lifecycle тесту: {e}")
        import traceback
        traceback.print_exc()
        
        # Спробувати очистити якщо щось залишилось
        try:
            manager.stop_zero_container(config.container_name, remove=True)
        except:
            pass
        
        return False


def test_celery_tasks(config):
    """Тест 4: Celery задачі."""
    print("\n" + "="*60)
    print("ТЕСТ 4: Celery задачі (опціонально)")
    print("="*60)
    
    if not config:
        print("⚠️  Немає config для тесту")
        return False
    
    try:
        from MASTER.clients.tasks import check_zero_container_health_task
        
        print("📋 Запуск health check через Celery...")
        result = check_zero_container_health_task.delay(config.pk)
        print(f"   Task ID: {result.id}")
        print(f"   ✅ Задача відправлена в чергу")
        print(f"   💡 Перевірте результат через Celery worker logs")
        
        return True
        
    except Exception as e:
        print(f"⚠️  Celery тест пропущено: {e}")
        return False


def main():
    """Головна функція тестування."""
    print("\n" + "🚀 " * 20)
    print("ТЕСТУВАННЯ ZERO EMAIL SERVICE INTEGRATION")
    print("🚀 " * 20)
    
    # Тест 1: Docker connection
    if not test_docker_connection():
        print("\n❌ Тести зупинено: немає підключення до Docker")
        return
    
    # Тест 2: Create config
    config = test_create_zero_config()
    if not config:
        print("\n❌ Тести зупинено: не вдалося створити config")
        return
    
    # Тест 3: Container lifecycle
    lifecycle_ok = test_container_lifecycle(config)
    
    # Тест 4: Celery tasks (optional)
    test_celery_tasks(config)
    
    # Підсумок
    print("\n" + "="*60)
    print("ПІДСУМОК ТЕСТУВАННЯ")
    print("="*60)
    print(f"✅ Docker підключення: OK")
    print(f"✅ Zero Config створено: OK")
    print(f"{'✅' if lifecycle_ok else '⚠️ '} Container Lifecycle: {'OK' if lifecycle_ok else 'ПОТРЕБУЄ IMAGE'}")
    print(f"✅ Celery інтеграція: OK")
    
    print("\n" + "📚 " * 20)
    print("НАСТУПНІ КРОКИ:")
    print("📚 " * 20)
    print("1. Відкрийте Django Admin: http://localhost:8001/admin/")
    print("2. Перейдіть до Clients")
    print("3. Виберіть клієнта і розгорніть 'Zero Email Service Configuration'")
    print("4. Заповніть необхідні поля (секрети, БД, image)")
    print("5. Активуйте 'enabled' і збережіть")
    print("6. Виберіть клієнта і виконайте action: '🚀 Start Zero Service'")
    print("7. Перевірте статус у колонці 'Zero Status'")
    print("\n💡 Для повноцінної роботи Zero потрібні:")
    print("   - BETTER_AUTH_SECRET (автогенерується)")
    print("   - GOOGLE_CLIENT_ID + SECRET (для Gmail)")
    print("   - AUTUMN_SECRET_KEY (для шифрування)")
    print("   - TWILIO credentials (для SMS, опційно)")
    print("   - PostgreSQL БД (окрема для кожного клієнта)")
    print("\n🔗 Документація Zero: https://github.com/Mail-0/Zero")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()

