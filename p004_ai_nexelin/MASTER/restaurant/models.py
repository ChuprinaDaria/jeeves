from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from pgvector.django import VectorField
from MASTER.clients.models import Client, ClientDocument
from MASTER.EmbeddingModel.models import EmbeddingModel
import qrcode
import io
from django.core.files.base import ContentFile
from PIL import Image
import secrets
from django.db.models.signals import post_save
from django.dispatch import receiver
from typing import List, Dict, Any, Optional
from datetime import timedelta
from MASTER.processing.embedding_service import EmbeddingService


class MenuCategory(models.Model):
    """Categories for menu items (e.g., Appetizers, Main Courses, Desserts)"""
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='menu_categories',
        limit_choices_to={'client_type': 'restaurant'}
    )
    name = models.CharField(max_length=100)
    name_translations = models.JSONField(default=dict, blank=True, help_text='{"en": "Appetizers", "uk": "Закуски"}')
    description = models.TextField(blank=True)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    icon = models.CharField(max_length=50, blank=True, help_text='Emoji or icon class')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Menu Category'
        verbose_name_plural = 'Menu Categories'
        ordering = ['sort_order', 'name']
        unique_together = [['client', 'name']]
    
    def __str__(self):
        return f"{self.client.company_name} - {self.name}"


class Menu(models.Model):
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='menus',
        limit_choices_to={'client_type': 'restaurant'}
    )
    name = models.CharField(max_length=200)
    description_text = models.TextField(blank=True)
    document = models.ForeignKey(
        ClientDocument,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='linked_menus'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Menu'
        verbose_name_plural = 'Menus'
        ordering = ['name']
        unique_together = [['client', 'name']]

    def __str__(self):
        return f"{self.client.company_name} - {self.name}"


class MenuItem(models.Model):
    """Individual menu items with full details"""
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='menu_items',
        limit_choices_to={'client_type': 'restaurant'}
    )
    menu = models.ForeignKey('Menu', on_delete=models.CASCADE, related_name='items', null=True, blank=True)
    document = models.ForeignKey(
        ClientDocument,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='linked_menu_items'
    )
    category = models.ForeignKey(MenuCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='items')
    
    # Basic info
    name = models.CharField(max_length=200)
    name_translations = models.JSONField(default=dict, blank=True)
    description = models.TextField()
    description_translations = models.JSONField(default=dict, blank=True)
    
    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default='UAH')
    
    # Media
    image = models.ImageField(upload_to='restaurant/menu/%Y/%m/', blank=True, null=True)
    image_url = models.URLField(blank=True, help_text='External image URL if not uploading')
    
    # Nutritional info
    calories = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    proteins = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    fats = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    carbs = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    
    # Allergens and dietary
    allergens = models.JSONField(
        default=list,
        blank=True,
        help_text='List of allergens: ["gluten", "dairy", "nuts", "shellfish", "eggs", "soy"]'
    )
    dietary_labels = models.JSONField(
        default=list,
        blank=True,
        help_text='["vegetarian", "vegan", "gluten-free", "halal", "kosher"]'
    )
    
    # Additional info
    ingredients = models.TextField(blank=True, help_text='Detailed ingredients list')
    cooking_time = models.IntegerField(null=True, blank=True, help_text='Preparation time in minutes')
    spicy_level = models.IntegerField(default=0, validators=[MinValueValidator(0)], help_text='0-5 scale')
    
    # Wine pairing and recommendations
    wine_pairing = models.TextField(blank=True)
    chef_recommendation = models.BooleanField(default=False)
    popular_item = models.BooleanField(default=False)
    
    # Availability
    is_available = models.BooleanField(default=True)
    available_from = models.TimeField(null=True, blank=True)
    available_until = models.TimeField(null=True, blank=True)
    stock_quantity = models.IntegerField(null=True, blank=True, help_text='For limited items')
    
    # Metadata
    tags = models.JSONField(default=list, blank=True, help_text='["signature", "seasonal", "new"]')
    sort_order = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Menu Item'
        verbose_name_plural = 'Menu Items'
        ordering = ['menu', 'category', 'sort_order', 'name']
        indexes = [
            models.Index(fields=['client', 'is_available']),
            models.Index(fields=['category', 'is_available']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.price} {self.currency}"
    
    def get_display_price(self):
        """Return discount price if available, otherwise regular price"""
        return self.discount_price if self.discount_price else self.price


class MenuItemEmbedding(models.Model):
    """Vector embeddings for menu items to enable semantic search"""
    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.CASCADE,
        related_name='embeddings'
    )
    embedding_model = models.ForeignKey(
        EmbeddingModel,
        on_delete=models.PROTECT,
        related_name='menu_embeddings'
    )
    
    # Fixed at 1536 dimensions (pgvector limit <= 2000; matches text-embedding-3-small)
    vector = VectorField(dimensions=1536, null=True, blank=True)
    content = models.TextField(help_text='Combined searchable content from menu item')
    language = models.CharField(max_length=10, default='uk', help_text='Language of the content')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Menu Item Embedding'
        verbose_name_plural = 'Menu Item Embeddings'
        unique_together = [['menu_item', 'embedding_model', 'language']]
        indexes = [
            models.Index(fields=['menu_item']),
            models.Index(fields=['language']),
        ]
    
    def save(self, *args, **kwargs):
        # Pad vector to 1536 dimensions if needed
        if self.vector is not None and self.embedding_model:
            actual_dim = len(self.vector)
            if actual_dim > 1536:
                raise ValidationError(f"Vector dimensions exceed maximum: {actual_dim} > 1536")
            if actual_dim < 1536:
                self.vector = list(self.vector) + [0.0] * (1536 - actual_dim)
        super().save(*args, **kwargs)


