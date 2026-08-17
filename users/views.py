from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from rest_framework.pagination import PageNumberPagination
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import logout
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)
from .models import User, UserProfile
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserSerializer,
    UserUpdateSerializer,
    ChangePasswordSerializer,
    UserProfileSerializer
)

class UserPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT token serializer with additional user data"""
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Add custom claims
        token['email'] = user.email
        token['first_name'] = user.first_name
        token['last_name'] = user.last_name
        
        return token
    
    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Add user data to response
        data['user'] = {
            'id': self.user.id,
            'email': self.user.email,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'full_name': self.user.get_full_name(),
        }
        
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom JWT token view"""
    serializer_class = CustomTokenObtainPairSerializer


class UserRegistrationView(generics.CreateAPIView):
    """User registration view with enhanced validation and rate limiting"""
    
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AnonRateThrottle]
    
    def create(self, request, *args, **kwargs):
        try:
            # Check if email already exists
            email = request.data.get('email', '').lower()
            if email and User.objects.filter(email=email).exists():
                return Response({
                    'error': 'User with this email already exists'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            serializer = self.get_serializer(data=request.data)
            if not serializer.is_valid():
                logger.error(f"Registration error: {serializer.errors}")
                return Response({
                    'error': 'Validation failed',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user = serializer.save()
            
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            # Create user profile
            UserProfile.objects.get_or_create(user=user)
            
            # Send login signal
            user_logged_in.send(sender=user.__class__, request=request, user=user)
            
            logger.info(f"New user registered: {user.email}")
            
            return Response({
                'message': 'User registered successfully',
                'user': UserSerializer(user).data,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }, status=status.HTTP_201_CREATED)
            
        except ValidationError as e:
            logger.warning(f"Registration validation error: {str(e)}")
            return Response({
                'error': 'Invalid registration data',
                'details': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return Response({
                'error': 'Registration failed. Please try again.',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserLoginView(APIView):
    """User login view with enhanced security and rate limiting"""
    
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AnonRateThrottle]
    
    def post(self, request):
        try:
            serializer = UserLoginSerializer(
                data=request.data,
                context={'request': request}
            )
            if not serializer.is_valid():
                logger.warning(f"Login attempt with invalid data: {serializer.errors}")
                return Response({
                    'error': 'Invalid login credentials'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user = serializer.validated_data['user']
            
            # Check if user is active
            if not user.is_active:
                logger.warning(f"Login attempt for inactive user: {user.email}")
                return Response({
                    'error': 'Account is deactivated'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            # Update last active timestamp
            user.last_active = timezone.now()
            user.save(update_fields=['last_active'])
            
            # Send login signal
            user_logged_in.send(sender=user.__class__, request=request, user=user)
            
            logger.info(f"Successful login: {user.email}")
            
            return Response({
                'message': 'Login successful',
                'user': UserSerializer(user).data,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return Response({
                'error': 'Login failed. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserLogoutView(APIView):
    """User logout view with enhanced error handling"""
    
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh_token')
            if refresh_token:
                try:
                    token = RefreshToken(refresh_token)
                    token.blacklist()
                except Exception as token_error:
                    logger.warning(f"Token blacklist error: {str(token_error)}")
            
            # Send logout signal
            user_logged_out.send(
                sender=request.user.__class__,
                request=request,
                user=request.user
            )
            
            logger.info(f"User logged out: {request.user.email}")
            
            return Response({
                'message': 'Logout successful'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return Response({
                'error': 'Logout failed'
            }, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """User profile view with enhanced validation and caching"""
    
    serializer_class = UserUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def get_object(self):
        return self.request.user
    
    def get(self, request, *args, **kwargs):
        """Get user profile with caching"""
        try:
            user = self.get_object()
            
            # Check cache first
            cache_key = f"user_profile_{user.id}"
            cached_profile = cache.get(cache_key)
            
            if cached_profile is None:
                serializer = UserSerializer(user)
                cached_profile = serializer.data
                # Cache for 10 minutes
                cache.set(cache_key, cached_profile, 600)
            
            return Response(cached_profile)
        except Exception as e:
            logger.error(f"Error getting user profile: {str(e)}")
            return Response({
                'error': 'Failed to retrieve profile'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def perform_update(self, serializer):
        try:
            user = serializer.save()
            # Clear cache after update
            cache_key = f"user_profile_{user.id}"
            cache.delete(cache_key)
            logger.info(f"User profile updated: {user.email}")
        except Exception as e:
            logger.error(f"Error updating user profile: {str(e)}")
            raise ValidationError("Failed to update profile")


class ChangePasswordView(APIView):
    """Change password view"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'message': 'Password changed successfully'
        }, status=status.HTTP_200_OK)


class UserListView(generics.ListAPIView):
    """User list view (for admin purposes) with enhanced filtering and pagination"""
    
    queryset = User.objects.select_related('userprofile')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]
    pagination_class = UserPagination
    throttle_classes = [UserRateThrottle]
    
    def get_queryset(self):
        try:
            queryset = super().get_queryset()
            search = self.request.query_params.get('search', None)
            is_active = self.request.query_params.get('is_active', None)
            is_verified = self.request.query_params.get('is_verified', None)
            
            if search:
                queryset = queryset.filter(
                    models.Q(first_name__icontains=search) |
                    models.Q(last_name__icontains=search) |
                    models.Q(email__icontains=search)
                )
            
            if is_active is not None:
                queryset = queryset.filter(is_active=is_active.lower() == 'true')
            
            if is_verified is not None:
                queryset = queryset.filter(is_email_verified=is_verified.lower() == 'true')
            
            return queryset.order_by('-date_joined')
        except Exception as e:
            logger.error(f"Error getting user list: {str(e)}")
            return User.objects.none()


class UserDetailView(generics.RetrieveAPIView):
    """User detail view"""
    
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        # Users can only view their own profile unless they're admin
        if self.request.user.is_staff:
            return super().get_object()
        return self.request.user


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_stats(request):
    """Get user statistics"""
    user = request.user
    
    # Update user statistics
    user.update_statistics()
    
    # Get watchlist count
    from movies.models import Watchlist
    watchlist_count = Watchlist.objects.filter(user=user).count()
    
    # Get favorite genres (top 5 most rated genres)
    from movies.models import Rating
    favorite_genres = []
    if user.total_ratings_given > 0:
        genre_ratings = Rating.objects.filter(user=user, rating__gte=4.0).values_list('movie__genres__name', flat=True)
        from collections import Counter
        genre_counts = Counter(genre_ratings)
        favorite_genres = [genre for genre, count in genre_counts.most_common(5) if genre]
    
    # Get preferred languages (from user's many-to-many field)
    preferred_languages = list(user.preferred_languages.values_list('name', flat=True))
    
    stats = {
        'total_ratings': user.total_ratings_given,
        'average_rating_given': user.average_rating,
        'total_watchlist_items': watchlist_count,
        'favorite_genres': favorite_genres,
        'preferred_languages': preferred_languages,
        'member_since': user.date_joined,
    }
    
    return Response(stats)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def refresh_user_stats(request):
    """Manually refresh user statistics"""
    user = request.user
    user.update_statistics()
    
    return Response({
        'message': 'User statistics updated successfully'
    })


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def check_email_availability(request):
    """Check if email is available for registration"""
    email = request.query_params.get('email', '')
    
    if not email:
        return Response({
            'error': 'Email parameter is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    is_available = not User.objects.filter(email=email).exists()
    
    return Response({
        'email': email,
        'is_available': is_available
    })


class UserPreferencesView(APIView):
    """View for managing user preferences (notifications, privacy, etc.)"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get user preferences"""
        try:
            user = request.user
            profile = user.userprofile
            
            preferences = {
                'notifications': {
                    'email_notifications': profile.email_notifications,
                    'recommendation_emails': profile.recommendation_emails,
                },
                'privacy': {
                    'is_profile_public': profile.is_profile_public,
                    'show_ratings': profile.show_ratings,
                    'show_watchlist': profile.show_watchlist,
                },
                'content': {
                    'min_rating_threshold': profile.min_rating_threshold,
                    'exclude_adult_content': profile.exclude_adult_content,
                }
            }
            
            return Response(preferences)
        except Exception as e:
            logger.error(f"Error getting user preferences: {str(e)}")
            return Response({
                'error': 'Failed to retrieve preferences'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def put(self, request):
        """Update user preferences"""
        try:
            user = request.user
            profile = user.userprofile
            data = request.data
            
            # Update notification preferences
            if 'notifications' in data:
                notifications = data['notifications']
                if 'email_notifications' in notifications:
                    profile.email_notifications = notifications['email_notifications']
                if 'recommendation_emails' in notifications:
                    profile.recommendation_emails = notifications['recommendation_emails']
            
            # Update privacy preferences
            if 'privacy' in data:
                privacy = data['privacy']
                if 'is_profile_public' in privacy:
                    profile.is_profile_public = privacy['is_profile_public']
                if 'show_ratings' in privacy:
                    profile.show_ratings = privacy['show_ratings']
                if 'show_watchlist' in privacy:
                    profile.show_watchlist = privacy['show_watchlist']
            
            # Update content preferences
            if 'content' in data:
                content = data['content']
                if 'min_rating_threshold' in content:
                    profile.min_rating_threshold = content['min_rating_threshold']
                if 'exclude_adult_content' in content:
                    profile.exclude_adult_content = content['exclude_adult_content']
            
            profile.save()
            
            # Clear cache
            cache_key = f"user_profile_{user.id}"
            cache.delete(cache_key)
            
            logger.info(f"User preferences updated: {user.email}")
            
            return Response({
                'message': 'Preferences updated successfully'
            })
        except Exception as e:
            logger.error(f"Error updating user preferences: {str(e)}")
            return Response({
                'error': 'Failed to update preferences'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
