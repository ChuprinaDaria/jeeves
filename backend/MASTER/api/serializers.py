from rest_framework import serializers


class RAGQuerySerializer(serializers.Serializer):
    query = serializers.CharField(max_length=1000)


class DocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    title = serializers.CharField(max_length=255)

