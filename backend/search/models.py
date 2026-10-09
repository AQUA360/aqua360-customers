from django.db import models
from django.contrib.auth.models import User

class History(models.Model):
    searched_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    query = models.CharField(max_length=255, null=True, blank=True)
    found = models.CharField(max_length=255, null=True, blank=True)
    entity = models.CharField(max_length=255, null=True, blank=True)
    app = models.CharField(max_length=255, null=True, blank=True)
    found_field = models.CharField(max_length=255, null=True, blank=True)
    item_id = models.CharField(max_length=255, null=True, blank=True)

    