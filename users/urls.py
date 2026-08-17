from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

app_name = 'users'

urlpatterns = [
    # Authentication endpoints
    path('register/', views.UserRegistrationView.as_view(), name='register'),
    path('login/', views.UserLoginView.as_view(), name='login'),
    path('logout/', views.UserLogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # User profile endpoints
    path('profile/', views.UserProfileView.as_view(), name='profile'),
    path('preferences/', views.UserPreferencesView.as_view(), name='preferences'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    
    # User management endpoints
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/<int:pk>/', views.UserDetailView.as_view(), name='user_detail'),
    
    # Utility endpoints
    path('stats/', views.user_stats, name='user_stats'),
    path('refresh-stats/', views.refresh_user_stats, name='refresh_user_stats'),
    path('check-email/', views.check_email_availability, name='check_email'),
]