@receiver(post_save, sender=MenuItem)
def enqueue_menu_item_embedding(sender, instance: MenuItem, created: bool, **kwargs):  # type: ignore[name-defined]
    """Enqueue background job to generate/update embedding (Celery)."""
    try:
        from MASTER.restaurant.tasks import process_menu_item_embedding  # local import to avoid circular
        process_menu_item_embedding.delay(int(instance.pk))
    except Exception:
        # Avoid blocking saves if Celery is not running in dev
        pass


class RestaurantTable(models.Model):
    """Restaurant tables with QR codes for WhatsApp integration"""
    id = models.AutoField(primary_key=True)  # Explicitly declare id field for type checking
    
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='restaurant_tables',
        limit_choices_to={'client_type': 'restaurant'},
        verbose_name='Restaurant'
    )
    
    table_number = models.CharField(
        max_length=20,
        verbose_name='Table Number',
        help_text='Table number (e.g., "5", "VIP-1", "Terrace-3")'
    )
    
    display_name = models.CharField(
        max_length=100, 
        blank=True,
        verbose_name='Display Name',
        help_text='Display name for the table'
    )
    
    capacity = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Capacity',
        help_text='Number of seats at the table'
    )
    
    location = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name='Location',
        help_text='e.g., "Main Hall", "Terrace", "VIP Room"'
    )
    
    # QR Code
    qr_code = models.ImageField(
        upload_to='restaurant/qr_codes/', 
        blank=True, 
        null=True,
        verbose_name='QR Code',
        help_text='QR code for customer scanning'
    )
    
    qr_code_url = models.URLField(
        blank=True, 
        editable=False,
        verbose_name='QR Code URL'
    )
    
    access_token = models.CharField(
        max_length=64, 
        unique=True, 
        editable=False,
        verbose_name='Access Token'
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        verbose_name='Active',
        help_text='Whether the table is available for orders'
    )
    
    is_occupied = models.BooleanField(
        default=False,
        verbose_name='Occupied',
        help_text='Whether the table is currently occupied'
    )
    
    # Metadata
    notes = models.TextField(
        blank=True,
        verbose_name='Notes',
        help_text='Additional notes about the table'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Created At'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Updated At'
    )
    
    class Meta:
        verbose_name = 'Restaurant Table'
        verbose_name_plural = 'Restaurant Tables'
        ordering = ['table_number']
        unique_together = [['client', 'table_number']]
        indexes = [
            models.Index(fields=['client', 'is_active']),
            models.Index(fields=['table_number']),
        ]
    
    def __str__(self):
        return f"{self.client.company_name} - Table {self.table_number}"
    
    def get_whatsapp_prefill(self) -> str:
        """Returns prefill text for WhatsApp"""
        c = self.client
        # Get parameters from restaurant
        branch_slug = 'demo'
        specialization_slug = 'restaurant'
        client_token = f"client-{c.id}"
        
        if hasattr(c, 'specialization') and c.specialization:
            branch_slug = getattr(c.specialization.branch, 'slug', 'demo')
            specialization_slug = getattr(c.specialization, 'slug', 'restaurant')
        
        # Get client_token from API key
        api_key = c.api_keys.filter(is_active=True).first()
        if api_key:
            client_token = api_key.key
        
        from MASTER.clients.qr_utils import build_start2_prefill
        return build_start2_prefill(branch_slug, specialization_slug, client_token, str(self.table_number))
    
    def get_whatsapp_link(self) -> str:
        """Returns WhatsApp deep link for this table"""
        from MASTER.clients.qr_utils import build_wa_me_link
        return build_wa_me_link(self.get_whatsapp_prefill())
    
    def generate_qr_code(self):
        """Generate QR code with WhatsApp deep link and restaurant logo"""
        if not self.client:
            raise ValidationError("Cannot generate QR code without restaurant")
        
        link = self.get_whatsapp_link()
        logo_path = self.client.logo.path if getattr(self.client, "logo", None) and self.client.logo else None
        
        from MASTER.clients.qr_utils import render_qr_with_logo, save_qr_png_to_field
        png = render_qr_with_logo(link, logo_path)
        fname = f"table_{self.pk}.png" if self.pk else f"table_tmp_{self.client.id}_{self.table_number}.png"
        save_qr_png_to_field(self, "qr_code", png, fname)
        self.qr_code_url = link
    
    def save(self, *args, **kwargs):
        # Generate access token if not exists
        if not self.access_token:
            self.access_token = secrets.token_urlsafe(32)
        
        # Generate QR code if not exists
        if not self.qr_code and not self.qr_code_url:
            self.generate_qr_code()
        
        super().save(*args, **kwargs)
    
    @property
    def whatsapp_url(self) -> str:
        """Property for getting WhatsApp URL"""
        return self.get_whatsapp_link()
    
    def get_conversations_count(self) -> int:
        """Returns number of conversations for this table"""
        return RestaurantConversation.objects.filter(table=self).count()
    
    def get_active_conversations_count(self) -> int:
        """Returns number of active conversations for this table"""
        return RestaurantConversation.objects.filter(table=self, is_active=True).count()


