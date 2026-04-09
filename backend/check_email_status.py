#!/usr/bin/env python
"""
Скрипт для перевірки налаштувань email для клієнта
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, '/home/dchuprina/nexelin_web/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MASTER.settings')
django.setup()

from MASTER.clients.models import Client

def check_email_status():
    """Перевіряє налаштування email для всіх клієнтів"""
    print("=" * 80)
    print("EMAIL STATUS FOR ALL CLIENTS")
    print("=" * 80)
    
    clients = Client.objects.all()
    
    for client in clients:
        print(f"\nClient ID: {client.id}")
        print(f"  User: {client.user}")
        print(f"  Company: {client.company_name or 'N/A'}")
        print(f"  Email SMTP Enabled: {client.email_smtp_enabled}")
        
        if client.email_smtp_enabled:
            print(f"  SMTP Host: {client.email_smtp_host}")
            print(f"  SMTP Port: {client.email_smtp_port}")
            print(f"  SMTP Use TLS: {client.email_smtp_use_tls}")
            print(f"  SMTP Username: {client.email_smtp_username}")
            password_set = bool(client.email_smtp_password and client.email_smtp_password.strip())
            print(f"  SMTP Password: {'SET (' + '*' * min(20, len(client.email_smtp_password)) + ')' if password_set else 'NOT SET ⚠️'}")
            print(f"  From Address: {client.email_from_address}")
            print(f"  From Name: {client.email_from_name}")
            
            # Test IMAP host detection
            from MASTER.clients.email_service import EmailService
            try:
                email_service = EmailService(client)
                if email_service.imap_host:
                    print(f"  IMAP Host (detected): {email_service.imap_host} ✅")
                else:
                    print(f"  IMAP Host (detected): None ⚠️ (Email reading will not work)")
                
                # Test if we can connect (optional, might be slow)
                if password_set and email_service.imap_host:
                    print(f"  Email reading: Available (IMAP configured)")
                elif password_set:
                    print(f"  Email reading: Not available (IMAP host not detected)")
                else:
                    print(f"  Email reading: Not available (Password not set)")
            except Exception as e:
                print(f"  IMAP Host detection error: {e}")
        else:
            print("  Email is DISABLED")
    
    print("\n" + "=" * 80)

def enable_email_for_client(client_id, smtp_host, smtp_username, smtp_password, from_address=None):
    """Вмикає email для клієнта"""
    try:
        client = Client.objects.get(id=client_id)
        print(f"\nEnabling email for client {client_id} ({client.user})")
        
        client.email_smtp_enabled = True
        client.email_smtp_host = smtp_host
        client.email_smtp_port = 587
        client.email_smtp_use_tls = True
        client.email_smtp_username = smtp_username
        client.email_smtp_password = smtp_password
        client.email_from_address = from_address or smtp_username
        client.email_from_name = client.company_name or "AI Assistant"
        
        client.save()
        
        print("✅ Email enabled successfully!")
        print(f"  SMTP Host: {client.email_smtp_host}")
        print(f"  Username: {client.email_smtp_username}")
        print(f"  From: {client.email_from_address}")
        
        return True
    except Client.DoesNotExist:
        print(f"❌ Client {client_id} not found")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == '__main__':
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'enable' and len(sys.argv) >= 5:
            # Usage: python check_email_status.py enable <client_id> <smtp_host> <username> <password> [from_address]
            client_id = int(sys.argv[2])
            smtp_host = sys.argv[3]
            username = sys.argv[4]
            password = sys.argv[5]
            from_addr = sys.argv[6] if len(sys.argv) > 6 else None
            
            enable_email_for_client(client_id, smtp_host, username, password, from_addr)
        else:
            print("Usage:")
            print("  Check status: python check_email_status.py")
            print("  Enable email: python check_email_status.py enable <client_id> <smtp_host> <username> <password> [from_address]")
    else:
        check_email_status()

