from rest_framework import serializers
from MASTER.clients.models import Client, ClientDocument, ClientAPIKey, KnowledgeBlock, ClientQRCode


class ClientSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    branch_name = serializers.SerializerMethodField()
    specialization_name = serializers.SerializerMethodField()
    embedding_model_name = serializers.SerializerMethodField()

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
        read_only_fields = ['uploaded_at', 'is_processed', 'processing_error', 'chunks_count']

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

