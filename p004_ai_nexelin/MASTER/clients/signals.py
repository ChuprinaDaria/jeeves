from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Client, ClientQRCode
import logging

logger = logging.getLogger(__name__)

# Import package sync functions (may fail if module not available)
try:
    from .package_sync import create_package_on_mg_async_delay, update_package_on_mg_async_delay
except ImportError:
    logger.warning("package_sync module not available, package sync to MG will be disabled")
    def create_package_on_mg_async_delay(*args, **kwargs):
        pass
    def update_package_on_mg_async_delay(*args, **kwargs):
        pass


@receiver(pre_save, sender=Client)
def capture_old_matrix_manager_ids(sender, instance: Client, **kwargs):
    """Store old matrix_manager_user_ids before save so post_save can detect new ones."""
    if instance.pk:
        try:
            old = Client.objects.filter(pk=instance.pk).values_list(
                'matrix_manager_user_ids', flat=True
            ).first()
            instance._old_matrix_manager_user_ids = old or []
        except Exception:
            instance._old_matrix_manager_user_ids = []
    else:
        instance._old_matrix_manager_user_ids = []


@receiver(post_save, sender=Client)
def onboard_new_matrix_managers(sender, instance: Client, created, **kwargs):
    """Detect newly added Matrix manager IDs and send them a welcome DM."""
    old_ids = set(getattr(instance, '_old_matrix_manager_user_ids', []))
    new_ids = set(instance.matrix_manager_user_ids or [])
    added = new_ids - old_ids

    if not added:
        return

    client_name = instance.company_name or instance.tag or str(instance.pk)
    for manager_user_id in added:
        if not manager_user_id or not manager_user_id.strip():
            continue
        try:
            from .tasks import onboard_matrix_manager
            onboard_matrix_manager.delay(instance.pk, manager_user_id.strip(), client_name)
            logger.info(f"Queued onboarding for Matrix manager {manager_user_id} (client {instance.pk})")
        except Exception as e:
            logger.error(f"Failed to queue onboarding for {manager_user_id}: {e}")


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


@receiver(post_save, sender=Client)
def sync_package_to_mg(sender, instance: Client, created, **kwargs):
    """
    Sync package to mg.nexelin when client is created or updated.
    Creates package on create, updates package on update.
    """
    try:
        # Only sync if client has tag (required for GUID)
        if not instance.tag:
            return
        
        # Check if sync is disabled for this client (using sync_usage_stats as indicator)
        # If client has disabled usage stats sync, we might also want to disable package sync
        # This can be extended with a dedicated sync_package_to_mg field if needed
        if hasattr(instance, 'sync_usage_stats') and not instance.sync_usage_stats:
            logger.debug(f"Package sync to MG skipped for client {instance.id} (sync_usage_stats is disabled)")
            # Note: We still sync packages even if usage stats are disabled, 
            # but this can be changed if needed
        
        if created:
            # Create package on MG
            logger.info(f"Creating package on MG for new client {instance.id} (tag: {instance.tag})")
            create_package_on_mg_async_delay(instance.id)
        else:
            # Update package on MG
            # Only sync if relevant fields were updated
            update_fields = kwargs.get('update_fields')
            if update_fields:
                # Check if any relevant fields were updated
                relevant_fields = {'company_name', 'description', 'is_active', 'client_type', 'tag'}
                if any(field in update_fields for field in relevant_fields):
                    logger.info(f"Updating package on MG for client {instance.id} (tag: {instance.tag})")
                    update_package_on_mg_async_delay(instance.id)
            else:
                # If update_fields is None, it means all fields might have changed
                # Sync to be safe
                logger.info(f"Updating package on MG for client {instance.id} (tag: {instance.tag})")
                update_package_on_mg_async_delay(instance.id)
    except Exception as e:
        logger.error(f"Error syncing package to MG for client {instance.id}: {e}", exc_info=True)
