from django.contrib.auth.models import User
from django.db import models


class UserDashboard(models.Model):
    """
    Disposició personalitzada de la pàgina d'inici d'un usuari. `layout` és una
    llista ordenada de cards: [{"id": "<uuid>", "key": "<card>", "size": "sm|md|lg",
    "config": {...}}]. Si l'usuari no en té, es fa servir dashboard.defaults.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='dashboard')
    layout = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = "User Dashboard"
        verbose_name_plural = "User Dashboards"

    def __str__(self):
        """Return a dashboard label identifying its user."""
        return "Dashboard of {}".format(self.user_id)
