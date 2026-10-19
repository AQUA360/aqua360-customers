from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from auth.permissions import PermissionManager

from .cards import available_cards, get_card
from .defaults import default_layout
from .models import UserDashboard
from .serializers import LayoutSerializer, clean_layout


class DashboardLayoutView(APIView):
    """Disposició de la pàgina d'inici de l'usuari de la sessió."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return the user layout or defaults, filtered by current permissions."""
        dashboard = UserDashboard.objects.filter(user=request.user).first()
        layout = dashboard.layout if dashboard else default_layout()
        return Response({
            'layout': clean_layout(layout, user=request.user),
            'is_default': dashboard is None,
        })

    def put(self, request):
        """Validate and save the authenticated user dashboard layout."""
        serializer = LayoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dashboard, _created = UserDashboard.objects.update_or_create(
            user=request.user, defaults={'layout': serializer.validated_data['layout']},
        )
        return Response({
            'layout': clean_layout(dashboard.layout, user=request.user),
            'is_default': False,
        }, status=status.HTTP_200_OK)

    def delete(self, request):
        """Torna a la disposició per defecte."""
        UserDashboard.objects.filter(user=request.user).delete()
        return Response({
            'layout': clean_layout(default_layout(), user=request.user),
            'is_default': True,
        }, status=status.HTTP_200_OK)


class DashboardCardListView(APIView):
    """Catàleg de cards que l'usuari pot afegir segons els seus permisos."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return catalog metadata for cards the authenticated user may use."""
        return Response([card.describe() for card in available_cards(request.user)])


class DashboardCardDataView(APIView):
    """
    Dades d'una card. La configuració va als paràmetres de la URL
    (p. ex. ?period=month), i es valida contra l'esquema de la card.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, key):
        """Check card access and return data using validated configuration."""
        card = get_card(key)
        if not card or not card.has_data:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if not card.is_allowed(request.user, PermissionManager.get_user_permissions(request.user)):
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        config = card.clean_config(request.query_params.dict())
        return Response({'key': key, 'config': config, 'data': card.get_data(request.user, config)})
