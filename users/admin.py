from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import UserProfile

User = get_user_model()

# Customize admin site headers
admin.site.site_header = "Movie Recommendation System Admin"
admin.site.site_title = "Movie Rec Admin"
admin.site.index_title = "Welcome to Movie Recommendation System Administration"

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile Settings'
    fields = [
        ('is_profile_public', 'show_ratings', 'show_watchlist'),
        ('email_notifications', 'recommendation_emails'),
        ('min_rating_threshold', 'exclude_adult_content')
    ]
    extra = 0

class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = [
        'username', 'email', 'get_full_name', 'is_staff', 
        'is_active', 'get_rating_count', 'date_joined'
    ]
    search_fields = ['username', 'email', 'first_name', 'last_name']
    list_filter = [
        'is_staff', 'is_superuser', 'is_active', 'date_joined',
        'profile__is_profile_public'
    ]
    ordering = ['-date_joined']
    list_per_page = 25
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}" if obj.first_name or obj.last_name else "-"
    get_full_name.short_description = "Full Name"
    
    def get_rating_count(self, obj):
        count = obj.ratings.count()
        if count > 0:
            url = reverse('admin:movies_rating_changelist') + f'?user__id__exact={obj.id}'
            return format_html('<a href="{}">{} ratings</a>', url, count)
        return "No ratings"
    get_rating_count.short_description = "Ratings Given"
    get_rating_count.admin_order_field = 'ratings__count'

# Register our custom User admin
admin.site.register(User, UserAdmin)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'is_profile_public', 'min_rating_threshold', 
        'get_notification_settings', 'created_at'
    ]
    search_fields = ['user__username', 'user__email']
    list_filter = [
        'is_profile_public', 'show_ratings', 'show_watchlist', 
        'email_notifications', 'recommendation_emails', 'created_at'
    ]
    autocomplete_fields = ['user']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Privacy Settings', {
            'fields': ('is_profile_public', 'show_ratings', 'show_watchlist')
        }),
        ('Notification Settings', {
            'fields': ('email_notifications', 'recommendation_emails')
        }),
        ('Content Preferences', {
            'fields': ('min_rating_threshold', 'exclude_adult_content')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_notification_settings(self, obj):
        notifications = []
        if obj.email_notifications:
            notifications.append("📧 Email")
        if obj.recommendation_emails:
            notifications.append("🎬 Recommendations")
        return " | ".join(notifications) if notifications else "None"
    get_notification_settings.short_description = "Notifications"
