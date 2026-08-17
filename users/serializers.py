from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User, UserProfile
from movies.models import Genre
from recommendations.models import UserPreference


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile"""
    
    class Meta:
        model = UserProfile
        fields = [
            'is_profile_public', 'show_ratings', 'show_watchlist',
            'email_notifications', 'recommendation_emails', 'min_rating_threshold',
            'exclude_adult_content', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'}
    )
    profile = UserProfileSerializer(required=False)
    favorite_genres = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        write_only=True,
        help_text="List of favorite genre names"
    )
    
    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'password', 
            'password_confirm', 'profile', 'favorite_genres'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
        }
    
    def validate_email(self, value):
        """Validate email uniqueness"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "A user with this email already exists."
            )
        return value
    
    def validate_password(self, value):
        """Validate password using Django's password validators"""
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value
    
    def validate(self, attrs):
        """Validate password confirmation"""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError(
                {"password_confirm": "Password fields didn't match."}
            )
        return attrs
    
    def create(self, validated_data):
        """Create user with profile and preferences"""
        # Remove password_confirm, profile data, and favorite_genres
        validated_data.pop('password_confirm')
        profile_data = validated_data.pop('profile', {})
        favorite_genres_data = validated_data.pop('favorite_genres', [])
        
        # Create user
        user = User.objects.create_user(**validated_data)
        
        # Update or create profile
        if profile_data:
            for attr, value in profile_data.items():
                setattr(user.userprofile, attr, value)
            user.userprofile.save()
        
        # Handle favorite genres
        if favorite_genres_data:
            # Add genres to user's favorite_genres
            genres = Genre.objects.filter(name__in=favorite_genres_data)
            user.favorite_genres.set(genres)
            
            # Create user preferences with genre weights
            genre_preferences = {}
            for genre in genres:
                genre_preferences[genre.name.lower()] = 1.0  # Default weight
            
            UserPreference.objects.create(
                user=user,
                preferred_genres=genre_preferences
            )
        else:
            # Create empty user preferences
            UserPreference.objects.create(user=user)
        
        return user


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    
    email = serializers.EmailField()
    password = serializers.CharField(
        style={'input_type': 'password'},
        trim_whitespace=False
    )
    
    def validate(self, attrs):
        """Validate and authenticate user"""
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            user = authenticate(
                request=self.context.get('request'),
                username=email,
                password=password
            )
            
            if not user:
                raise serializers.ValidationError(
                    'Unable to log in with provided credentials.',
                    code='authorization'
                )
            
            if not user.is_active:
                raise serializers.ValidationError(
                    'User account is disabled.',
                    code='authorization'
                )
            
            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError(
                'Must include "email" and "password".',
                code='authorization'
            )


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user details"""
    
    profile = UserProfileSerializer(source='userprofile', read_only=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'is_active', 'date_joined', 'last_login', 'profile'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user information"""
    
    profile = UserProfileSerializer(source='userprofile', required=False)
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'profile']
    
    def update(self, instance, validated_data):
        """Update user and profile"""
        profile_data = validated_data.pop('userprofile', {})
        
        # Update user fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update profile fields
        if profile_data:
            for attr, value in profile_data.items():
                setattr(instance.userprofile, attr, value)
            instance.userprofile.save()
        
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing password"""
    
    old_password = serializers.CharField(
        style={'input_type': 'password'},
        required=True
    )
    new_password = serializers.CharField(
        style={'input_type': 'password'},
        required=True,
        min_length=8
    )
    new_password_confirm = serializers.CharField(
        style={'input_type': 'password'},
        required=True
    )
    
    def validate_old_password(self, value):
        """Validate old password"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError(
                "Old password is incorrect."
            )
        return value
    
    def validate_new_password(self, value):
        """Validate new password"""
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value
    
    def validate(self, attrs):
        """Validate password confirmation"""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError(
                {"new_password_confirm": "Password fields didn't match."}
            )
        return attrs
    
    def save(self):
        """Save new password"""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user