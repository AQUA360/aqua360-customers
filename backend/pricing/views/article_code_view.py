from rest_framework import status
from rest_framework.decorators import action
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response

from pricing.models import (ArticleCode, LineItemType, PriceIntervalStretch, PriceVariableIntervalStretch)
from pricing.serializers.value_objects_serializer import (ArticleCodeSerializer)
from pricing.permissions import PriceRatePermission
class ArticleCodeViewSet(viewsets.ModelViewSet):
    queryset = ArticleCode.objects.all().order_by('position')
    serializer_class = ArticleCodeSerializer
    permission_classes = [IsAuthenticated, PriceRatePermission]
    
    
    @action(detail=False, methods=['post'], url_path='save-article')
    def save_article_in_object(self, request):
        
        code = request.data.get('code', None)
        stretch_id = request.data.get('stretch_id', None)
        line_item_type_id = request.data.get('line_item_type_id', None)
        article_id = request.data.get('article_id', None)
        is_fix = request.data.get('is_fix', False)
        
        article = None
        stretch = None
        line_item_type = None
        
        if article_id:
            article = ArticleCode.objects.get(id=article_id)
        if stretch_id:
            if is_fix:
                stretch = PriceVariableIntervalStretch.objects.get(id=stretch_id)
            else:
                stretch = PriceIntervalStretch.objects.get(id=stretch_id)
            stretch.article = article
            stretch.code = code
            stretch.save()
        if line_item_type_id:
            line_item_type = LineItemType.objects.get(id=line_item_type_id)
            line_item_type.article = article
            line_item_type.code = code
            line_item_type.save()
        
        return Response({"ok": True}, status=status.HTTP_200_OK, content_type='application/json')
    
    
    @action(detail=False, methods=['post'], url_path='update-positions')
    def update_positions(self, request):
        updated_positions = []
        ids = request.data

        for new_position, id in enumerate(ids):
            instance = ArticleCode.objects.filter(id=id).first()
            if instance:
                instance.position = new_position
                instance.save()
                updated_positions.append({
                    'id': instance.id,
                    'position': instance.position,
                    'name': instance.name,
                    'is_default': instance.is_default
                })

        return Response({
            "status": "positions updated",
            "updated": updated_positions
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], url_path='update-default')
    def update_default(self, request):
        updated_items = []
        id = request.data

        # Validar que el ID existeix
        if not ArticleCode.objects.filter(id=id).exists():
            return Response({
                "status": "error",
                "message": "No valid ID provided."
            }, status=status.HTTP_400_BAD_BAD_REQUEST)

        # Marcar tots els ids com a no default
        ArticleCode.objects.update(is_default=False)

        # Després marcar el que toca com a default
        default_item = ArticleCode.objects.get(id=id)
        default_item.is_default = True
        default_item.save()
        updated_items.append({
            'id': default_item.id,
            'is_default': default_item.is_default
        })

        return Response({
            "status": "is_default updated",
            "updated": updated_items
        }, status=status.HTTP_200_OK)
