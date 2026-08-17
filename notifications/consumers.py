import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from .models import Notification, NotificationSettings
from .serializers import WebSocketNotificationSerializer

User = get_user_model()
logger = logging.getLogger(__name__)

class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications
    """
    
    async def connect(self):
        """
        Handle WebSocket connection
        """
        # Get user from scope (set by authentication middleware)
        self.user = self.scope.get('user')
        
        if not self.user or isinstance(self.user, AnonymousUser):
            # Reject connection for unauthenticated users
            await self.close(code=4001)
            return
        
        # Create group name for this user
        self.group_name = f"notifications_{self.user.id}"
        
        # Join notification group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        # Accept the connection
        await self.accept()
        
        # Send connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to notification service',
            'user_id': self.user.id,
            'timestamp': timezone.now().isoformat()
        }))
        
        # Send unread notification count
        unread_count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': unread_count
        }))
        
        logger.info(f"User {self.user.username} connected to notifications")
    
    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection
        """
        if hasattr(self, 'group_name'):
            # Leave notification group
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
        
        if hasattr(self, 'user') and self.user:
            logger.info(f"User {self.user.username} disconnected from notifications")
    
    async def receive(self, text_data):
        """
        Handle messages from WebSocket
        """
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'mark_as_read':
                await self.handle_mark_as_read(data)
            elif message_type == 'mark_all_as_read':
                await self.handle_mark_all_as_read()
            elif message_type == 'get_recent_notifications':
                await self.handle_get_recent_notifications(data)
            elif message_type == 'ping':
                await self.handle_ping()
            else:
                await self.send_error(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {str(e)}")
            await self.send_error("Internal server error")
    
    async def handle_mark_as_read(self, data):
        """
        Mark a notification as read
        """
        notification_id = data.get('notification_id')
        if not notification_id:
            await self.send_error("notification_id is required")
            return
        
        success = await self.mark_notification_as_read(notification_id)
        if success:
            # Send updated unread count
            unread_count = await self.get_unread_count()
            await self.send(text_data=json.dumps({
                'type': 'notification_marked_read',
                'notification_id': notification_id,
                'unread_count': unread_count
            }))
        else:
            await self.send_error("Failed to mark notification as read")
    
    async def handle_mark_all_as_read(self):
        """
        Mark all notifications as read
        """
        count = await self.mark_all_notifications_as_read()
        await self.send(text_data=json.dumps({
            'type': 'all_notifications_marked_read',
            'count': count,
            'unread_count': 0
        }))
    
    async def handle_get_recent_notifications(self, data):
        """
        Get recent notifications
        """
        limit = data.get('limit', 10)
        notifications = await self.get_recent_notifications(limit)
        
        await self.send(text_data=json.dumps({
            'type': 'recent_notifications',
            'notifications': notifications
        }))
    
    async def handle_ping(self):
        """
        Handle ping message for connection health check
        """
        await self.send(text_data=json.dumps({
            'type': 'pong',
            'timestamp': timezone.now().isoformat()
        }))
    
    async def notification_message(self, event):
        """
        Handle notification message from group
        """
        notification_data = event['notification']
        
        # Send notification to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'new_notification',
            'notification': notification_data
        }))
        
        # Send updated unread count
        unread_count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': unread_count
        }))
    
    async def send_error(self, message):
        """
        Send error message to client
        """
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
            'timestamp': timezone.now().isoformat()
        }))
    
    # Database operations (sync functions wrapped with database_sync_to_async)
    
    @database_sync_to_async
    def get_unread_count(self):
        """
        Get unread notification count for the user
        """
        return Notification.objects.filter(
            user=self.user,
            is_read=False,
            is_deleted=False
        ).count()
    
    @database_sync_to_async
    def mark_notification_as_read(self, notification_id):
        """
        Mark a specific notification as read
        """
        try:
            notification = Notification.objects.get(
                id=notification_id,
                user=self.user,
                is_deleted=False
            )
            notification.mark_as_read()
            return True
        except Notification.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"Error marking notification as read: {str(e)}")
            return False
    
    @database_sync_to_async
    def mark_all_notifications_as_read(self):
        """
        Mark all notifications as read for the user
        """
        try:
            updated_count = Notification.objects.filter(
                user=self.user,
                is_read=False,
                is_deleted=False
            ).update(
                is_read=True,
                read_at=timezone.now()
            )
            return updated_count
        except Exception as e:
            logger.error(f"Error marking all notifications as read: {str(e)}")
            return 0
    
    @database_sync_to_async
    def get_recent_notifications(self, limit=10):
        """
        Get recent notifications for the user
        """
        try:
            notifications = Notification.objects.filter(
                user=self.user,
                is_deleted=False
            ).order_by('-created_at')[:limit]
            
            serializer = WebSocketNotificationSerializer(notifications, many=True)
            return serializer.data
        except Exception as e:
            logger.error(f"Error getting recent notifications: {str(e)}")
            return []

