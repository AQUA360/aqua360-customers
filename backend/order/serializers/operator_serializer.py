from django.db import transaction
from rest_framework import serializers
from ..models import Operator
from lecturapp.serializers import ReadingOperatorCreateSerializer
from lecturapp.models import ReadingOperator


class ReadingOperatorNestedCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating ReadingOperator with password (nested in Operator creation)"""
    
    password = serializers.CharField(write_only=True, min_length=6, required=True)
    password_confirm = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = ReadingOperator
        fields = ['name', 'surname', 'username', 'password', 'password_confirm']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Passwords don't match"})
        return attrs


class ReadingOperatorNestedUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating ReadingOperator (nested in Operator update) - password is optional"""
    
    password = serializers.CharField(write_only=True, min_length=6, required=False)
    password_confirm = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = ReadingOperator
        fields = ['name', 'surname', 'username', 'password', 'password_confirm', 'is_active']
    
    def validate(self, attrs):
        # Only validate password matching if password is provided
        password = attrs.get('password')
        password_confirm = attrs.get('password_confirm')
        
        if password or password_confirm:
            if not password or not password_confirm:
                raise serializers.ValidationError({
                    "password": "Both password and password_confirm are required when updating password"
                })
            if password != password_confirm:
                raise serializers.ValidationError({"password": "Passwords don't match"})
        
        return attrs


class OperatorCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Operator"""
    app_user = ReadingOperatorNestedCreateSerializer(required=False, allow_null=True)
    
    class Meta:
        model = Operator
        fields = '__all__'
    
    def create(self, validated_data):
        app_user_data = validated_data.pop('app_user', None)
        
        # Create the operator first
        operator = super().create(validated_data)
        
        # Handle app_user creation/assignment
        if app_user_data:
            if isinstance(app_user_data, dict):
                # Remove password_confirm as it's not a model field
                password = app_user_data.pop('password')
                app_user_data.pop('password_confirm', None)
                
                # Create new ReadingOperator
                app_user = ReadingOperator.objects.create(**app_user_data)
                app_user.set_password(password)
                app_user.save()
                
                operator.app_user = app_user
                operator.save()
            elif isinstance(app_user_data, ReadingOperator):
                # Use existing ReadingOperator
                operator.app_user = app_user_data
                operator.save()
        
        return operator


class OperatorUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Operator - password is optional"""
    # Use JSONField to accept raw dict without nested serializer validation
    app_user = serializers.JSONField(required=False, allow_null=True)
    
    class Meta:
        model = Operator
        fields = '__all__'
    
    def validate_app_user(self, value):
        """Custom validation for app_user data"""
        if value and isinstance(value, dict):
            # Validate password fields if provided
            password = value.get('password')
            password_confirm = value.get('password_confirm')
            
            if password or password_confirm:
                if not password or not password_confirm:
                    raise serializers.ValidationError({
                        "password": "Both password and password_confirm are required when updating password"
                    })
                if password != password_confirm:
                    raise serializers.ValidationError({"password": "Passwords don't match"})
                if len(password) < 6:
                    raise serializers.ValidationError({"password": "Password must be at least 6 characters"})
            
            # If we're updating an existing operator with an app_user
            if self.instance and self.instance.app_user:
                # Check if username is being changed
                username = value.get('username')
                if username and username != self.instance.app_user.username:
                    # Only validate uniqueness if username is actually changing
                    if ReadingOperator.objects.filter(username=username).exists():
                        raise serializers.ValidationError({
                            "username": "Reading Operator with this Username already exists."
                        })
            elif value.get('username'):
                # Creating new app_user, check username uniqueness
                if ReadingOperator.objects.filter(username=value.get('username')).exists():
                    raise serializers.ValidationError({
                        "username": "Reading Operator with this Username already exists."
                    })
        
        return value
    
    def update(self, instance, validated_data):
        app_user_data = validated_data.pop('app_user', None)
        
        print(f"App user data: {app_user_data}")
        
        # Update the operator first
        operator = super().update(instance, validated_data)
        
        # Handle app_user update
        if app_user_data is not None:  # Allow setting to None
            if app_user_data is None:
                # Clear the app_user
                operator.app_user = None
            elif isinstance(app_user_data, dict):
                # Extract password fields
                password = app_user_data.pop('password', None)
                app_user_data.pop('password_confirm', None)
                
                # Update or create ReadingOperator
                if operator.app_user:
                    # Update existing ReadingOperator
                    for attr, value in app_user_data.items():
                        setattr(operator.app_user, attr, value)
                    
                    # Only update password if provided
                    if password:
                        operator.app_user.set_password(password)
                    
                    operator.app_user.save()
                else:
                    # Create new ReadingOperator (password is required in this case)
                    if not password:
                        raise serializers.ValidationError({
                            "app_user": {"password": "Password is required when creating a new app user"}
                        })
                    
                    app_user = ReadingOperator.objects.create(**app_user_data)
                    app_user.set_password(password)
                    app_user.save()
                    operator.app_user = app_user
            elif isinstance(app_user_data, ReadingOperator):
                # Use existing ReadingOperator
                operator.app_user = app_user_data
            
            operator.save()
        
        return operator


class OperatorSerializer(serializers.ModelSerializer):
    """Read-only serializer for Operator"""
    app_user = ReadingOperatorNestedUpdateSerializer(required=False, allow_null=True, read_only=True)
    
    class Meta:
        model = Operator
        fields = '__all__'

