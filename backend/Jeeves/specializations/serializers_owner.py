from django.utils.text import slugify
from rest_framework import serializers

from Jeeves.branches.models import Branch
from Jeeves.EmbeddingModel.models import EmbeddingModel
from .models import Specialization


class BranchNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ['id', 'name']


class EmbeddingModelNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmbeddingModel
        fields = ['id', 'name']


class SpecializationOwnerSerializer(serializers.ModelSerializer):
    branch = BranchNestedSerializer(read_only=True)
    branch_id = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(), source='branch', write_only=True,
    )
    embedding_model = EmbeddingModelNestedSerializer(read_only=True)
    embedding_model_id = serializers.PrimaryKeyRelatedField(
        queryset=EmbeddingModel.objects.all(), source='embedding_model',
        write_only=True, required=False, allow_null=True,
    )
    documents_count = serializers.IntegerField(read_only=True, default=0)
    clients_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Specialization
        fields = [
            'id', 'name', 'slug', 'description', 'is_active',
            'custom_system_prompt',
            'branch', 'branch_id',
            'embedding_model', 'embedding_model_id',
            'documents_count', 'clients_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'documents_count', 'clients_count', 'created_at', 'updated_at']

    def create(self, validated_data):
        if not validated_data.get('slug'):
            base = slugify(validated_data.get('name', ''))
            slug = base
            counter = 2
            branch = validated_data.get('branch')
            while Specialization.objects.filter(branch=branch, slug=slug).exists():
                slug = f"{base}-{counter}"
                counter += 1
            validated_data['slug'] = slug
        return super().create(validated_data)