class Order(models.Model):
    """Customer orders from tables"""
    STATUS_PENDING = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_PREPARING = 'preparing'
    STATUS_READY = 'ready'
    STATUS_SERVED = 'served'
    STATUS_PAID = 'paid'
    STATUS_CANCELLED = 'cancelled'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_PREPARING, 'Preparing'),
        (STATUS_READY, 'Ready'),
        (STATUS_SERVED, 'Served'),
        (STATUS_PAID, 'Paid'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]
    
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='restaurant_orders'
    )
    table = models.ForeignKey(
        RestaurantTable,
        on_delete=models.SET_NULL,
        null=True,
        related_name='orders'
    )
    
    # Order details
    order_number = models.CharField(max_length=20, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    
    # Customer info (optional)
    customer_name = models.CharField(max_length=100, blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_language = models.CharField(max_length=10, default='uk')
    
    # Financial
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Special requests
    special_requests = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    served_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    # Integration
    pos_order_id = models.CharField(max_length=100, blank=True, help_text='External POS system order ID')
    webhook_sent = models.BooleanField(default=False)
    webhook_response = models.JSONField(default=dict, blank=True)
    
    class Meta:
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['table', 'status']),
            models.Index(fields=['order_number']),
        ]
    
    def __str__(self):
        return f"Order {self.order_number} - Table {self.table.table_number if self.table else 'N/A'}"
    
    def save(self, *args, **kwargs):
        # Generate order number if not exists
        if not self.order_number:
            import datetime
            timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            # Keep total length <= 20: 'ORD' (3) + timestamp (14) + suffix (2) = 19
            random_suffix = secrets.token_hex(1).upper()
            self.order_number = f"ORD{timestamp}{random_suffix}"
        
        super().save(*args, **kwargs)
    
    def calculate_total(self):
        """Calculate total from order items"""
        items_qs = getattr(self, 'items', None)
        self.subtotal = sum(item.total_price for item in items_qs.all()) if items_qs is not None else 0
        self.total_amount = self.subtotal + self.tax_amount - self.discount_amount
        self.save()


class OrderItem(models.Model):
    """Individual items in an order"""
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )
    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.PROTECT,
        related_name='order_items'
    )
    
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Customizations
    notes = models.TextField(blank=True, help_text='e.g., "No onions", "Extra spicy"')
    modifiers = models.JSONField(default=list, blank=True, help_text='["extra cheese", "no ice"]')
    
    # Status
    is_ready = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.quantity}x {self.menu_item.name}"
    
    def save(self, *args, **kwargs):
        # Calculate total price
        if not self.unit_price:
            self.unit_price = self.menu_item.get_display_price()
        self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)


