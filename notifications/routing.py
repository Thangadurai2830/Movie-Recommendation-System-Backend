from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # User notification WebSocket
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
    
    # User notification WebSocket with user ID
    re_path(r'ws/notifications/(?P<user_id>\d+)/$', consumers.NotificationConsumer.as_asgi()),
    
    # Admin broadcast WebSocket
    re_path(r'ws/notifications/broadcast/$', consumers.NotificationBroadcastConsumer.as_asgi()),
    
    # Admin stats WebSocket
    re_path(r'ws/notifications/stats/$', consumers.NotificationStatsConsumer.as_asgi()),
]