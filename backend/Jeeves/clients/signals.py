from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Client, ClientQRCode
import logging

logger = logging.getLogger(__name__)


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


