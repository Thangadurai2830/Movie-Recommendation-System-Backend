from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    # Notification CRUD endpoints
    path('', views.NotificationListView.as_view(), name='notification-list'),
    path('<int:pk>/', views.NotificationDetailView.as_view(), name='notification-detail'),
    path('create/', views.NotificationCreateView.as_view(), name='notification-create'),
    
    # Custom notification endpoints
    path('mark-read/<int:notification_id>/', 
         views.mark_notification_read, name='mark-notification-read'),
    path('mark-all-read/', 
         views.mark_all_notifications_read, name='mark-all-notifications-read'),
    path('bulk-action/', 
         views.bulk_notification_action, name='bulk-notification-action'),
    path('stats/', 
         views.notification_stats, name='notification-stats'),
    path('test/', 
         views.send_test_notification, name='send-test-notification'),
    
    # Notification creation endpoints
    path('create/recommendation/', 
         views.create_recommendation_notification, name='create-recommendation-notification'),
    path('create/social/', 
         views.create_social_notification, name='create-social-notification'),
    path('create/system/', 
         views.create_system_notification, name='create-system-notification'),
    
    # User preferences
    path('preferences/', 
         views.NotificationPreferencesView.as_view(), name='notification-preferences'),
    path('preferences/update/', 
         views.update_notification_preferences, name='update-notification-preferences'),
    
    # WebSocket endpoint info
    path('websocket-info/', 
         views.websocket_info, name='websocket-info'),
    
    # Admin endpoints
    path('admin/broadcast/', 
         views.broadcast_notification, name='broadcast-notification'),
    path('admin/cleanup/', 
         views.cleanup_old_notifications, name='cleanup-old-notifications'),
    path('admin/analytics/', 
         views.notification_analytics, name='notification-analytics'),
]