#!/usr/bin/env python
"""
Перевірка паролю для email клієнта
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, '/home/dchuprina/nexelin_web/p004_ai_nexelin')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MASTER.settings')
django.setup()

from MASTER.clients.models import Client

def check_password(client_id):
    """Перевірка паролю для клієнта"""
    try:
        client = Client.objects.get(id=client_id)
        print(f"Client ID: {client_id}")
        print(f"Email SMTP Enabled: {client.email_smtp_enabled}")
        print(f"SMTP Username: {client.email_smtp_username}")
        print(f"SMTP Password field value: '{client.email_smtp_password}'")
        print(f"Password length: {len(client.email_smtp_password) if client.email_smtp_password else 0}")
        print(f"Password is None: {client.email_smtp_password is None}")
        print(f"Password is empty string: {client.email_smtp_password == ''}")
        print(f"Password stripped is empty: {client.email_smtp_password.strip() == '' if client.email_smtp_password else 'N/A'}")
        
        if client.email_smtp_password:
            print(f"✅ Password is SET (length: {len(client.email_smtp_password)})")
            # Don't show password, just first and last char
            if len(client.email_smtp_password) > 2:
                masked = client.email_smtp_password[0] + '*' * (len(client.email_smtp_password) - 2) + client.email_smtp_password[-1]
                print(f"Password preview: {masked}")
        else:
            print("❌ Password is NOT SET")
            
    except Client.DoesNotExist:
        print(f"❌ Client {client_id} not found")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        client_id = int(sys.argv[1])
        check_password(client_id)
    else:
        print("Usage: python check_password.py <client_id>")
        print("Example: python check_password.py 21")

