from rest_framework import serializers
from ..models import ( ACADocument, ACADocumentChange, ACADocumentStatus )

class ACADocumentChangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ACADocumentChange
        fields = '__all__'

class ACADocumentStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ACADocumentStatus
        fields = '__all__'

class ACADocumentSerializer(serializers.ModelSerializer):

    document_changes = ACADocumentChangeSerializer(many=True, read_only=True)
    status = ACADocumentStatusSerializer(read_only=True, required=False, allow_null=True)
    status_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = ACADocument
        fields = '__all__'
        
    def create(self, validated_data):
        
        ACA_document = ACADocument.objects.create(**validated_data)
        
        default_status = ACADocumentStatus.objects.filter(is_default=True).first()
        if default_status:
            ACA_document.status = default_status
            ACA_document.save()
        
        return ACA_document
    
    def update(self, instance, validated_data):
        
        status_id = validated_data.get('status_id', None)
        if status_id:
            instance.status = ACADocumentStatus.objects.get(id=status_id)
            instance.save()
        
        return instance
    
    def to_representation(self, instance):
        # Call the parent representation
        representation = super().to_representation(instance)
        
        # Override `document_changes` to order by `id`
        document_changes = instance.document_changes.order_by('id')  # Assumes a related_name of `document_changes`
        representation['document_changes'] = ACADocumentChangeSerializer(document_changes, many=True).data
        
        return representation