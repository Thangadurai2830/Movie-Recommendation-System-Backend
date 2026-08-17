from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import (
    Notification,
    NotificationSettings,
    NotificationTemplate,
    NotificationBatch,
    NotificationDelivery,
    NotificationType,
    NotificationPriority
)

User = get_user_model()

class NotificationSerializer(serializers.ModelSerializer):
    """
    Serializer for Notification model
    """
    age_in_hours = serializers.ReadOnlyField()
    is_expired = serializers.ReadOnlyField()
    user_username = serializers.CharField(source='user.username', read_only=True)
    content_object_repr = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'user_username', 'title', 'message',
            'notification_type', 'priority', 'is_read', 'is_deleted',
            'data', 'action_url', 'action_text', 'content_type',
            'object_id', 'content_object_repr', 'created_at', 'updated_at',
            'read_at', 'expires_at', 'age_in_hours', 'is_expired'
        ]
        read_only_fields = [
            'id', 'user', 'user_username', 'created_at', 'updated_at',
            'age_in_hours', 'is_expired', 'content_object_repr'
        ]
    
    def get_content_object_repr(self, obj):
        """
        Get string representation of the related content object
        """
        if obj.content_object:
            return str(obj.content_object)
        return None
    
    def to_representation(self, instance):
        """
        Customize the representation of the notification
        """
        data = super().to_representation(instance)
        
        # Add human-readable labels
        data['notification_type_display'] = instance.get_notification_type_display()
        data['priority_display'] = instance.get_priority_display()
        
        # Format timestamps
        if instance.created_at:
            data['created_at_formatted'] = instance.created_at.strftime('%Y-%m-%d %H:%M:%S')
        if instance.read_at:
            data['read_at_formatted'] = instance.read_at.strftime('%Y-%m-%d %H:%M:%S')
        
        # Add relative time
        now = timezone.now()
        time_diff = now - instance.created_at
        
        if time_diff.days > 0:
            data['time_ago'] = f"{time_diff.days} day{'s' if time_diff.days > 1 else ''} ago"
        elif time_diff.seconds > 3600:
            hours = time_diff.seconds // 3600
            data['time_ago'] = f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif time_diff.seconds > 60:
            minutes = time_diff.seconds // 60
            data['time_ago'] = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            data['time_ago'] = "Just now"
        
        return data

class NotificationCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating notifications
    """
    class Meta:
        model = Notification
        fields = [
            'user', 'title', 'message', 'notification_type', 'priority',
            'data', 'action_url', 'action_text', 'content_type',
            'object_id', 'expires_at'
        ]
    
    def validate_user(self, value):
        """
        Validate that the user exists and is active
        """
        if not value.is_active:
            raise serializers.ValidationError("Cannot send notification to inactive user.")
        return value
    
    def validate_expires_at(self, value):
        """
        Validate that expiration date is in the future
        """
        if value and value <= timezone.now():
            raise serializers.ValidationError("Expiration date must be in the future.")
        return value
    
    def create(self, validated_data):
        """
        Create notification with additional validation
        """
        user = validated_data['user']
        notification_type = validated_data['notification_type']
        
        # Check user's notification settings
        try:
            settings = user.notification_settings
            if not settings.enabled:
                raise serializers.ValidationError("User has disabled notifications.")
            
            if not settings.is_notification_type_enabled(notification_type):
                raise serializers.ValidationError(
                    f"User has disabled {notification_type} notifications."
                )
            
            if settings.is_quiet_hours():
                # Store for later delivery or skip based on settings
                validated_data['data'] = validated_data.get('data', {})
                validated_data['data']['delayed_due_to_quiet_hours'] = True
        
        except NotificationSettings.DoesNotExist:
            # Create default settings if they don't exist
            NotificationSettings.objects.create(user=user)
        
        return super().create(validated_data)

class NotificationSettingsSerializer(serializers.ModelSerializer):
    """
    Serializer for NotificationSettings model
    """
    class Meta:
        model = NotificationSettings
        fields = [
            'enabled', 'sound_enabled', 'desktop_notifications',
            'email_notifications', 'push_notifications',
            'recommendations_enabled', 'social_enabled', 'achievements_enabled',
            'system_enabled', 'trending_enabled', 'watchlist_enabled',
            'rating_enabled', 'review_enabled', 'friend_enabled',
            'marketing_enabled', 'quiet_hours_start', 'quiet_hours_end',
            'max_notifications_per_hour', 'digest_frequency',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def validate_max_notifications_per_hour(self, value):
        """
        Validate max notifications per hour
        """
        if value < 1 or value > 100:
            raise serializers.ValidationError(
                "Max notifications per hour must be between 1 and 100."
            )
        return value
    
    def validate(self, data):
        """
        Validate quiet hours
        """
        quiet_start = data.get('quiet_hours_start')
        quiet_end = data.get('quiet_hours_end')
        
        if quiet_start and not quiet_end:
            raise serializers.ValidationError(
                "Quiet hours end time is required when start time is set."
            )
        
        if quiet_end and not quiet_start:
            raise serializers.ValidationError(
                "Quiet hours start time is required when end time is set."
            )
        
        return data

class NotificationBulkActionSerializer(serializers.Serializer):
    """
    Serializer for bulk notification actions
    """
    notification_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=100
    )
    action = serializers.ChoiceField(
        choices=['mark_read', 'mark_unread', 'delete']
    )
    
    def validate_notification_ids(self, value):
        """
        Validate that all notification IDs exist
        """
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Duplicate notification IDs found.")
        return value

class NotificationTemplateSerializer(serializers.ModelSerializer):
    """
    Serializer for NotificationTemplate model
    """
    class Meta:
        model = NotificationTemplate
        fields = [
            'id', 'name', 'notification_type', 'title_template',
            'message_template', 'action_text_template', 'action_url_template',
            'variables', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_name(self, value):
        """
        Validate template name uniqueness
        """
        if self.instance:
            # Update case - exclude current instance
            if NotificationTemplate.objects.exclude(
                id=self.instance.id
            ).filter(name=value).exists():
                raise serializers.ValidationError(
                    "Template with this name already exists."
                )
        else:
            # Create case
            if NotificationTemplate.objects.filter(name=value).exists():
                raise serializers.ValidationError(
                    "Template with this name already exists."
                )
        return value

class NotificationBatchSerializer(serializers.ModelSerializer):
    """
    Serializer for NotificationBatch model
    """
    notifications = NotificationSerializer(many=True, read_only=True)
    notification_count = serializers.SerializerMethodField()
    
    class Meta:
        model = NotificationBatch
        fields = [
            'id', 'user', 'batch_type', 'title', 'notifications',
            'notification_count', 'is_sent', 'sent_at', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_notification_count(self, obj):
        """
        Get count of notifications in the batch
        """
        return obj.notifications.count()

class NotificationDeliverySerializer(serializers.ModelSerializer):
    """
    Serializer for NotificationDelivery model
    """
    notification = NotificationSerializer(read_only=True)
    
    class Meta:
        model = NotificationDelivery
        fields = [
            'id', 'notification', 'channel', 'status', 'delivery_data',
            'error_message', 'created_at', 'sent_at', 'delivered_at'
        ]
        read_only_fields = ['id', 'created_at']

class NotificationStatsSerializer(serializers.Serializer):
    """
    Serializer for notification statistics
    """
    total_count = serializers.IntegerField()
    unread_count = serializers.IntegerField()
    recent_count = serializers.IntegerField()
    type_counts = serializers.ListField(
        child=serializers.DictField()
    )
    priority_counts = serializers.ListField(
        child=serializers.DictField()
    )

class NotificationPreferencesSerializer(serializers.Serializer):
    """
    Serializer for notification preferences summary
    """
    notification_types = serializers.ListField(
        child=serializers.DictField()
    )
    priorities = serializers.ListField(
        child=serializers.DictField()
    )
    delivery_channels = serializers.ListField(
        child=serializers.DictField()
    )

class WebSocketNotificationSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for WebSocket notifications
    """
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'title', 'message', 'notification_type', 'priority',
            'is_read', 'action_url', 'action_text', 'created_at', 'time_ago'
        ]
    
    def get_time_ago(self, obj):
        """
        Get relative time for WebSocket updates
        """
        now = timezone.now()
        time_diff = now - obj.created_at
        
        if time_diff.days > 0:
            return f"{time_diff.days}d"
        elif time_diff.seconds > 3600:
            hours = time_diff.seconds // 3600
            return f"{hours}h"
        elif time_diff.seconds > 60:
            minutes = time_diff.seconds // 60
            return f"{minutes}m"
        else:
            return "now"

class NotificationSummarySerializer(serializers.Serializer):
    """
    Serializer for notification summary/digest
    """
    period = serializers.CharField()  # 'daily', 'weekly', etc.
    total_notifications = serializers.IntegerField()
    unread_notifications = serializers.IntegerField()
    top_categories = serializers.ListField(
        child=serializers.DictField()
    )
    recent_highlights = serializers.ListField(
        child=NotificationSerializer()
    )
    generated_at = serializers.DateTimeField()

class NotificationFilterSerializer(serializers.Serializer):
    """
    Serializer for notification filtering options
    """
    is_read = serializers.BooleanField(required=False)
    notification_type = serializers.ChoiceField(
        choices=NotificationType.choices,
        required=False
    )
    priority = serializers.ChoiceField(
        choices=NotificationPriority.choices,
        required=False
    )
    date_from = serializers.DateTimeField(required=False)
    date_to = serializers.DateTimeField(required=False)
    search = serializers.CharField(max_length=255, required=False)
    
    def validate(self, data):
        """
        Validate date range
        """
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError(
                "Start date must be before end date."
            )
        
        return data