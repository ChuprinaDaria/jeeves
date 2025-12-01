from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Client, ClientQRCode
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Client)
def regenerate_table_qrs_on_logo_change(sender, instance: Client, created, **kwargs):
    """Regenerates QR codes for all tables when client logo changes"""
    # Check if this is a restaurant
    if instance.client_type != 'restaurant':
        return
    
    # If creating new client with logo or updating logo
    if created and instance.logo:
        # New client with logo - regenerate
        pass
    elif not created and 'logo' in (kwargs.get('update_fields') or []):
        # Logo update - regenerate
        pass
    else:
        # Other cases - don't regenerate
        return
    
    # Check if Celery is available
    try:
        from .tasks import regenerate_qrs_for_client_task
        # Call asynchronously via Celery
        client_id = getattr(instance, 'id', None)
        if client_id:
            regenerate_qrs_for_client_task.delay(client_id)
            print(f"Celery task started for client {client_id}")
    except ImportError:
        # If Celery is not available - do synchronously
        client_id = getattr(instance, 'id', None)
        print(f"Regenerating QR synchronously for client {client_id}")
        try:
            from MASTER.restaurant.models import RestaurantTable
            tables = RestaurantTable.objects.filter(client=instance)
            for table in tables:
                try:
                    table.generate_qr_code()
                    table.save(update_fields=["qr_code"])
                    print(f"QR regenerated for table {table.table_number}")
                except Exception as e:
                    print(f"Error regenerating QR code for table {table.table_number}: {e}")
        except ImportError:
            print("Restaurant app not available")


@receiver(post_save, sender=Client)
def regenerate_web_qrs_on_domain_change(sender, instance: Client, created, **kwargs):
    """Regenerates QR codes for web integration when webchat_domain changes"""
    # Check if webchat_domain was updated (не обмежуємо тільки white label)
    if created:
        # New client - no need to regenerate
        return
    
    update_fields = kwargs.get('update_fields')
    if update_fields and 'webchat_domain' not in update_fields:
        # webchat_domain was not updated
        return
    
    # Тільки якщо webchat_domain встановлений
    if not instance.webchat_domain:
        return
    
    # Regenerate all web integration QR codes for this client
    try:
        web_qr_codes = ClientQRCode.objects.filter(
            client=instance,
            integration_type='web',
            is_active=True
        )
        
        regenerated_count = 0
        for qr_code in web_qr_codes:
            try:
                # Update location with new domain
                new_link = qr_code.get_web_chat_link()
                qr_code.location = new_link
                # Regenerate QR code image
                qr_code.generate_qr_code()
                qr_code.save(update_fields=['qr_code', 'qr_code_url', 'location'])
                regenerated_count += 1
                logger.info(f"Regenerated web QR code {qr_code.id} for client {instance.id} after webchat_domain change to {instance.webchat_domain}")
            except Exception as e:
                logger.error(f"Failed to regenerate web QR code {qr_code.id}: {e}")
        
        if regenerated_count > 0:
            logger.info(f"Regenerated {regenerated_count} web QR codes for client {instance.id} after webchat_domain change")
    except Exception as e:
        logger.error(f"Error regenerating web QR codes for client {instance.id}: {e}")
