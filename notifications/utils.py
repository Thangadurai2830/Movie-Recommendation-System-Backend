from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.db.models import Q, Count
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from .models import (
    Notification,
    NotificationSettings,
    NotificationTemplate,
    NotificationDelivery,
    NotificationType,
    NotificationPriority
)
from .serializers import WebSocketNotificationSerializer

User = get_user_model()
logger = logging.getLogger(__name__)

class NotificationManager:
    """
    Central manager for handling all notification operations
    """
    
    @staticmethod
    def create_notification(
        user: User,
        title: str,
        message: str,
        notification_type: str = NotificationType.SYSTEM,
        priority: str = NotificationPriority.MEDIUM,
        action_url: str = None,
        action_text: str = None,
        data: Dict = None,
        content_object = None,
        expires_at: datetime = None,
        send_real_time: bool = True
    ) -> Notification:
        """
        Create a new notification with all validations
        """
        try:
            # Check user's notification settings
            settings_obj = NotificationManager.get_user_settings(user)
            
            if not settings_obj.enabled:
                logger.info(f"Notifications disabled for user {user.username}")
                return None
            
            if not settings_obj.is_notification_type_enabled(notification_type):
                logger.info(
                    f"{notification_type} notifications disabled for user {user.username}"
                )
                return None
            
            # Check rate limiting
            if not NotificationManager.check_rate_limit(user, settings_obj):
                logger.warning(f"Rate limit exceeded for user {user.username}")
                return None
            
            # Create notification
            notification_data = {
                'user': user,
                'title': title,
                'message': message,
                'notification_type': notification_type,
                'priority': priority,
                'data': data or {}
            }
            
            if action_url:
                notification_data['action_url'] = action_url
            if action_text:
                notification_data['action_text'] = action_text
            if expires_at:
                notification_data['expires_at'] = expires_at
            if content_object:
                notification_data['content_object'] = content_object
            
            # Handle quiet hours
            if settings_obj.is_quiet_hours():
                notification_data['data']['created_during_quiet_hours'] = True
                send_real_time = False  # Don't send real-time during quiet hours
            
            notification = Notification.objects.create(**notification_data)
            
            # Send real-time notification
            if send_real_time:
                NotificationManager.send_real_time_notification(notification)
            
            # Schedule other delivery methods
            NotificationManager.schedule_delivery(notification, settings_obj)
            
            logger.info(f"Notification created: {notification.id} for user {user.username}")
            return notification
            
        except Exception as e:
            logger.error(f"Error creating notification: {str(e)}")
            return None
    
    @staticmethod
    def get_user_settings(user: User) -> NotificationSettings:
        """
        Get or create user notification settings
        """
        settings_obj, created = NotificationSettings.objects.get_or_create(
            user=user
        )
        return settings_obj
    
    @staticmethod
    def check_rate_limit(user: User, settings: NotificationSettings) -> bool:
        """
        Check if user has exceeded notification rate limit
        """
        hour_ago = timezone.now() - timedelta(hours=1)
        recent_count = Notification.objects.filter(
            user=user,
            created_at__gte=hour_ago
        ).count()
        
        return recent_count < settings.max_notifications_per_hour
    
    @staticmethod
    def send_real_time_notification(notification: Notification):
        """
        Send notification via WebSocket
        """
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                logger.warning("Channel layer not configured")
                return
            
            # Serialize notification data
            serializer = WebSocketNotificationSerializer(notification)
            notification_data = serializer.data
            
            # Send to user's notification group
            group_name = f"notifications_{notification.user.id}"
            
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'notification_message',
                    'notification': notification_data
                }
            )
            
            # Create delivery record
            NotificationDelivery.objects.create(
                notification=notification,
                channel='websocket',
                status='sent',
                sent_at=timezone.now()
            )
            
            logger.info(f"Real-time notification sent: {notification.id}")
            
        except Exception as e:
            logger.error(f"Error sending real-time notification: {str(e)}")
            
            # Create failed delivery record
            NotificationDelivery.objects.create(
                notification=notification,
                channel='websocket',
                status='failed',
                error_message=str(e)
            )
    
    @staticmethod
    def schedule_delivery(notification: Notification, settings: NotificationSettings):
        """
        Schedule notification delivery via other channels
        """
        # Email delivery
        if settings.email_notifications:
            NotificationManager.send_email_notification(notification)
        
        # Push notification delivery
        if settings.push_notifications:
            NotificationManager.send_push_notification(notification)
    
    @staticmethod
    def send_email_notification(notification: Notification):
        """
        Send notification via email
        """
        try:
            user = notification.user
            
            # Render email template
            context = {
                'notification': notification,
                'user': user,
                'site_name': getattr(settings, 'SITE_NAME', 'Movie Recommendation System')
            }
            
            subject = f"[{context['site_name']}] {notification.title}"
            html_message = render_to_string(
                'notifications/email_notification.html',
                context
            )
            plain_message = render_to_string(
                'notifications/email_notification.txt',
                context
            )
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False
            )
            
            # Create delivery record
            NotificationDelivery.objects.create(
                notification=notification,
                channel='email',
                status='sent',
                sent_at=timezone.now(),
                delivery_data={'email': user.email}
            )
            
            logger.info(f"Email notification sent: {notification.id}")
            
        except Exception as e:
            logger.error(f"Error sending email notification: {str(e)}")
            
            # Create failed delivery record
            NotificationDelivery.objects.create(
                notification=notification,
                channel='email',
                status='failed',
                error_message=str(e),
                delivery_data={'email': notification.user.email}
            )
    
    @staticmethod
    def send_push_notification(notification: Notification):
        """
        Send push notification (placeholder for future implementation)
        """
        try:
            # Placeholder for push notification service integration
            # This would integrate with services like Firebase, OneSignal, etc.
            
            logger.info(f"Push notification scheduled: {notification.id}")
            
            # Create delivery record
            NotificationDelivery.objects.create(
                notification=notification,
                channel='push',
                status='sent',
                sent_at=timezone.now()
            )
            
        except Exception as e:
            logger.error(f"Error sending push notification: {str(e)}")
            
            NotificationDelivery.objects.create(
                notification=notification,
                channel='push',
                status='failed',
                error_message=str(e)
            )
    
    @staticmethod
    def create_from_template(
        template_name: str,
        user: User,
        context: Dict,
        **kwargs
    ) -> Optional[Notification]:
        """
        Create notification from template
        """
        try:
            template = NotificationTemplate.objects.get(
                name=template_name,
                is_active=True
            )
            
            # Render template
            rendered = template.render(context)
            
            return NotificationManager.create_notification(
                user=user,
                title=rendered['title'],
                message=rendered['message'],
                notification_type=template.notification_type,
                action_text=rendered['action_text'],
                action_url=rendered['action_url'],
                **kwargs
            )
            
        except NotificationTemplate.DoesNotExist:
            logger.error(f"Notification template not found: {template_name}")
            return None
        except Exception as e:
            logger.error(f"Error creating notification from template: {str(e)}")
            return None
    
    @staticmethod
    def bulk_create_notifications(
        users: List[User],
        title: str,
        message: str,
        **kwargs
    ) -> List[Notification]:
        """
        Create notifications for multiple users
        """
        notifications = []
        
        for user in users:
            notification = NotificationManager.create_notification(
                user=user,
                title=title,
                message=message,
                **kwargs
            )
            if notification:
                notifications.append(notification)
        
        return notifications
    
    @staticmethod
    def cleanup_old_notifications(days: int = 30):
        """
        Clean up old notifications
        """
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Delete old read notifications
        deleted_count = Notification.objects.filter(
            created_at__lt=cutoff_date,
            is_read=True
        ).delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} old notifications")
        return deleted_count
    
    @staticmethod
    def get_user_notification_stats(user: User) -> Dict:
        """
        Get comprehensive notification statistics for a user
        """
        notifications = Notification.objects.filter(
            user=user,
            is_deleted=False
        )
        
        total_count = notifications.count()
        unread_count = notifications.filter(is_read=False).count()
        
        # Count by type
        type_stats = notifications.values('notification_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Count by priority
        priority_stats = notifications.values('priority').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Recent activity
        week_ago = timezone.now() - timedelta(days=7)
        recent_count = notifications.filter(
            created_at__gte=week_ago
        ).count()
        
        return {
            'total_count': total_count,
            'unread_count': unread_count,
            'recent_count': recent_count,
            'type_stats': list(type_stats),
            'priority_stats': list(priority_stats)
        }

class NotificationTemplateManager:
    """
    Manager for notification templates
    """
    
    @staticmethod
    def create_default_templates():
        """
        Create default notification templates
        """
        templates = [
            {
                'name': 'movie_recommendation',
                'notification_type': NotificationType.RECOMMENDATION,
                'title_template': 'New Movie Recommendation: {{ movie.title }}',
                'message_template': 'We think you\'ll love "{{ movie.title }}"! {{ recommendation_reason }}',
                'action_text_template': 'View Movie',
                'action_url_template': '/movies/{{ movie.id }}/',
                'variables': {
                    'movie': 'Movie object with title, id, etc.',
                    'recommendation_reason': 'Reason for recommendation'
                }
            },
            {
                'name': 'new_follower',
                'notification_type': NotificationType.SOCIAL,
                'title_template': 'New Follower',
                'message_template': '{{ follower.username }} started following you!',
                'action_text_template': 'View Profile',
                'action_url_template': '/users/{{ follower.id }}/',
                'variables': {
                    'follower': 'User object who started following'
                }
            },
            {
                'name': 'review_liked',
                'notification_type': NotificationType.SOCIAL,
                'title_template': 'Review Liked',
                'message_template': '{{ liker.username }} liked your review of "{{ movie.title }}"!',
                'action_text_template': 'View Review',
                'action_url_template': '/reviews/{{ review.id }}/',
                'variables': {
                    'liker': 'User who liked the review',
                    'movie': 'Movie that was reviewed',
                    'review': 'Review object'
                }
            },
            {
                'name': 'trending_movie',
                'notification_type': NotificationType.TRENDING,
                'title_template': 'Trending Now',
                'message_template': '"{{ movie.title }}" is trending! Join the conversation.',
                'action_text_template': 'Check it out',
                'action_url_template': '/movies/{{ movie.id }}/',
                'variables': {
                    'movie': 'Trending movie object'
                }
            },
            {
                'name': 'watchlist_reminder',
                'notification_type': NotificationType.WATCHLIST,
                'title_template': 'Watchlist Reminder',
                'message_template': 'Don\'t forget to watch "{{ movie.title }}" from your watchlist!',
                'action_text_template': 'Watch Now',
                'action_url_template': '/movies/{{ movie.id }}/',
                'variables': {
                    'movie': 'Movie from watchlist'
                }
            },
            {
                'name': 'system_maintenance',
                'notification_type': NotificationType.SYSTEM,
                'title_template': 'System Maintenance',
                'message_template': '{{ message }}',
                'action_text_template': 'Learn More',
                'action_url_template': '{{ url }}',
                'variables': {
                    'message': 'Maintenance message',
                    'url': 'URL for more information'
                }
            }
        ]
        
        created_count = 0
        for template_data in templates:
            template, created = NotificationTemplate.objects.get_or_create(
                name=template_data['name'],
                defaults=template_data
            )
            if created:
                created_count += 1
        
        logger.info(f"Created {created_count} default notification templates")
        return created_count

class NotificationAnalytics:
    """
    Analytics and reporting for notifications
    """
    
    @staticmethod
    def get_delivery_stats(days: int = 7) -> Dict:
        """
        Get notification delivery statistics
        """
        start_date = timezone.now() - timedelta(days=days)
        
        deliveries = NotificationDelivery.objects.filter(
            created_at__gte=start_date
        )
        
        total_deliveries = deliveries.count()
        successful_deliveries = deliveries.filter(status='delivered').count()
        failed_deliveries = deliveries.filter(status='failed').count()
        
        # Stats by channel
        channel_stats = deliveries.values('channel').annotate(
            total=Count('id'),
            successful=Count('id', filter=Q(status='delivered')),
            failed=Count('id', filter=Q(status='failed'))
        )
        
        return {
            'period_days': days,
            'total_deliveries': total_deliveries,
            'successful_deliveries': successful_deliveries,
            'failed_deliveries': failed_deliveries,
            'success_rate': (successful_deliveries / total_deliveries * 100) if total_deliveries > 0 else 0,
            'channel_stats': list(channel_stats)
        }
    
    @staticmethod
    def get_user_engagement_stats(days: int = 30) -> Dict:
        """
        Get user engagement statistics
        """
        start_date = timezone.now() - timedelta(days=days)
        
        notifications = Notification.objects.filter(
            created_at__gte=start_date
        )
        
        total_notifications = notifications.count()
        read_notifications = notifications.filter(is_read=True).count()
        clicked_notifications = notifications.filter(
            action_url__isnull=False,
            is_read=True
        ).count()
        
        # Engagement by type
        type_engagement = notifications.values('notification_type').annotate(
            total=Count('id'),
            read=Count('id', filter=Q(is_read=True))
        )
        
        return {
            'period_days': days,
            'total_notifications': total_notifications,
            'read_notifications': read_notifications,
            'clicked_notifications': clicked_notifications,
            'read_rate': (read_notifications / total_notifications * 100) if total_notifications > 0 else 0,
            'click_rate': (clicked_notifications / total_notifications * 100) if total_notifications > 0 else 0,
            'type_engagement': list(type_engagement)
        }

# Utility functions for common notification scenarios
def notify_movie_recommendation(user: User, movie, recommendation_type: str = 'general'):
    """
    Send a movie recommendation notification
    """
    return NotificationManager.create_from_template(
        template_name='movie_recommendation',
        user=user,
        context={
            'movie': movie,
            'recommendation_reason': f'Based on your {recommendation_type} preferences'
        },
        priority=NotificationPriority.MEDIUM
    )

def notify_new_follower(user: User, follower: User):
    """
    Send a new follower notification
    """
    return NotificationManager.create_from_template(
        template_name='new_follower',
        user=user,
        context={'follower': follower},
        priority=NotificationPriority.LOW
    )

def notify_review_liked(user: User, liker: User, review, movie):
    """
    Send a review liked notification
    """
    return NotificationManager.create_from_template(
        template_name='review_liked',
        user=user,
        context={
            'liker': liker,
            'review': review,
            'movie': movie
        },
        priority=NotificationPriority.LOW
    )

def notify_trending_movie(users: List[User], movie):
    """
    Send trending movie notifications to multiple users
    """
    return NotificationManager.bulk_create_notifications(
        users=users,
        title=f"Trending Now: {movie.title}",
        message=f'"{movie.title}" is trending! Join the conversation.',
        notification_type=NotificationType.TRENDING,
        priority=NotificationPriority.MEDIUM,
        action_url=f'/movies/{movie.id}/',
        action_text='Check it out'
    )

def notify_system_maintenance(message: str, url: str = None):
    """
    Send system maintenance notification to all users
    """
    active_users = User.objects.filter(is_active=True)
    
    return NotificationManager.bulk_create_notifications(
        users=active_users,
        title="System Maintenance",
        message=message,
        notification_type=NotificationType.SYSTEM,
        priority=NotificationPriority.HIGH,
        action_url=url,
        action_text='Learn More' if url else None
    )