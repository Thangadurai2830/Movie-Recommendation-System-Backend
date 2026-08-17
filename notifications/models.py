from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
import json

User = get_user_model()

class NotificationType(models.TextChoices):
    RECOMMENDATION = 'recommendation', 'Movie Recommendation'
    SOCIAL = 'social', 'Social Activity'
    ACHIEVEMENT = 'achievement', 'Achievement Unlocked'
    SYSTEM = 'system', 'System Update'
    TRENDING = 'trending', 'Trending Alert'
    WATCHLIST = 'watchlist', 'Watchlist Update'
    RATING = 'rating', 'Rating Update'
    REVIEW = 'review', 'Review Update'
    FRIEND = 'friend', 'Friend Activity'
    MARKETING = 'marketing', 'Marketing'

class NotificationPriority(models.TextChoices):
    LOW = 'low', 'Low'
    MEDIUM = 'medium', 'Medium'
    HIGH = 'high', 'High'
    URGENT = 'urgent', 'Urgent'

class Notification(models.Model):
    """
    Main notification model for storing all types of notifications
    """
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='notifications'
    )
    
    # Notification content
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        default=NotificationType.SYSTEM
    )
    priority = models.CharField(
        max_length=10,
        choices=NotificationPriority.choices,
        default=NotificationPriority.MEDIUM
    )
    
    # Status
    is_read = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    
    # Metadata
    data = models.JSONField(default=dict, blank=True)  # Additional data
    action_url = models.URLField(blank=True, null=True)  # URL to navigate to
    action_text = models.CharField(max_length=100, blank=True)  # Button text
    
    # Generic foreign key for related objects
    content_type = models.ForeignKey(
        ContentType, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    read_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', 'is_deleted']),
            models.Index(fields=['notification_type', 'created_at']),
            models.Index(fields=['priority', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
    
    def mark_as_unread(self):
        """Mark notification as unread"""
        if self.is_read:
            self.is_read = False
            self.read_at = None
            self.save(update_fields=['is_read', 'read_at'])
    
    def soft_delete(self):
        """Soft delete notification"""
        self.is_deleted = True
        self.save(update_fields=['is_deleted'])
    
    @property
    def is_expired(self):
        """Check if notification is expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    @property
    def age_in_hours(self):
        """Get notification age in hours"""
        return (timezone.now() - self.created_at).total_seconds() / 3600

class NotificationSettings(models.Model):
    """
    User notification preferences
    """
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='notification_settings'
    )
    
    # General settings
    enabled = models.BooleanField(default=True)
    sound_enabled = models.BooleanField(default=True)
    desktop_notifications = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)
    
    # Notification type preferences
    recommendations_enabled = models.BooleanField(default=True)
    social_enabled = models.BooleanField(default=True)
    achievements_enabled = models.BooleanField(default=True)
    system_enabled = models.BooleanField(default=True)
    trending_enabled = models.BooleanField(default=True)
    watchlist_enabled = models.BooleanField(default=True)
    rating_enabled = models.BooleanField(default=True)
    review_enabled = models.BooleanField(default=True)
    friend_enabled = models.BooleanField(default=True)
    marketing_enabled = models.BooleanField(default=False)
    
    # Timing preferences
    quiet_hours_start = models.TimeField(null=True, blank=True)  # e.g., 22:00
    quiet_hours_end = models.TimeField(null=True, blank=True)    # e.g., 08:00
    
    # Frequency settings
    max_notifications_per_hour = models.PositiveIntegerField(default=10)
    digest_frequency = models.CharField(
        max_length=20,
        choices=[
            ('immediate', 'Immediate'),
            ('hourly', 'Hourly'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('never', 'Never')
        ],
        default='immediate'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_settings'
    
    def __str__(self):
        return f"{self.user.username} - Notification Settings"
    
    def is_notification_type_enabled(self, notification_type):
        """Check if a specific notification type is enabled"""
        type_mapping = {
            NotificationType.RECOMMENDATION: self.recommendations_enabled,
            NotificationType.SOCIAL: self.social_enabled,
            NotificationType.ACHIEVEMENT: self.achievements_enabled,
            NotificationType.SYSTEM: self.system_enabled,
            NotificationType.TRENDING: self.trending_enabled,
            NotificationType.WATCHLIST: self.watchlist_enabled,
            NotificationType.RATING: self.rating_enabled,
            NotificationType.REVIEW: self.review_enabled,
            NotificationType.FRIEND: self.friend_enabled,
            NotificationType.MARKETING: self.marketing_enabled,
        }
        return type_mapping.get(notification_type, True)
    
    def is_quiet_hours(self):
        """Check if current time is within quiet hours"""
        if not self.quiet_hours_start or not self.quiet_hours_end:
            return False
        
        now = timezone.now().time()
        start = self.quiet_hours_start
        end = self.quiet_hours_end
        
        if start <= end:
            return start <= now <= end
        else:  # Quiet hours span midnight
            return now >= start or now <= end

class NotificationTemplate(models.Model):
    """
    Templates for different types of notifications
    """
    name = models.CharField(max_length=100, unique=True)
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices
    )
    title_template = models.CharField(max_length=255)
    message_template = models.TextField()
    action_text_template = models.CharField(max_length=100, blank=True)
    action_url_template = models.CharField(max_length=255, blank=True)
    
    # Template variables documentation
    variables = models.JSONField(
        default=dict, 
        help_text="Available template variables and their descriptions"
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_templates'
    
    def __str__(self):
        return f"{self.name} ({self.notification_type})"
    
    def render(self, context):
        """Render template with given context"""
        from django.template import Template, Context
        
        title = Template(self.title_template).render(Context(context))
        message = Template(self.message_template).render(Context(context))
        action_text = Template(self.action_text_template).render(Context(context)) if self.action_text_template else ''
        action_url = Template(self.action_url_template).render(Context(context)) if self.action_url_template else ''
        
        return {
            'title': title,
            'message': message,
            'action_text': action_text,
            'action_url': action_url
        }

class NotificationBatch(models.Model):
    """
    For grouping related notifications (e.g., daily digest)
    """
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='notification_batches'
    )
    batch_type = models.CharField(max_length=50)  # e.g., 'daily_digest', 'weekly_summary'
    title = models.CharField(max_length=255)
    notifications = models.ManyToManyField(Notification, related_name='batches')
    
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'notification_batches'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.batch_type} ({self.created_at.date()})"

class NotificationDelivery(models.Model):
    """
    Track notification delivery across different channels
    """
    notification = models.ForeignKey(
        Notification, 
        on_delete=models.CASCADE, 
        related_name='deliveries'
    )
    
    DELIVERY_CHANNELS = [
        ('web', 'Web'),
        ('email', 'Email'),
        ('push', 'Push Notification'),
        ('sms', 'SMS'),
        ('websocket', 'WebSocket'),
    ]
    
    channel = models.CharField(max_length=20, choices=DELIVERY_CHANNELS)
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('sent', 'Sent'),
            ('delivered', 'Delivered'),
            ('failed', 'Failed'),
            ('bounced', 'Bounced'),
        ],
        default='pending'
    )
    
    # Delivery details
    delivery_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'notification_deliveries'
        unique_together = ['notification', 'channel']
    
    def __str__(self):
        return f"{self.notification.title} - {self.channel} ({self.status})"