class RestaurantConversation(models.Model):
    """WhatsApp conversation history for restaurants"""
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='restaurant_conversations',
        verbose_name='Restaurant'
    )
    
    table = models.ForeignKey(
        RestaurantTable,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations',
        verbose_name='Table',
        help_text='Table where the conversation started (can be empty)'
    )
    
    customer_phone = models.CharField(
        max_length=20,
        verbose_name='Customer Phone',
        help_text='Customer phone number in format +380671234567'
    )
    
    messages = models.JSONField(
        default=list,
        verbose_name='Messages',
        help_text='List of messages in JSON format'
    )
    
    started_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Conversation Start'
    )
    
    ended_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Conversation End',
        help_text='Time when conversation ended (null if active)'
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='Active',
        help_text='Whether conversation is active (less than 24 hours without messages)'
    )
    
    total_messages = models.IntegerField(
        default=0,
        verbose_name='Total Messages',
        help_text='Number of messages in conversation'
    )
    
    # Session tracking for compatibility
    session_id = models.CharField(
        max_length=100, 
        db_index=True,
        blank=True,
        verbose_name='Session ID'
    )
    
    # Language
    language = models.CharField(
        max_length=10, 
        default='uk',
        verbose_name='Language'
    )
    
    # Context (what menu items were discussed, etc.)
    context_metadata = models.JSONField(
        default=dict, 
        blank=True,
        verbose_name='Context Metadata'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Created At'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Updated At'
    )

    class Meta:
        verbose_name = 'Restaurant Conversation'
        verbose_name_plural = 'Restaurant Conversations'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['client', 'customer_phone']),
            models.Index(fields=['table']),
            models.Index(fields=['started_at']),
            models.Index(fields=['is_active']),
            models.Index(fields=['session_id', 'created_at']),
        ]

    def __str__(self) -> str:
        table_info = f" - Table {self.table.table_number}" if self.table else ""
        return f"{self.client.company_name} - {self.customer_phone}{table_info} - {self.started_at.strftime('%d.%m.%Y %H:%M')}"

    def add_message(self, role: str, content: str) -> None:
        """Adds a message to the conversation"""
        if role not in ['user', 'assistant']:
            raise ValidationError("Role must be 'user' or 'assistant'")
        
        if not content.strip():
            raise ValidationError("Message content cannot be empty")
        
        message = {
            'role': role,
            'content': content.strip(),
            'timestamp': timezone.now().isoformat()
        }
        
        if not self.messages:
            self.messages = []
        
        self.messages.append(message)
        self.total_messages = len(self.messages)
        self.updated_at = timezone.now()
        
        # Update activity status
        self._update_activity_status()
        
        self.save(update_fields=['messages', 'total_messages', 'updated_at', 'is_active'])

    def get_last_messages(self, n: int = 10) -> List[Dict[str, Any]]:
        """Returns last N messages"""
        if not self.messages:
            return []
        return self.messages[-n:] if n > 0 else self.messages

    def end_conversation(self) -> None:
        """Ends the conversation"""
        self.ended_at = timezone.now()
        self.is_active = False
        self.save(update_fields=['ended_at', 'is_active'])

    def get_duration(self) -> Optional[timedelta]:
        """Returns conversation duration as timedelta"""
        if not self.ended_at:
            return None
        return self.ended_at - self.started_at

    def get_duration_hours(self) -> Optional[float]:
        """Returns conversation duration in hours as float"""
        duration = self.get_duration()
        if duration is None:
            return None
        return duration.total_seconds() / 3600

    def _update_activity_status(self) -> None:
        """Updates conversation activity status"""
        if self.ended_at:
            self.is_active = False
            return
        
        # Conversation is considered active if last message was less than 24 hours ago
        if self.messages:
            from datetime import datetime
            last_message_time = datetime.fromisoformat(
                self.messages[-1]['timestamp'].replace('Z', '+00:00')
            )
            time_since_last_message = timezone.now() - last_message_time
            self.is_active = time_since_last_message < timedelta(hours=24)
        else:
            # If no messages, conversation is inactive
            self.is_active = False

    def clean(self) -> None:
        """Model validation"""
        super().clean()
        
        if not self.customer_phone:
            raise ValidationError("Customer phone is required")
        
        # Basic phone format validation
        phone = self.customer_phone.strip()
        if not phone.startswith('+') or len(phone) < 8:
            raise ValidationError("Phone must be in format +1234567890")
        
        if self.table and self.table.client != self.client:
            raise ValidationError("Table must belong to the same restaurant")

    def save(self, *args, **kwargs) -> None:
        """Override save for validation and status update"""
        self.clean()
        self._update_activity_status()
        super().save(*args, **kwargs)


# Keep RestaurantChat as alias for backward compatibility
RestaurantChat = RestaurantConversation


