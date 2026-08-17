from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth import get_user_model
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.pagination import PageNumberPagination
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import logging

from .models import Notification, NotificationSettings, NotificationDelivery
from .serializers import (
    NotificationSerializer, NotificationSettingsSerializer,
    NotificationDeliverySerializer, NotificationCreateSerializer
)
from .utils import NotificationManager

User = get_user_model()
logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()


class NotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class NotificationListView(generics.ListAPIView):
    """List notifications for authenticated user"""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NotificationPagination
    
    def get_queryset(self):
        user = self.request.user
        queryset = Notification.objects.filter(user=user).order_by('-created_at')
        
        # Filter by read status
        is_read = self.request.query_params.get('is_read')
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == 'true')
        
        # Filter by notification type
        notification_type = self.request.query_params.get('type')
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        
        # Filter by priority
        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        return queryset


class NotificationDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete a notification"""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


class NotificationCreateView(generics.CreateAPIView):
    """Create a new notification"""
    serializer_class = NotificationCreateSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    """Mark a specific notification as read"""
    try:
        notification = get_object_or_404(
            Notification, 
            id=notification_id, 
            user=request.user
        )
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
        
        serializer = NotificationSerializer(notification)
        return Response(serializer.data)
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    """Mark all notifications as read for the user"""
    try:
        updated_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(
            is_read=True,
            read_at=timezone.now()
        )
        
        return Response({
            'message': f'Marked {updated_count} notifications as read',
            'updated_count': updated_count
        })
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_notification_action(request):
    """Perform bulk actions on notifications"""
    try:
        action = request.data.get('action')
        notification_ids = request.data.get('notification_ids', [])
        
        if not action or not notification_ids:
            return Response(
                {'error': 'Action and notification_ids are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notifications = Notification.objects.filter(
            id__in=notification_ids,
            user=request.user
        )
        
        if action == 'mark_read':
            updated_count = notifications.update(
                is_read=True,
                read_at=timezone.now()
            )
        elif action == 'mark_unread':
            updated_count = notifications.update(
                is_read=False,
                read_at=None
            )
        elif action == 'delete':
            updated_count = notifications.count()
            notifications.delete()
        else:
            return Response(
                {'error': 'Invalid action'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({
            'message': f'Action {action} performed on {updated_count} notifications',
            'updated_count': updated_count
        })
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_stats(request):
    """Get notification statistics for the user"""
    try:
        user = request.user
        
        total_count = Notification.objects.filter(user=user).count()
        unread_count = Notification.objects.filter(user=user, is_read=False).count()
        read_count = total_count - unread_count
        
        # Get counts by type
        type_counts = Notification.objects.filter(user=user).values(
            'notification_type'
        ).annotate(count=Count('id'))
        
        # Get counts by priority
        priority_counts = Notification.objects.filter(user=user).values(
            'priority'
        ).annotate(count=Count('id'))
        
        return Response({
            'total_count': total_count,
            'unread_count': unread_count,
            'read_count': read_count,
            'type_counts': list(type_counts),
            'priority_counts': list(priority_counts)
        })
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_test_notification(request):
    """Send a test notification to the user"""
    try:
        user = request.user
        
        notification = NotificationManager.create_notification(
            user=user,
            title='Test Notification',
            message='This is a test notification to verify the system is working correctly.',
            notification_type='system',
            priority='low'
        )
        
        if notification:
            serializer = NotificationSerializer(notification)
            return Response({
                'message': 'Test notification sent successfully',
                'notification': serializer.data
            })
        else:
            return Response(
                {'error': 'Failed to create test notification'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_recommendation_notification(request):
    """Create a recommendation notification"""
    try:
        user = request.user
        movie_id = request.data.get('movie_id')
        reason = request.data.get('reason', 'Based on your preferences')
        
        if not movie_id:
            return Response(
                {'error': 'movie_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from movies.models import Movie
        movie = get_object_or_404(Movie, id=movie_id)
        
        notification = NotificationManager.create_notification(
            user=user,
            title=f'New Movie Recommendation: {movie.title}',
            message=f'We think you\'ll love "{movie.title}"! {reason}',
            notification_type='recommendation',
            priority='medium',
            action_url=f'/movies/{movie.id}/',
            action_text='View Movie',
            content_object=movie
        )
        
        if notification:
            serializer = NotificationSerializer(notification)
            return Response(serializer.data)
        else:
            return Response(
                {'error': 'Failed to create notification'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_social_notification(request):
    """Create a social notification"""
    try:
        user = request.user
        title = request.data.get('title')
        message = request.data.get('message')
        
        if not title or not message:
            return Response(
                {'error': 'title and message are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notification = NotificationManager.create_notification(
            user=user,
            title=title,
            message=message,
            notification_type='social',
            priority='low'
        )
        
        if notification:
            serializer = NotificationSerializer(notification)
            return Response(serializer.data)
        else:
            return Response(
                {'error': 'Failed to create notification'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_system_notification(request):
    """Create a system notification"""
    try:
        user = request.user
        title = request.data.get('title')
        message = request.data.get('message')
        priority = request.data.get('priority', 'medium')
        
        if not title or not message:
            return Response(
                {'error': 'title and message are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notification = NotificationManager.create_notification(
            user=user,
            title=title,
            message=message,
            notification_type='system',
            priority=priority
        )
        
        if notification:
            serializer = NotificationSerializer(notification)
            return Response(serializer.data)
        else:
            return Response(
                {'error': 'Failed to create notification'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_400_BAD_REQUEST
        )


class NotificationPreferencesView(generics.RetrieveUpdateAPIView):
    """Get or update notification preferences"""
    serializer_class = NotificationSettingsSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        settings, created = NotificationSettings.objects.get_or_create(
            user=self.request.user
        )
        return settings


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_notification_preferences(request):
    """Update notification preferences"""
    try:
        settings, created = NotificationSettings.objects.get_or_create(
            user=request.user
        )
        
        serializer = NotificationSettingsSerializer(
            settings, 
            data=request.data, 
            partial=True
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        else:
            return Response(
                serializer.errors, 
                status=status.HTTP_400_BAD_REQUEST
            )
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def websocket_info(request):
    """Get WebSocket connection information"""
    return Response({
        'websocket_url': '/ws/notifications/',
        'requires_authentication': True,
        'supported_events': [
            'notification_created',
            'notification_updated',
            'notification_deleted'
        ]
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def broadcast_notification(request):
    """Broadcast notification to all users (admin only)"""
    if not request.user.is_staff:
        return Response(
            {'error': 'Permission denied'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        title = request.data.get('title')
        message = request.data.get('message')
        notification_type = request.data.get('type', 'system')
        priority = request.data.get('priority', 'medium')
        
        if not title or not message:
            return Response(
                {'error': 'title and message are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create notifications for all users
        users = User.objects.filter(is_active=True)
        notifications_created = 0
        
        for user in users:
            notification = NotificationManager.create_notification(
                user=user,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority
            )
            if notification:
                notifications_created += 1
        
        return Response({
            'message': f'Broadcast notification sent to {notifications_created} users',
            'notifications_created': notifications_created
        })
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def cleanup_old_notifications(request):
    """Clean up old notifications (admin only)"""
    if not request.user.is_staff:
        return Response(
            {'error': 'Permission denied'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        days = int(request.query_params.get('days', 30))
        cutoff_date = timezone.now() - timedelta(days=days)
        
        deleted_count = Notification.objects.filter(
            created_at__lt=cutoff_date,
            is_read=True
        ).delete()[0]
        
        return Response({
            'message': f'Cleaned up {deleted_count} old notifications',
            'deleted_count': deleted_count
        })
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_analytics(request):
    """Get notification analytics (admin only)"""
    if not request.user.is_staff:
        return Response(
            {'error': 'Permission denied'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        # Get analytics for the last 30 days
        cutoff_date = timezone.now() - timedelta(days=30)
        
        total_notifications = Notification.objects.filter(
            created_at__gte=cutoff_date
        ).count()
        
        read_notifications = Notification.objects.filter(
            created_at__gte=cutoff_date,
            is_read=True
        ).count()
        
        # Get delivery statistics
        delivery_stats = NotificationDelivery.objects.filter(
            notification__created_at__gte=cutoff_date
        ).values('channel', 'status').annotate(count=Count('id'))
        
        # Get user engagement
        active_users = Notification.objects.filter(
            created_at__gte=cutoff_date
        ).values('user').distinct().count()
        
        return Response({
            'period_days': 30,
            'total_notifications': total_notifications,
            'read_notifications': read_notifications,
            'read_rate': (read_notifications / total_notifications * 100) if total_notifications > 0 else 0,
            'delivery_stats': list(delivery_stats),
            'active_users': active_users
        })
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_400_BAD_REQUEST
        )