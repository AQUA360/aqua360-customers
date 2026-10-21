from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import NotificationPreference


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    has_email = serializers.SerializerMethodField()

    class Meta:
        model = NotificationPreference
        fields = ['email_daily_tasks', 'has_email']

    def get_has_email(self, obj):
        """Return whether the preference owner has an email address."""
        return bool(obj.user.email)


class NotificationPreferenceView(APIView):
    """Preferències de notificació de l'usuari de la sessió (GET / PUT)."""
    permission_classes = [IsAuthenticated]

    def _preference(self, request):
        """Get or create notification preferences for the authenticated user."""
        preference, _created = NotificationPreference.objects.get_or_create(user=request.user)
        return preference

    def get(self, request):
        """Return the authenticated user notification preferences."""
        return Response(NotificationPreferenceSerializer(self._preference(request)).data)

    def put(self, request):
        """Validate and partially update the authenticated user preferences."""
        serializer = NotificationPreferenceSerializer(self._preference(request), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