class TableStatistics(models.Model):
    """Aggregated statistics for tables per day"""
    
    table = models.ForeignKey(
        RestaurantTable,
        on_delete=models.CASCADE,
        related_name='statistics',
        verbose_name='Table'
    )
    
    date = models.DateField(
        verbose_name='Date',
        help_text='Date for which statistics are collected'
    )
    
    total_conversations = models.IntegerField(
        default=0,
        verbose_name='Total Conversations',
        help_text='Number of conversations per day'
    )
    
    total_messages = models.IntegerField(
        default=0,
        verbose_name='Total Messages',
        help_text='Number of messages per day'
    )
    
    total_duration_hours = models.FloatField(
        default=0.0,
        verbose_name='Dialog Hours',
        help_text='Total duration of conversations in hours'
    )
    
    unique_customers = models.IntegerField(
        default=0,
        verbose_name='Unique Customers',
        help_text='Number of unique customers per day'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Created At'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Updated At'
    )

    class Meta:
        verbose_name = 'Table Statistics'
        verbose_name_plural = 'Table Statistics'
        unique_together = [['table', 'date']]
        ordering = ['-date']
        indexes = [
            models.Index(fields=['table', 'date']),
            models.Index(fields=['date']),
        ]

    def __str__(self) -> str:
        return f"{self.table} - {self.date} - {self.total_duration_hours:.1f}h"

    @classmethod
    def calculate_for_table(cls, table, date) -> 'TableStatistics':
        """Calculates statistics for a day for a specific table"""
        from django.db.models import Count, Sum, Q
        from django.utils import timezone
        from datetime import datetime
        
        # Get all conversations for the table on the date
        start_of_day = datetime.combine(date, datetime.min.time())
        end_of_day = datetime.combine(date, datetime.max.time())
        
        conversations = RestaurantConversation.objects.filter(
            table=table,
            started_at__date=date
        )
        
        # Calculate metrics
        total_conversations = conversations.count()
        total_messages = conversations.aggregate(
            total=Sum('total_messages')
        )['total'] or 0
        
        total_duration_hours = sum(
            conv.get_duration_hours() or 0 
            for conv in conversations 
            if conv.get_duration_hours() is not None
        )
        
        unique_customers = conversations.values('customer_phone').distinct().count()
        
        # Create or update statistics
        stats, created = cls.objects.get_or_create(
            table=table,
            date=date,
            defaults={
                'total_conversations': total_conversations,
                'total_messages': total_messages,
                'total_duration_hours': total_duration_hours,
                'unique_customers': unique_customers,
            }
        )
        
        if not created:
            # Update existing statistics
            stats.total_conversations = total_conversations
            stats.total_messages = total_messages
            stats.total_duration_hours = total_duration_hours
            stats.unique_customers = unique_customers
            stats.save()
        
        return stats

    @classmethod
    def calculate_for_month(cls, table, year: int, month: int) -> Dict[str, Any]:
        """Calculates statistics for a month for a table"""
        from django.db.models import Sum, Avg, Count
        from calendar import monthrange
        from datetime import date
        
        # Get all days of the month
        start_date = date(year, month, 1)
        end_date = date(year, month, monthrange(year, month)[1])
        
        # Get monthly statistics
        monthly_stats = cls.objects.filter(
            table=table,
            date__range=[start_date, end_date]
        ).aggregate(
            total_conversations=Sum('total_conversations'),
            total_messages=Sum('total_messages'),
            total_duration_hours=Sum('total_duration_hours'),
            avg_duration_hours=Avg('total_duration_hours'),
            total_unique_customers=Sum('unique_customers'),
            active_days=Count('id')
        )
        
        return {
            'table': table,
            'year': year,
            'month': month,
            'total_conversations': monthly_stats['total_conversations'] or 0,
            'total_messages': monthly_stats['total_messages'] or 0,
            'total_duration_hours': monthly_stats['total_duration_hours'] or 0.0,
            'avg_duration_hours': monthly_stats['avg_duration_hours'] or 0.0,
            'total_unique_customers': monthly_stats['total_unique_customers'] or 0,
            'active_days': monthly_stats['active_days'] or 0,
        }

    def clean(self) -> None:
        """Model validation"""
        super().clean()
        
        if not self.table:
            raise ValidationError("Table is required")
        
        if not self.date:
            raise ValidationError("Date is required")
        
        if self.total_conversations < 0:
            raise ValidationError("Number of conversations cannot be negative")
        
        if self.total_messages < 0:
            raise ValidationError("Number of messages cannot be negative")
        
        if self.total_duration_hours < 0:
            raise ValidationError("Duration cannot be negative")
        
        if self.unique_customers < 0:
            raise ValidationError("Number of unique customers cannot be negative")