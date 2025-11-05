from rest_framework import serializers
from .models import (
    MenuCategory, Menu, MenuItem, MenuItemEmbedding,
    RestaurantTable, Order, OrderItem, RestaurantChat
)
from MASTER.clients.models import Client


class MenuCategorySerializer(serializers.ModelSerializer[MenuCategory]):
    items_count = serializers.IntegerField(read_only=True)
    
    class Meta:  # type: ignore[override]
        model = MenuCategory  # type: ignore[assignment]
        fields = [
            'id', 'name', 'name_translations', 'description',
            'sort_order', 'is_active', 'icon', 'items_count'
        ]
        read_only_fields = ['items_count']


class MenuSerializer(serializers.ModelSerializer[Menu]):
    document_file = serializers.FileField(write_only=True, required=False)
    document_title = serializers.CharField(write_only=True, required=False, allow_blank=True)
    file_type = serializers.ChoiceField(write_only=True, required=False, choices=[('pdf','pdf'),('txt','txt'),('csv','csv'),('json','json'),('docx','docx')])
    class Meta:  # type: ignore[override]
        model = Menu  # type: ignore[assignment]
        fields = [
            'id', 'name', 'description_text', 'document', 'document_file', 'document_title', 'file_type',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def create(self, validated_data):
        document_file = validated_data.pop('document_file', None)
        document_title = validated_data.pop('document_title', '') or ''
        file_type = validated_data.pop('file_type', None)
        menu = super().create(validated_data)
        if document_file and file_type:
            from MASTER.clients.models import ClientDocument
            doc = ClientDocument.objects.create(
                client=menu.client,
                title=document_title or (getattr(document_file, 'name', 'menu_upload')),
                file=document_file,
                file_type=file_type,
                file_size=getattr(document_file, 'size', 0),
            )
            menu.document = doc
            menu.save(update_fields=['document'])
        return menu

    def update(self, instance, validated_data):
        document_file = validated_data.pop('document_file', None)
        document_title = validated_data.pop('document_title', '') or ''
        file_type = validated_data.pop('file_type', None)
        instance = super().update(instance, validated_data)
        if document_file and file_type:
            from MASTER.clients.models import ClientDocument
            doc = ClientDocument.objects.create(
                client=instance.client,
                title=document_title or (getattr(document_file, 'name', 'menu_upload')),
                file=document_file,
                file_type=file_type,
                file_size=getattr(document_file, 'size', 0),
            )
            instance.document = doc
            instance.save(update_fields=['document'])
        return instance


class MenuItemSerializer(serializers.ModelSerializer[MenuItem]):
    category_name = serializers.SerializerMethodField()
    menu_name = serializers.SerializerMethodField()
    document_file = serializers.FileField(write_only=True, required=False)
    document_title = serializers.CharField(write_only=True, required=False, allow_blank=True)
    file_type = serializers.ChoiceField(write_only=True, required=False, choices=[('pdf','pdf'),('txt','txt'),('csv','csv'),('json','json'),('docx','docx')])
    display_price = serializers.DecimalField(
        source='get_display_price',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )

    def get_category_name(self, obj):
        """Safely get category name"""
        return obj.category.name if obj.category else None

    def get_menu_name(self, obj):
        """Safely get menu name"""
        return obj.menu.name if obj.menu else None
    
    class Meta:  # type: ignore[override]
        model = MenuItem  # type: ignore[assignment]
        fields = [
            'id', 'menu', 'menu_name', 'category', 'category_name', 'name', 'name_translations',
            'description', 'description_translations', 'price', 'discount_price',
            'display_price', 'currency', 'image', 'image_url',
            'calories', 'proteins', 'fats', 'carbs',
            'allergens', 'dietary_labels', 'ingredients',
            'cooking_time', 'spicy_level', 'wine_pairing',
            'chef_recommendation', 'popular_item',
            'is_available', 'available_from', 'available_until',
            'stock_quantity', 'tags', 'sort_order',
            'document', 'document_file', 'document_title', 'file_type'
        ]
        read_only_fields = ['category_name', 'menu_name', 'display_price']
        extra_kwargs = {
            'menu': {'required': False},
            'category': {'required': False},
        }

    def create(self, validated_data):
        document_file = validated_data.pop('document_file', None)
        document_title = validated_data.pop('document_title', '') or ''
        file_type = validated_data.pop('file_type', None)
        item = super().create(validated_data)
        if document_file and file_type:
            from MASTER.clients.models import ClientDocument
            doc = ClientDocument.objects.create(
                client=item.client,
                title=document_title or (getattr(document_file, 'name', 'menu_item_upload')),
                file=document_file,
                file_type=file_type,
                file_size=getattr(document_file, 'size', 0),
            )
            item.document = doc
            item.save(update_fields=['document'])
        return item

    def update(self, instance, validated_data):
        document_file = validated_data.pop('document_file', None)
        document_title = validated_data.pop('document_title', '') or ''
        file_type = validated_data.pop('file_type', None)
        instance = super().update(instance, validated_data)
        if document_file and file_type:
            from MASTER.clients.models import ClientDocument
            doc = ClientDocument.objects.create(
                client=instance.client,
                title=document_title or (getattr(document_file, 'name', 'menu_item_upload')),
                file=document_file,
                file_type=file_type,
                file_size=getattr(document_file, 'size', 0),
            )
            instance.document = doc
            instance.save(update_fields=['document'])
        return instance


class MenuItemCompactSerializer(serializers.ModelSerializer[MenuItem]):
    """Compact version for list views"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    menu_name = serializers.CharField(source='menu.name', read_only=True)
    display_price = serializers.DecimalField(
        source='get_display_price',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    
    class Meta:  # type: ignore[override]
        model = MenuItem  # type: ignore[assignment]
        fields = [
            'id', 'menu_name', 'category_name', 'name', 'description',
            'display_price', 'discount_price', 'currency', 'image', 'image_url',
            'dietary_labels', 'chef_recommendation',
            'is_available', 'spicy_level'
        ]


class RestaurantTableSerializer(serializers.ModelSerializer[RestaurantTable]):
    qr_code_data = serializers.SerializerMethodField()
    
    class Meta:  # type: ignore[override]
        model = RestaurantTable  # type: ignore[assignment]
        fields = [
            'id', 'table_number', 'display_name', 'capacity',
            'location', 'qr_code', 'qr_code_url', 'qr_code_data',
            'is_active', 'is_occupied', 'notes'
        ]
        read_only_fields = ['qr_code', 'qr_code_url', 'access_token']
    
    def get_qr_code_data(self, obj):
        """Return the URL that QR code points to"""
        return obj.qr_code_url if obj.qr_code_url else None


class OrderItemSerializer(serializers.ModelSerializer[OrderItem]):
    menu_item_name = serializers.CharField(source='menu_item.name', read_only=True)
    menu_item_details = MenuItemCompactSerializer(source='menu_item', read_only=True)
    
    class Meta:  # type: ignore[override]
        model = OrderItem  # type: ignore[assignment]
        fields = [
            'id', 'menu_item', 'menu_item_name', 'menu_item_details',
            'quantity', 'unit_price', 'total_price',
            'notes', 'modifiers', 'is_ready'
        ]
        read_only_fields = ['unit_price', 'total_price', 'menu_item_name']


class OrderItemCreateSerializer(serializers.ModelSerializer[OrderItem]):
    """For creating order items"""
    class Meta:  # type: ignore[override]
        model = OrderItem  # type: ignore[assignment]
        fields = ['menu_item', 'quantity', 'notes', 'modifiers']


class OrderSerializer(serializers.ModelSerializer[Order]):
    items = OrderItemSerializer(many=True, read_only=True)
    table_number = serializers.CharField(source='table.table_number', read_only=True)
    
    class Meta:  # type: ignore[override]
        model = Order  # type: ignore[assignment]
        fields = [
            'id', 'order_number', 'status', 'table', 'table_number',
            'customer_name', 'customer_phone', 'customer_email',
            'customer_language', 'subtotal', 'tax_amount',
            'discount_amount', 'total_amount', 'special_requests',
            'items', 'created_at', 'confirmed_at', 'ready_at',
            'served_at', 'paid_at', 'pos_order_id'
        ]
        read_only_fields = [
            'order_number', 'subtotal', 'total_amount',
            'created_at', 'confirmed_at', 'ready_at',
            'served_at', 'paid_at'
        ]


class OrderCreateSerializer(serializers.ModelSerializer[Order]):
    """For creating orders with items"""
    items = OrderItemCreateSerializer(many=True)
    
    class Meta:  # type: ignore[override]
        model = Order  # type: ignore[assignment]
        fields = [
            'table', 'customer_name', 'customer_phone',
            'customer_email', 'customer_language',
            'special_requests', 'items'
        ]
    
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        
        # Get client from context
        client = self.context.get('client')
        if not client:
            raise serializers.ValidationError("Client is required")
        
        # Create order
        order = Order.objects.create(client=client, **validated_data)
        
        # Create order items
        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)
        
        # Calculate totals
        order.calculate_total()
        
        return order


class OrderStatusUpdateSerializer(serializers.Serializer):
    """For updating order status"""
    status = serializers.ChoiceField(choices=Order.STATUS_CHOICES)
    
    def update(self, instance, validated_data):
        from django.utils import timezone
        
        new_status = validated_data['status']
        instance.status = new_status
        
        # Update timestamps based on status
        if new_status == Order.STATUS_CONFIRMED:
            instance.confirmed_at = timezone.now()
        elif new_status == Order.STATUS_READY:
            instance.ready_at = timezone.now()
        elif new_status == Order.STATUS_SERVED:
            instance.served_at = timezone.now()
        elif new_status == Order.STATUS_PAID:
            instance.paid_at = timezone.now()
        
        instance.save()
        return instance


class RestaurantChatSerializer(serializers.ModelSerializer[RestaurantChat]):
    class Meta:  # type: ignore[override]
        model = RestaurantChat  # type: ignore[assignment]
        fields = [
            'id', 'session_id', 'role', 'message',
            'language', 'context_metadata', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class RestaurantChatRequestSerializer(serializers.Serializer):
    """For chat requests"""
    message = serializers.CharField(max_length=2000)
    session_id = serializers.CharField(max_length=100)
    table_id = serializers.IntegerField(required=False, allow_null=True)
    language = serializers.CharField(max_length=10, default='uk')
    order_id = serializers.IntegerField(required=False, allow_null=True)


class RestaurantChatResponseSerializer(serializers.Serializer):
    """For chat responses"""
    response = serializers.CharField()
    suggested_items = MenuItemCompactSerializer(many=True, required=False)
    context_payload = serializers.JSONField(required=False)
    session_id = serializers.CharField()


class MenuSearchSerializer(serializers.Serializer):
    """For menu search requests"""
    query = serializers.CharField(max_length=500)
    language = serializers.CharField(max_length=10, default='uk')
    category_id = serializers.IntegerField(required=False, allow_null=True)
    dietary_filters = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    allergen_exclude = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    max_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True
    )
    min_calories = serializers.IntegerField(required=False, allow_null=True)
    max_calories = serializers.IntegerField(required=False, allow_null=True)


class WebhookConfigSerializer(serializers.Serializer):
    """For configuring POS webhook"""
    webhook_url = serializers.URLField(required=False, allow_blank=True)
    webhook_enabled = serializers.BooleanField(default=False)
    webhook_headers = serializers.JSONField(required=False, default=dict)

