from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.core.exceptions import ValidationError
import re
import uuid
from django.utils import timezone
from datetime import timedelta

# Create your models here.

class ReadingOperator(models.Model):
    name = models.CharField(max_length=100, verbose_name="Name")
    surname = models.CharField(max_length=100, verbose_name="Surname")
    username = models.CharField(max_length=50, unique=True, verbose_name="Username")
    password = models.CharField(max_length=255, verbose_name="Password")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created at")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated at")

    class Meta:
        verbose_name = "Reading Operator"
        verbose_name_plural = "Reading Operators"
        db_table = 'lecturapp_reading_operator'

    def __str__(self):
        return f"{self.name} {self.surname} ({self.username})"

    def save(self, *args, **kwargs):
        # Hash password only if it's not already hashed
        if self.password and not self.password.startswith('pbkdf2_sha256$'):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)

    def set_password(self, raw_password):
        """Set password with encryption"""
        self.password = make_password(raw_password)
        self.save(update_fields=['password'])

    def check_password(self, raw_password):
        """Check if the provided password matches the stored hash"""
        return check_password(raw_password, self.password)

    def clean(self):
        """Validate the model"""
        super().clean()
        
        # Validate username format (alphanumeric and underscore only)
        if self.username and not re.match(r'^[a-zA-Z0-9_]+$', self.username):
            raise ValidationError({
                'username': 'Username can only contain letters, numbers, and underscores.'
            })
        
        # Validate username length
        if self.username and len(self.username) < 3:
            raise ValidationError({
                'username': 'Username must be at least 3 characters long.'
            })

    @classmethod
    def authenticate(cls, username, password):
        """Authenticate a user with username and password"""
        try:
            operator = cls.objects.get(username=username, is_active=True)
            print(f"Operator: {operator}")
            print(f"Password: {password}")
            print(f"Operator password: {operator.password}")
            print(f"Operator check password: {operator.check_password(password)}")
            if operator.check_password(password):
                return operator
        except cls.DoesNotExist:
            pass
        return None

    def generate_token(self):
        """Generate a new token for this operator"""
        # Delete any existing tokens for this operator
        Token.objects.filter(operator=self).delete()
        
        # Create a new token with 60 days expiration
        token = Token.objects.create(
            operator=self,
            token=str(uuid.uuid4()),
            created_at=timezone.now(),
            expiration_date=timezone.now() + timedelta(days=60)
        )
        return token


class Token(models.Model):
    """Token model for authentication"""
    operator = models.ForeignKey(ReadingOperator, on_delete=models.CASCADE, related_name='tokens')
    token = models.CharField(max_length=255, unique=True, verbose_name="Token")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created at")
    expiration_date = models.DateTimeField(verbose_name="Expiration date", null=True, blank=True)

    class Meta:
        verbose_name = "Authentication Token"
        verbose_name_plural = "Authentication Tokens"
        db_table = 'lecturapp_token'

    def __str__(self):
        return f"Token for {self.operator.username}"

    def is_expired(self):
        """Check if the token is expired"""
        if self.expiration_date is None:
            return True  # Treat tokens without expiration date as expired
        return timezone.now() > self.expiration_date

    def extend_expiration(self):
        """Extend the token expiration by 60 days from now"""
        self.expiration_date = timezone.now() + timedelta(days=60)
        self.save(update_fields=['expiration_date'])

    @classmethod
    def get_operator_from_token(cls, token_string):
        """Get operator from token string and extend expiration if valid"""
        try:
            token = cls.objects.get(token=token_string)
            
            # Check if token is expired
            if token.is_expired():
                return None
            
            # Extend the token expiration by 60 days
            token.extend_expiration()
            
            return token.operator
        except cls.DoesNotExist:
            return None
