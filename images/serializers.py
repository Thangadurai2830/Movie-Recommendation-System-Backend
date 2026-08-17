from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    ImageProfile, ImageUpload, ImageMetadata, ImageSettings,
    ImageLike, ImageComment, ImageShare, ImageCollection, ImageCollectionItem
)
from PIL import Image
import os


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']


class ImageProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    max_upload_size_mb = serializers.SerializerMethodField()
    
    class Meta:
        model = ImageProfile
        fields = [
            'id', 'user', 'max_upload_size', 'max_upload_size_mb', 'default_privacy',
            'auto_optimize', 'enable_notifications', 'watermark_text', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
    
    def get_max_upload_size_mb(self, obj):
        return round(obj.max_upload_size / (1024 * 1024), 1)


class ImageMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImageMetadata
        fields = [
            'id', 'camera_make', 'camera_model', 'focal_length', 'aperture',
            'iso', 'shutter_speed', 'gps_latitude', 'gps_longitude',
            'location_name', 'taken_at', 'exif_data', 'color_palette', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ImageSettingsSerializer(serializers.ModelSerializer):
    has_modifications = serializers.ReadOnlyField()
    
    class Meta:
        model = ImageSettings
        fields = [
            'id', 'brightness', 'contrast', 'saturation', 'hue', 'sharpness', 'blur',
            'filter_applied', 'crop_x', 'crop_y', 'crop_width', 'crop_height',
            'rotation', 'flip_horizontal', 'flip_vertical', 'quality',
            'watermark_enabled', 'watermark_text', 'watermark_opacity',
            'has_modifications', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'has_modifications', 'created_at', 'updated_at']
    
    def validate_brightness(self, value):
        if not -100 <= value <= 100:
            raise serializers.ValidationError("Brightness must be between -100 and 100")
        return value
    
    def validate_contrast(self, value):
        if not -100 <= value <= 100:
            raise serializers.ValidationError("Contrast must be between -100 and 100")
        return value
    
    def validate_saturation(self, value):
        if not -100 <= value <= 100:
            raise serializers.ValidationError("Saturation must be between -100 and 100")
        return value
    
    def validate_hue(self, value):
        if not -180 <= value <= 180:
            raise serializers.ValidationError("Hue must be between -180 and 180")
        return value
    
    def validate_quality(self, value):
        if not 1 <= value <= 100:
            raise serializers.ValidationError("Quality must be between 1 and 100")
        return value


class ImageUploadSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    metadata = ImageMetadataSerializer(read_only=True)
    settings = ImageSettingsSerializer(read_only=True)
    file_size_mb = serializers.SerializerMethodField()
    dimensions = serializers.SerializerMethodField()
    likes_count = serializers.ReadOnlyField()
    comments_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    
    class Meta:
        model = ImageUpload
        fields = [
            'id', 'user', 'title', 'description', 'image', 'privacy', 'status',
            'tags', 'file_size', 'file_size_mb', 'width', 'height', 'dimensions',
            'format', 'views_count', 'likes_count', 'comments_count', 'downloads_count',
            'is_featured', 'is_liked', 'metadata', 'settings', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'file_size', 'width', 'height', 'format',
            'views_count', 'likes_count', 'comments_count', 'downloads_count',
            'created_at', 'updated_at'
        ]
    
    def get_file_size_mb(self, obj):
        return round(obj.file_size / (1024 * 1024), 2) if obj.file_size else 0
    
    def get_dimensions(self, obj):
        return f"{obj.width}x{obj.height}" if obj.width and obj.height else "Unknown"
    
    def get_comments_count(self, obj):
        return obj.comments.count()
    
    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False
    
    def validate_image(self, value):
        # Validate file size (max 10MB)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Image file too large. Maximum size is 10MB.")
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError("Unsupported image format. Allowed: JPEG, PNG, GIF, WebP.")
        
        return value
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ImageUploadListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views"""
    user = serializers.StringRelatedField()
    file_size_mb = serializers.SerializerMethodField()
    dimensions = serializers.SerializerMethodField()
    likes_count = serializers.ReadOnlyField()
    is_liked = serializers.SerializerMethodField()
    
    class Meta:
        model = ImageUpload
        fields = [
            'id', 'user', 'title', 'image', 'privacy', 'status',
            'file_size_mb', 'dimensions', 'likes_count', 'views_count',
            'is_featured', 'is_liked', 'created_at'
        ]
    
    def get_file_size_mb(self, obj):
        return round(obj.file_size / (1024 * 1024), 2) if obj.file_size else 0
    
    def get_dimensions(self, obj):
        return f"{obj.width}x{obj.height}" if obj.width and obj.height else "Unknown"
    
    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False


class ImageLikeSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = ImageLike
        fields = ['id', 'user', 'image', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ImageCommentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    replies = serializers.SerializerMethodField()
    replies_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ImageComment
        fields = [
            'id', 'user', 'image', 'content', 'parent', 'replies',
            'replies_count', 'is_edited', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'is_edited', 'created_at', 'updated_at']
    
    def get_replies(self, obj):
        if obj.replies.exists():
            return ImageCommentSerializer(obj.replies.all(), many=True, context=self.context).data
        return []
    
    def get_replies_count(self, obj):
        return obj.replies.count()
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ImageShareSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    share_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ImageShare
        fields = [
            'id', 'user', 'image', 'share_type', 'recipient_email',
            'share_token', 'share_url', 'view_count', 'expires_at', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'share_token', 'share_url', 'view_count', 'created_at']
    
    def get_share_url(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(f'/shared/image/{obj.share_token}/')
        return f'/shared/image/{obj.share_token}/'
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ImageCollectionItemSerializer(serializers.ModelSerializer):
    image = ImageUploadListSerializer(read_only=True)
    
    class Meta:
        model = ImageCollectionItem
        fields = ['id', 'image', 'order', 'added_at']
        read_only_fields = ['id', 'added_at']


class ImageCollectionSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    items = ImageCollectionItemSerializer(many=True, read_only=True)
    image_count = serializers.ReadOnlyField()
    cover_image = ImageUploadListSerializer(read_only=True)
    
    class Meta:
        model = ImageCollection
        fields = [
            'id', 'user', 'name', 'description', 'cover_image', 'privacy',
            'is_featured', 'image_count', 'items', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'image_count', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ImageCollectionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for collection list views"""
    user = serializers.StringRelatedField()
    image_count = serializers.ReadOnlyField()
    cover_image = serializers.SerializerMethodField()
    
    class Meta:
        model = ImageCollection
        fields = [
            'id', 'user', 'name', 'description', 'cover_image',
            'privacy', 'is_featured', 'image_count', 'created_at', 'updated_at'
        ]
    
    def get_cover_image(self, obj):
        if obj.cover_image:
            return {
                'id': obj.cover_image.id,
                'image': obj.cover_image.image.url if obj.cover_image.image else None,
                'title': obj.cover_image.title
            }
        return None


class BulkImageActionSerializer(serializers.Serializer):
    """Serializer for bulk actions on images"""
    image_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=50
    )
    action = serializers.ChoiceField(choices=[
        ('delete', 'Delete'),
        ('privacy_public', 'Make Public'),
        ('privacy_private', 'Make Private'),
        ('privacy_friends', 'Friends Only'),
        ('feature', 'Feature'),
        ('unfeature', 'Unfeature'),
    ])
    
    def validate_image_ids(self, value):
        user = self.context['request'].user
        existing_ids = ImageUpload.objects.filter(
            id__in=value, user=user
        ).values_list('id', flat=True)
        
        if len(existing_ids) != len(value):
            raise serializers.ValidationError("Some images don't exist or you don't have permission.")
        
        return value