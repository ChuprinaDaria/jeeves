from rest_framework import serializers
from MASTER.clients.models import (
    Client,
    ClientDocument,
    ClientAPIKey,
    KnowledgeBlock,
    ClientQRCode,
    WebParsingRequest,
    Prompt,
    PromptVote,
    News,
)


class ClientSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    branch_name = serializers.SerializerMethodField()
    specialization_name = serializers.SerializerMethodField()
    embedding_model_name = serializers.SerializerMethodField()
    # Sensitive Meta fields as write-only
    meta_app_secret = serializers.CharField(write_only=True, required=False, allow_blank=True)
    meta_access_token = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Client
        fields = [
            'id',
            'user',
            'branch',
            'branch_name',
            'specialization',
            'specialization_name',
            'company_name',
            'tag',
            'webchat_domain',
            'description',
            'api_key',
            'logo',
            'logo_url',
            'is_active',
            'client_type',
            'features',
            'custom_system_prompt',
            'embedding_model',
            'embedding_model_name',
            # Browser extension
            'extension_enabled',
            # Meta WhatsApp config (non-sensitive read)
            'whatsapp_meta_enabled',
            'meta_waba_id',
            'meta_app_id',
            'meta_phone_number_id',
            'meta_verify_token',
            # Sensitive write-only
            'meta_app_secret',
            'meta_access_token',
            'created_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['api_key', 'created_by', 'created_at', 'updated_at']

    def get_logo_url(self, obj):
        if obj.logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.logo.url)
            return obj.logo.url
        return None

    def get_branch_name(self, obj):
        """Safely get branch name"""
        return obj.branch.name if obj.branch else None

    def get_specialization_name(self, obj):
        """Safely get specialization name"""
        return obj.specialization.name if obj.specialization else None

    def get_embedding_model_name(self, obj):
        """Get embedding model name"""
        return obj.embedding_model.name if obj.embedding_model else None
    


class ClientDocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    knowledge_block_name = serializers.SerializerMethodField()
    file_type = serializers.ChoiceField(choices=ClientDocument.FILE_TYPES, required=False)

    class Meta:
        model = ClientDocument
        fields = [
            'id',
            'client',
            'knowledge_block',
            'knowledge_block_name',
            'title',
            'file',
            'file_url',
            'file_type',
            'file_size',
            'metadata',
            'is_processed',
            'processing_error',
            'chunks_count',
            'uploaded_at',
        ]
        read_only_fields = ['client', 'file_size', 'uploaded_at', 'is_processed', 'processing_error', 'chunks_count']

    def get_file_url(self, obj):
        """Get absolute URL for file"""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

    def get_knowledge_block_name(self, obj):
        """Get knowledge block name"""
        return obj.knowledge_block.name if obj.knowledge_block else None
    
    def validate(self, data):
        """Auto-detect file_type if not provided"""
        if 'file' in data and not data.get('file_type'):
            file = data['file']
            file_name = file.name.lower()
            
            # Map file extensions to file types
            extension_map = {
                '.pdf': 'pdf',
                '.txt': 'txt',
                '.csv': 'csv',
                '.json': 'json',
                '.docx': 'docx',
                '.doc': 'docx',
            }
            
            for ext, file_type in extension_map.items():
                if file_name.endswith(ext):
                    data['file_type'] = file_type
                    break
            
            # Default to txt if unknown
            if not data.get('file_type'):
                data['file_type'] = 'txt'
        
        return data


class ClientAPIKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientAPIKey
        fields = '__all__'