class NotificationBroadcastConsumer(AsyncWebsocketConsumer):
    """
    Consumer for broadcasting system-wide notifications
    """
    
    async def connect(self):
        """
        Handle connection for broadcast notifications
        """
        # Only allow admin users to connect to broadcast channel
        self.user = self.scope.get('user')
        
        if not self.user or not self.user.is_staff:
            await self.close(code=4003)  # Forbidden
            return
        
        self.group_name = "notification_broadcast"
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        
        logger.info(f"Admin {self.user.username} connected to broadcast channel")
    
    async def disconnect(self, close_code):
        """
        Handle disconnection from broadcast channel
        """
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
        
        if hasattr(self, 'user') and self.user:
            logger.info(f"Admin {self.user.username} disconnected from broadcast channel")
    
    async def receive(self, text_data):
        """
        Handle broadcast messages
        """
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'system_announcement':
                await self.handle_system_announcement(data)
            elif message_type == 'maintenance_alert':
                await self.handle_maintenance_alert(data)
            else:
                await self.send_error(f"Unknown broadcast type: {message_type}")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Error handling broadcast message: {str(e)}")
            await self.send_error("Internal server error")
    
    async def handle_system_announcement(self, data):
        """
        Handle system announcement broadcast
        """
        title = data.get('title', 'System Announcement')
        message = data.get('message', '')
        priority = data.get('priority', 'medium')
        
        if not message:
            await self.send_error("Message is required for system announcement")
            return
        
        # Broadcast to all connected users
        await self.channel_layer.group_send(
            "notification_broadcast",
            {
                'type': 'system_message',
                'data': {
                    'title': title,
                    'message': message,
                    'priority': priority,
                    'timestamp': timezone.now().isoformat()
                }
            }
        )
        
        await self.send(text_data=json.dumps({
            'type': 'broadcast_sent',
            'message': 'System announcement sent successfully'
        }))
    
    async def handle_maintenance_alert(self, data):
        """
        Handle maintenance alert broadcast
        """
        start_time = data.get('start_time')
        duration = data.get('duration', '1 hour')
        message = data.get('message', 'Scheduled maintenance')
        
        # Broadcast maintenance alert
        await self.channel_layer.group_send(
            "notification_broadcast",
            {
                'type': 'maintenance_message',
                'data': {
                    'title': 'Scheduled Maintenance',
                    'message': message,
                    'start_time': start_time,
                    'duration': duration,
                    'timestamp': timezone.now().isoformat()
                }
            }
        )
        
        await self.send(text_data=json.dumps({
            'type': 'maintenance_alert_sent',
            'message': 'Maintenance alert sent successfully'
        }))
    
    async def system_message(self, event):
        """
        Send system message to all connected clients
        """
        await self.send(text_data=json.dumps({
            'type': 'system_announcement',
            'data': event['data']
        }))
    
    async def maintenance_message(self, event):
        """
        Send maintenance message to all connected clients
        """
        await self.send(text_data=json.dumps({
            'type': 'maintenance_alert',
            'data': event['data']
        }))
    
    async def send_error(self, message):
        """
        Send error message to client
        """
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
            'timestamp': timezone.now().isoformat()
        }))

class NotificationStatsConsumer(AsyncWebsocketConsumer):
    """
    Consumer for real-time notification statistics (admin only)
    """
    
    async def connect(self):
        """
        Handle connection for notification stats
        """
        self.user = self.scope.get('user')
        
        if not self.user or not self.user.is_staff:
            await self.close(code=4003)  # Forbidden
            return
        
        self.group_name = "notification_stats"
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial stats
        stats = await self.get_notification_stats()
        await self.send(text_data=json.dumps({
            'type': 'stats_update',
            'stats': stats
        }))
        
        logger.info(f"Admin {self.user.username} connected to stats channel")
    
    async def disconnect(self, close_code):
        """
        Handle disconnection from stats channel
        """
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """
        Handle stats requests
        """
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'get_stats':
                stats = await self.get_notification_stats()
                await self.send(text_data=json.dumps({
                    'type': 'stats_update',
                    'stats': stats
                }))
            
        except Exception as e:
            logger.error(f"Error handling stats request: {str(e)}")
    
    @database_sync_to_async
    def get_notification_stats(self):
        """
        Get real-time notification statistics
        """
        from django.db.models import Count
        from datetime import timedelta
        
        now = timezone.now()
        today = now.date()
        week_ago = now - timedelta(days=7)
        
        # Basic counts
        total_notifications = Notification.objects.count()
        unread_notifications = Notification.objects.filter(is_read=False).count()
        today_notifications = Notification.objects.filter(
            created_at__date=today
        ).count()
        week_notifications = Notification.objects.filter(
            created_at__gte=week_ago
        ).count()
        
        # Active users (users with notifications in last 24 hours)
        active_users = Notification.objects.filter(
            created_at__gte=now - timedelta(hours=24)
        ).values('user').distinct().count()
        
        # Notification types distribution
        type_distribution = list(
            Notification.objects.values('notification_type')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        return {
            'total_notifications': total_notifications,
            'unread_notifications': unread_notifications,
            'today_notifications': today_notifications,
            'week_notifications': week_notifications,
            'active_users': active_users,
            'type_distribution': type_distribution,
            'timestamp': now.isoformat()
        }
    
    async def stats_update(self, event):
        """
        Send stats update to connected clients
        """
        await self.send(text_data=json.dumps({
            'type': 'stats_update',
            'stats': event['stats']
        }))