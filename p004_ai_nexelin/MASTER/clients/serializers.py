from rest_framework import serializers
from MASTER.clients.models import Client, ClientDocument, ClientAPIKey, KnowledgeBlock, ClientQRCode, WebParsingRequest


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