class KnowledgeBlockSerializer(serializers.ModelSerializer):
    entries_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = KnowledgeBlock
        fields = [
            'id',
            'client',
            'name',
            'description',
            'is_active',
            'is_permanent',
            'entries_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['client', 'is_permanent', 'entries_count', 'created_at', 'updated_at']


class ClientQRCodeSerializer(serializers.ModelSerializer):
    qr_code_url_display = serializers.SerializerMethodField()
    
    class Meta:
        model = ClientQRCode
        fields = [
            'id',
            'client',
            'name',
            'description',
            'location',
            'integration_type',
            'qr_code',
            'qr_code_url',
            'qr_code_url_display',
            'qr_token',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['client', 'qr_token', 'qr_code_url', 'created_at', 'updated_at']
    
    def get_qr_code_url_display(self, obj):
        """Returns QR code image URL"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Для web integration, оновлюємо location з актуальним webchat_domain
        if obj.integration_type == 'web' and obj.client:
            try:
                new_link = obj.get_web_chat_link()
                if obj.location != new_link:
                    obj.location = new_link
                    obj.save(update_fields=['location'])
            except Exception as e:
                logger.error(f"Error updating web QR code location for {obj.id}: {e}", exc_info=True)
        
        if obj.qr_code:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.qr_code.url)
            return obj.qr_code.url
        return None


class WebParsingRequestSerializer(serializers.ModelSerializer):
    knowledge_block_name = serializers.SerializerMethodField()
    
    class Meta:
        model = WebParsingRequest
        fields = [
            'id',
            'client',
            'website_url',
            'description',
            'price',
            'status',
            'path_to_documents',
            'knowledge_block',
            'knowledge_block_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['client', 'created_at', 'updated_at', 'knowledge_block', 'knowledge_block_name']
    
    def get_knowledge_block_name(self, obj):
        """Get knowledge block name"""
        return obj.knowledge_block.name if obj.knowledge_block else None
    
    def validate(self, data):
        """Client can only set website_url and description"""
        # If user is not admin, restrict fields
        request = self.context.get('request')
        if request and not (request.user.is_superuser or getattr(request.user, 'is_staff', False)):
            # Remove admin-only fields
            data.pop('price', None)
            data.pop('status', None)
            data.pop('path_to_documents', None)
        return data


class PromptSerializer(serializers.ModelSerializer):
    like_ratio = serializers.FloatField(read_only=True)
    user_vote = serializers.SerializerMethodField()
    
    class Meta:
        model = Prompt
        fields = [
            'id',
            'title',
            'category',
            'industry',
            'description',
            'prompt_template',
            'variables',
            'examples',
            'model',
            'temperature',
            'max_tokens',
            'usage_count',
            'likes_count',
            'dislikes_count',
            'like_ratio',
            'tags',
            'is_public',
            'is_featured',
            'created_by',
            'created_at',
            'updated_at',
            'user_vote',
        ]
        read_only_fields = [
            'created_by', 'created_at', 'updated_at',
            'usage_count', 'likes_count', 'dislikes_count', 'like_ratio', 'user_vote'
        ]
    
    def get_user_vote(self, obj):
        """Get current user's vote if exists"""
        request = self.context.get('request')
        if not request:
            return None
        
        # Спробуємо отримати user_identifier
        user_identifier = self._get_user_identifier(request)
        if not user_identifier:
            return None
        
        try:
            vote = PromptVote.objects.get(prompt=obj, user_identifier=user_identifier)
            return vote.vote
        except PromptVote.DoesNotExist:
            return None
    
    def _get_user_identifier(self, request):
        """Get user identifier (user ID or IP address)"""
        if request.user and request.user.is_authenticated:
            return str(request.user.id)
        # Для анонімних користувачів використовуємо IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip or 'anonymous'


class PromptVoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromptVote
        fields = ['id', 'prompt', 'vote', 'created_at']
        read_only_fields = ['id', 'created_at']


class NewsSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    
    class Meta:
        model = News
        fields = [
            'id',
            'title',
            'description',
            'news_type',
            'image_url',
            'is_active',
            'is_featured',
            'created_at',
            'updated_at',
            'related_integration',
            'related_model',
            'related_feature',
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_image_url(self, obj):
        """Return uploaded image URL if available, otherwise return image_url field"""
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return obj.image_url
    
    def get_title(self, obj):
        """Return translated title based on user's language preference"""
        request = self.context.get('request')
        if request:
            # Priority: query param > Accept-Language header
            lang = request.GET.get('lang')
            if not lang:
                # Parse Accept-Language header (e.g., "en-US,en;q=0.9,uk;q=0.8")
                accept_lang = request.META.get('HTTP_ACCEPT_LANGUAGE', 'en')
                if accept_lang:
                    lang = accept_lang.split(',')[0].split('-')[0].lower()
            
            # Normalize language code
            if lang:
                lang = lang.lower()
                # Map common variations
                lang_map = {
                    'uk': 'uk',
                    'ua': 'uk',
                    'en': 'en',
                    'de': 'de',
                    'es': 'es',
                    'fr': 'fr',
                    'it': 'it',
                    'nl': 'nl',
                    'da': 'da',
                }
                lang = lang_map.get(lang, 'en')
            
            # Check if translation exists for this language
            if obj.translations and lang in obj.translations:
                translated_title = obj.translations[lang].get('title')
                if translated_title:
                    return translated_title
        
        # Fallback to English (default)
        return obj.title
    
    def get_description(self, obj):
        """Return translated description based on user's language preference"""
        request = self.context.get('request')
        if request:
            # Priority: query param > Accept-Language header
            lang = request.GET.get('lang')
            if not lang:
                # Parse Accept-Language header
                accept_lang = request.META.get('HTTP_ACCEPT_LANGUAGE', 'en')
                if accept_lang:
                    lang = accept_lang.split(',')[0].split('-')[0].lower()
            
            # Normalize language code
            if lang:
                lang = lang.lower()
                # Map common variations
                lang_map = {
                    'uk': 'uk',
                    'ua': 'uk',
                    'en': 'en',
                    'de': 'de',
                    'es': 'es',
                    'fr': 'fr',
                    'it': 'it',
                    'nl': 'nl',
                    'da': 'da',
                }
                lang = lang_map.get(lang, 'en')
            
            # Check if translation exists for this language
            if obj.translations and lang in obj.translations:
                translated_desc = obj.translations[lang].get('description')
                if translated_desc:
                    return translated_desc
        
        # Fallback to English (default)
        return obj.description

