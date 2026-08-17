from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    Notification, NotificationSettings, NotificationTemplate,
    NotificationBatch, NotificationDelivery
)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'notification_type', 'title', 'priority',
        'is_read', 'is_deleted', 'created_at', 'read_at'
    ]
    list_filter = [
        'notification_type', 'priority', 'is_read', 'is_deleted',
        'created_at', 'read_at'
    ]
    search_fields = ['title', 'message', 'user__username', 'user__email']
    readonly_fields = ['id', 'created_at', 'updated_at', 'read_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'notification_type', 'title', 'message')
        }),
        ('Settings', {
            'fields': ('priority', 'is_read', 'is_deleted')
        }),
        ('Related Object', {
            'fields': ('content_type', 'object_id'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('data', 'action_url', 'action_text'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'read_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['mark_as_read', 'mark_as_unread', 'soft_delete', 'restore']
    
    def mark_as_read(self, request, queryset):
        updated = queryset.filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        self.message_user(request, f'{updated} notifications marked as read.')
    mark_as_read.short_description = "Mark selected notifications as read"
    
    def mark_as_unread(self, request, queryset):
        updated = queryset.filter(is_read=True).update(
            is_read=False,
            read_at=None
        )
        self.message_user(request, f'{updated} notifications marked as unread.')
    mark_as_unread.short_description = "Mark selected notifications as unread"
    
    def soft_delete(self, request, queryset):
        updated = queryset.filter(is_deleted=False).update(is_deleted=True)
        self.message_user(request, f'{updated} notifications soft deleted.')
    soft_delete.short_description = "Soft delete selected notifications"
    
    def restore(self, request, queryset):
        updated = queryset.filter(is_deleted=True).update(is_deleted=False)
        self.message_user(request, f'{updated} notifications restored.')
    restore.short_description = "Restore selected notifications"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'user', 'content_type'
        )

@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'email_notifications', 'push_notifications', 'enabled',
        'quiet_hours_start', 'quiet_hours_end', 'digest_frequency'
    ]
    list_filter = [
        'email_notifications', 'push_notifications', 'enabled', 'digest_frequency'
    ]
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Channel Settings', {
            'fields': (
                'enabled', 'email_notifications', 'push_notifications',
                'desktop_notifications', 'sound_enabled'
            )
        }),
        ('Notification Types', {
            'fields': (
                'recommendations_enabled', 'social_enabled',
                'system_enabled', 'marketing_enabled', 'achievements_enabled',
                'trending_enabled', 'watchlist_enabled', 'rating_enabled',
                'review_enabled', 'friend_enabled'
            )
        }),
        ('Timing', {
            'fields': ('quiet_hours_start', 'quiet_hours_end', 'digest_frequency', 'max_notifications_per_hour')
        }),

        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'notification_type', 'is_active',
        'created_at', 'updated_at'
    ]
    list_filter = ['notification_type', 'is_active']
    search_fields = ['name', 'title_template', 'message_template']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'notification_type', 'is_active')
        }),
        ('Templates', {
            'fields': ('title_template', 'message_template', 'action_text_template', 'action_url_template')
        }),
        ('Variables', {
            'fields': ('variables',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['activate_templates', 'deactivate_templates']
    
    def activate_templates(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} templates activated.')
    activate_templates.short_description = "Activate selected templates"
    
    def deactivate_templates(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} templates deactivated.')
    deactivate_templates.short_description = "Deactivate selected templates"

@admin.register(NotificationBatch)
class NotificationBatchAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'batch_type', 'title', 'is_sent', 'created_at'
    ]
    list_filter = ['batch_type', 'is_sent', 'created_at']
    search_fields = ['title', 'batch_type', 'user__username']
    readonly_fields = [
        'id', 'created_at', 'sent_at'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'batch_type', 'title')
        }),
        ('Notifications', {
            'fields': ('notifications',)
        }),
        ('Status', {
            'fields': ('is_sent', 'sent_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    


@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(admin.ModelAdmin):
    list_display = [
        'notification', 'channel', 'status',
        'sent_at', 'delivered_at', 'created_at'
    ]
    list_filter = ['channel', 'status', 'sent_at', 'delivered_at']
    search_fields = [
        'notification__title', 'notification__user__username',
        'error_message'
    ]
    readonly_fields = [
        'sent_at', 'delivered_at', 'created_at'
    ]
    date_hierarchy = 'sent_at'
    
    fieldsets = (
        ('Delivery Information', {
            'fields': ('notification', 'channel', 'status')
        }),
        ('Delivery Data', {
            'fields': ('delivery_data',),
            'classes': ('collapse',)
        }),
        ('Error Information', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'sent_at', 'delivered_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['retry_failed_deliveries']
    
    def retry_failed_deliveries(self, request, queryset):
        failed_deliveries = queryset.filter(status='failed')
        count = failed_deliveries.count()
        
        # Reset status to pending for retry
        failed_deliveries.update(
            status='pending',
            error_message=''
        )
        
        self.message_user(
            request, 
            f'{count} failed deliveries queued for retry.'
        )
    retry_failed_deliveries.short_description = "Retry failed deliveries"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'notification', 'notification__user'
        )

# Custom admin views for statistics
class NotificationStatsAdmin(admin.ModelAdmin):
    """
    Custom admin view for notification statistics
    """
    change_list_template = 'admin/notifications/notification_stats.html'
    
    def changelist_view(self, request, extra_context=None):
        from django.db.models import Count, Q
        from datetime import timedelta
        
        now = timezone.now()
        today = now.date()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        # Basic statistics
        stats = {
            'total_notifications': Notification.objects.count(),
            'unread_notifications': Notification.objects.filter(
                is_read=False, is_deleted=False
            ).count(),
            'today_notifications': Notification.objects.filter(
                created_at__date=today
            ).count(),
            'week_notifications': Notification.objects.filter(
                created_at__gte=week_ago
            ).count(),
            'month_notifications': Notification.objects.filter(
                created_at__gte=month_ago
            ).count(),
        }
        
        # Notification types distribution
        type_stats = list(
            Notification.objects.values('notification_type')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        # Channel delivery stats
        delivery_stats = list(
            NotificationDelivery.objects.values('channel', 'status')
            .annotate(count=Count('id'))
            .order_by('channel', 'status')
        )
        
        extra_context = extra_context or {}
        extra_context.update({
            'stats': stats,
            'type_stats': type_stats,
            'delivery_stats': delivery_stats,
        })
        
        return super().changelist_view(request, extra_context=extra_context)
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False

# Note: Custom admin views can be added through URL patterns
# The NotificationStatsAdmin class is available for custom implementation