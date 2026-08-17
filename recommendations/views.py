from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.throttling import UserRateThrottle
from django.core.cache import cache
import logging
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Q
from movies.models import Movie, Rating, Genre
from .models import (
    UserPreference, Recommendation, SimilarMovie, UserMovieInteraction,
    RecommendationFeedback, TrendingMovie
)
from .serializers import (
    UserPreferenceSerializer, RecommendationSerializer, SimilarMovieSerializer,
    UserMovieInteractionSerializer, RecommendationFeedbackSerializer,
    TrendingMovieSerializer, RecommendationRequestSerializer, UserStatsSerializer
)
import random
from datetime import datetime, timedelta
from .ml_engine import recommendation_engine
from .cache_utils import cache_manager

User = get_user_model()
logger = logging.getLogger(__name__)

class RecommendationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class UserPreferenceView(generics.RetrieveUpdateAPIView):
    """Get or update user preferences"""
    serializer_class = UserPreferenceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        preference, created = UserPreference.objects.get_or_create(
            user=self.request.user
        )
        return preference
    
    def perform_update(self, serializer):
        serializer.save(user=self.request.user)

class RecommendationListView(generics.ListAPIView):
    """List user's recommendations with enhanced performance and caching"""
    serializer_class = RecommendationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = RecommendationPagination
    throttle_classes = [UserRateThrottle]
    
    def get_queryset(self):
        try:
            cache_key = f"user_recommendations_{self.request.user.id}"
            cached_recommendations = cache.get(cache_key)
            
            if cached_recommendations is None:
                queryset = Recommendation.objects.filter(
                    user=self.request.user
                ).select_related('movie').prefetch_related(
                    'movie__genres', 'movie__languages'
                ).order_by('-created_at')
                
                # Cache for 15 minutes
                cache.set(cache_key, list(queryset), 900)
                return queryset
            
            return cached_recommendations
        except Exception as e:
            logger.error(f"Error getting recommendations: {str(e)}")
            return Recommendation.objects.none()

class UserMovieInteractionListCreateView(generics.ListCreateAPIView):
    """List and create user movie interactions with enhanced validation"""
    serializer_class = UserMovieInteractionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = RecommendationPagination
    throttle_classes = [UserRateThrottle]
    
    def get_queryset(self):
        try:
            return UserMovieInteraction.objects.filter(
                user=self.request.user
            ).select_related('movie').prefetch_related(
                'movie__genres'
            ).order_by('-created_at')
        except Exception as e:
            logger.error(f"Error getting user interactions: {str(e)}")
            return UserMovieInteraction.objects.none()
    
    def perform_create(self, serializer):
        try:
            interaction = serializer.save(user=self.request.user)
            # Clear recommendation cache to trigger regeneration
            cache_key = f"recommendations_{self.request.user.id}_*"
            cache.delete_many([cache_key])
            
            # Invalidate user's cached recommendations when they interact with movies
            cache_manager.invalidate_user_cache(self.request.user.id)
            
            logger.info(f"Created interaction: User {self.request.user.id} {interaction.interaction_type} movie {interaction.movie.id}")
        except Exception as e:
            logger.error(f"Error creating interaction: {str(e)}")
            raise ValidationError("Failed to record movie interaction")

class RecommendationFeedbackListCreateView(generics.ListCreateAPIView):
    """List and create recommendation feedback with enhanced validation"""
    serializer_class = RecommendationFeedbackSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = RecommendationPagination
    throttle_classes = [UserRateThrottle]
    
    def get_queryset(self):
        try:
            return RecommendationFeedback.objects.filter(
                user=self.request.user
            ).select_related('recommendation', 'recommendation__movie').order_by('-created_at')
        except Exception as e:
            logger.error(f"Error getting recommendation feedback: {str(e)}")
            return RecommendationFeedback.objects.none()
    
    def perform_create(self, serializer):
        try:
            # Check if feedback already exists for this recommendation
            recommendation = serializer.validated_data['recommendation']
            if recommendation.user != self.request.user:
                raise ValidationError("Cannot provide feedback for another user's recommendation")
            
            existing_feedback = RecommendationFeedback.objects.filter(
                user=self.request.user,
                recommendation=recommendation
            ).first()
            
            if existing_feedback:
                # Update existing feedback
                for attr, value in serializer.validated_data.items():
                    setattr(existing_feedback, attr, value)
                existing_feedback.save()
                logger.info(f"Updated feedback for recommendation {recommendation.id}")
            else:
                # Create new feedback
                feedback = serializer.save(user=self.request.user)
                logger.info(f"Created feedback for recommendation {recommendation.id}")
                
                # Incorporate feedback into ML engine for improved recommendations
                try:
                    from .ml_engine import MovieRecommendationEngine
                    ml_engine = MovieRecommendationEngine()
                    ml_engine.incorporate_feedback(
                        user=self.request.user,
                        movie=recommendation.movie,
                        feedback_type=feedback.feedback_type,
                        rating=feedback.rating
                    )
                except Exception as e:
                    logger.error(f"Error incorporating feedback into ML engine: {str(e)}")
            
            # Invalidate user's cached recommendations when they provide feedback
            cache_manager.invalidate_user_cache(self.request.user.id)
            
        except Exception as e:
            logger.error(f"Error creating feedback: {str(e)}")
            raise ValidationError("Failed to submit recommendation feedback")

class TrendingMoviesView(generics.ListAPIView):
    """List trending movies"""
    serializer_class = TrendingMovieSerializer
    
    def get_queryset(self):
        period = self.request.query_params.get('period', 'weekly')
        return TrendingMovie.objects.filter(
            period_type=period
        ).order_by('-trending_score')[:20]

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_recommendations(request):
    """Generate personalized movie recommendations using advanced ML algorithms with enhanced validation and caching"""
    try:
        serializer = RecommendationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"Invalid recommendation request data: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        user = request.user
        count = data.get('count', 10)
        recommendation_type = data.get('recommendation_type', 'hybrid')
        include_watched = data.get('include_watched', False)
        
        # Validate parameters
        try:
            count = int(count)
            if count > 50:
                count = 50
            elif count < 1:
                count = 10
        except (ValueError, TypeError):
            count = 10
            logger.warning(f"Invalid count parameter, using default: {count}")
        
        # Check cache first using cache manager
        cached_result = cache_manager.get_cached_recommendations(
            user.id, recommendation_type, count, True, True
        )
        if cached_result:
            logger.info(f"Returning cached recommendations for user {user.id}")
            # Convert cached ML results to API response format
            recommendations_data = []
            for movie, confidence_score, reason in cached_result:
                recommendations_data.append({
                    'movie': {
                        'id': movie.id,
                        'title': movie.title,
                        'year': movie.year,
                        'poster': movie.poster_url,
                        'genres': [genre.name for genre in movie.genres.all()],
                        'rating': movie.ratings.aggregate(avg=Avg('rating'))['avg'] or 0,
                        'duration': movie.duration
                    },
                    'confidence_score': confidence_score,
                    'reason': reason,
                    'algorithm': recommendation_type
                })
            return Response({
                'recommendations': recommendations_data,
                'algorithm_used': recommendation_type,
                'total_count': len(recommendations_data)
            })
        
        # Use the new ML engine for recommendations
        ml_recommendations = recommendation_engine.get_recommendations(
            user=user,
            count=count,
            algorithm=recommendation_type
        )
        
        # Convert to the expected format and save recommendations
        recommendations_data = []
        for movie, confidence_score, reason in ml_recommendations:
            # Create or update recommendation record
            recommendation, created = Recommendation.objects.get_or_create(
                user=user,
                movie=movie,
                algorithm=recommendation_type,
                defaults={
                    'confidence_score': confidence_score,
                    'reason': reason
                }
            )
            
            if not created:
                recommendation.confidence_score = confidence_score
                recommendation.reason = reason
                recommendation.save()
            
            recommendations_data.append({
                'id': recommendation.id,
                'movie': {
                    'id': movie.id,
                    'title': movie.title,
                    'year': movie.year,
                    'poster': movie.poster_url,
                    'genres': [genre.name for genre in movie.genres.all()],
                    'rating': movie.ratings.aggregate(avg=Avg('rating'))['avg'] or 0,
                    'duration': movie.duration
                },
                'confidence_score': confidence_score,
                'reason': reason,
                'algorithm': recommendation_type,
                'created_at': recommendation.created_at
            })
        
        # Cache the response data
        response_data = {
            'recommendations': recommendations_data,
            'algorithm_used': recommendation_type,
            'total_count': len(recommendations_data)
        }
        
        # Cache the formatted response for API calls
        cache_manager.set_cached_recommendations(
            user.id, recommendation_type, count, True, True, ml_recommendations
        )
        
        return Response(response_data)
        
    except Exception as e:
        # Fallback to original algorithm if ML engine fails
        return _generate_fallback_recommendations(user, count, recommendation_type)

def _generate_fallback_recommendations(user, count, recommendation_type):
    """Fallback recommendation generation"""
    # Get user's rated movies
    user_ratings = Rating.objects.filter(user=user)
    watched_movie_ids = user_ratings.values_list('movie_id', flat=True)
    
    # Base queryset - exclude watched movies
    movies_queryset = Movie.objects.exclude(id__in=watched_movie_ids)
    
    # Generate recommendations based on type
    if recommendation_type == 'collaborative':
        recommended_movies = _collaborative_filtering(user, movies_queryset, count)
    elif recommendation_type == 'content_based':
        recommended_movies = _content_based_filtering(user, movies_queryset, count)
    elif recommendation_type == 'trending':
        recommended_movies = _trending_recommendations(movies_queryset, count)
    else:  # hybrid
        recommended_movies = _hybrid_recommendations(user, movies_queryset, count)
    
    # Convert to response format
    recommendations_data = []
    for movie, confidence_score, reason in recommended_movies:
        # Create recommendation record
        recommendation = Recommendation.objects.create(
            user=user,
            movie=movie,
            algorithm=recommendation_type,
            confidence_score=confidence_score,
            reason=reason
        )
        
        recommendations_data.append({
            'id': recommendation.id,
            'movie': {
                'id': movie.id,
                'title': movie.title,
                'year': movie.year,
                'poster': getattr(movie, 'poster_url', ''),
                'genres': [genre.name for genre in movie.genres.all()],
                'rating': movie.ratings.aggregate(avg=Avg('rating'))['avg'] or 0,
                'duration': movie.duration
            },
            'confidence_score': confidence_score,
            'reason': reason,
            'algorithm': recommendation_type,
            'created_at': recommendation.created_at
        })
    
    return Response({
        'recommendations': recommendations_data,
        'algorithm_used': recommendation_type,
        'total_count': len(recommendations_data),
        'fallback_used': True
    })

def _collaborative_filtering(user, movies_queryset, count):
    """Simple collaborative filtering based on similar users"""
    # Get user's ratings
    user_ratings = Rating.objects.filter(user=user)
    if not user_ratings.exists():
        return _trending_recommendations(movies_queryset, count)
    
    # Find similar users (users who rated similar movies highly)
    similar_users = User.objects.filter(
        ratings__movie__in=user_ratings.values('movie'),
        ratings__rating__gte=7
    ).exclude(id=user.id).annotate(
        common_movies=Count('ratings__movie')
    ).filter(common_movies__gte=3).order_by('-common_movies')[:10]
    
    # Get highly rated movies from similar users
    recommended_movies = Movie.objects.filter(
        id__in=movies_queryset.values('id'),
        ratings__user__in=similar_users,
        ratings__rating__gte=8
    ).annotate(
        avg_rating=Avg('ratings__rating'),
        rating_count=Count('ratings')
    ).filter(rating_count__gte=3).order_by('-avg_rating')[:count]
    
    return [(movie, movie.avg_rating, 'Users with similar taste loved this movie') 
            for movie in recommended_movies]

def _content_based_filtering(user, movies_queryset, count):
    """Content-based filtering based on user's genre preferences"""
    # Get user's favorite genres from ratings
    user_ratings = Rating.objects.filter(user=user, rating__gte=7)
    if not user_ratings.exists():
        return _trending_recommendations(movies_queryset, count)
    
    favorite_genres = Genre.objects.filter(
        movies__ratings__in=user_ratings
    ).annotate(
        avg_rating=Avg('movies__ratings__rating')
    ).order_by('-avg_rating')[:5]
    
    # Recommend movies from favorite genres
    recommended_movies = movies_queryset.filter(
        genres__in=favorite_genres
    ).annotate(
        avg_rating=Avg('ratings__rating'),
        rating_count=Count('ratings')
    ).filter(rating_count__gte=5).order_by('-avg_rating')[:count]
    
    return [(movie, movie.avg_rating or 0, f'Based on your love for {movie.genres.first().name} movies') 
            for movie in recommended_movies]

def _trending_recommendations(movies_queryset, count):
    """Get trending/popular movies"""
    trending_movies = movies_queryset.annotate(
        avg_rating=Avg('ratings__rating'),
        rating_count=Count('ratings')
    ).filter(
        rating_count__gte=10,
        avg_rating__gte=7
    ).order_by('-rating_count', '-avg_rating')[:count]
    
    return [(movie, movie.avg_rating, 'Currently trending and highly rated') 
            for movie in trending_movies]

def _hybrid_recommendations(user, movies_queryset, count):
    """Hybrid approach combining collaborative and content-based"""
    collaborative_count = count // 2
    content_count = count - collaborative_count
    
    collaborative_recs = _collaborative_filtering(user, movies_queryset, collaborative_count)
    content_recs = _content_based_filtering(user, movies_queryset, content_count)
    
    # Combine and remove duplicates
    all_recs = collaborative_recs + content_recs
    seen_movies = set()
    unique_recs = []
    
    for movie, score, reason in all_recs:
        if movie.id not in seen_movies:
            seen_movies.add(movie.id)
            unique_recs.append((movie, score, reason))
    
    # Fill remaining slots with trending if needed
    if len(unique_recs) < count:
        remaining = count - len(unique_recs)
        trending_recs = _trending_recommendations(
            movies_queryset.exclude(id__in=seen_movies), 
            remaining
        )
        unique_recs.extend(trending_recs)
    
    return unique_recs[:count]

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_recommendation_stats(request):
    """Get user's recommendation statistics"""
    user = request.user
    
    # Calculate various statistics
    total_movies_watched = Rating.objects.filter(user=user).count()
    total_ratings_given = Rating.objects.filter(user=user).count()
    avg_rating_given = Rating.objects.filter(user=user).aggregate(
        avg=Avg('rating')
    )['avg'] or 0
    
    # Favorite genres
    favorite_genres = Genre.objects.filter(
        movies__ratings__user=user,
        movies__ratings__rating__gte=7
    ).annotate(
        count=Count('movies__ratings')
    ).order_by('-count')[:5].values_list('name', flat=True)
    
    # Watchlist count
    from movies.models import Watchlist
    total_watchlist_items = Watchlist.objects.filter(user=user).count()
    
    # Recommendation stats
    recommendations_received = Recommendation.objects.filter(user=user).count()
    recommendations_liked = RecommendationFeedback.objects.filter(
        user=user,
        feedback_type='like'
    ).count()
    
    # Most watched genre
    most_watched_genre = Genre.objects.filter(
        movies__ratings__user=user
    ).annotate(
        count=Count('movies__ratings')
    ).order_by('-count').first()
    
    # Estimate watching time (assuming average movie duration)
    watching_time_minutes = total_movies_watched * 120  # Rough estimate
    
    stats = {
        'total_movies_watched': total_movies_watched,
        'total_ratings_given': total_ratings_given,
        'average_rating_given': round(avg_rating_given, 1),
        'favorite_genres': list(favorite_genres),
        'total_watchlist_items': total_watchlist_items,
        'recommendations_received': recommendations_received,
        'recommendations_liked': recommendations_liked,
        'most_watched_genre': most_watched_genre.name if most_watched_genre else 'None',
        'watching_time_minutes': watching_time_minutes
    }
    
    serializer = UserStatsSerializer(stats)
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def record_interaction(request, movie_id):
    """Record user interaction with a movie"""
    movie = get_object_or_404(Movie, id=movie_id)
    interaction_type = request.data.get('interaction_type', 'view')
    duration_watched = request.data.get('duration_watched')
    
    interaction = UserMovieInteraction.objects.create(
        user=request.user,
        movie=movie,
        interaction_type=interaction_type,
        duration_watched=duration_watched
    )
    
    serializer = UserMovieInteractionSerializer(interaction)
    return Response(serializer.data, status=status.HTTP_201_CREATED)

@api_view(['GET'])
def similar_movies(request, movie_id):
    """Get movies similar to the given movie"""
    movie = get_object_or_404(Movie, id=movie_id)
    
    # Find similar movies based on genres and ratings
    similar_movies = Movie.objects.filter(
        genres__in=movie.genres.all()
    ).exclude(
        id=movie.id
    ).annotate(
        avg_rating=Avg('ratings__rating'),
        rating_count=Count('ratings'),
        common_genres=Count('genres')
    ).filter(
        rating_count__gte=5
    ).order_by('-common_genres', '-avg_rating')[:10]
    
    from movies.serializers import MovieListSerializer
    serializer = MovieListSerializer(similar_movies, many=True, context={'request': request})
    return Response(serializer.data)

class FeedbackAnalyticsView(APIView):
    """Get analytics on recommendation feedback performance"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get feedback analytics for current user or overall system"""
        try:
            from .ml_engine import MovieRecommendationEngine
            
            ml_engine = MovieRecommendationEngine()
            
            # Get user-specific analytics if requested
            user_analytics = request.query_params.get('user_only', 'false').lower() == 'true'
            user = request.user if user_analytics else None
            
            analytics = ml_engine.get_feedback_analytics(user=user)
            
            # Add additional insights
            if analytics.get('total_feedback', 0) > 0:
                analytics['insights'] = self._generate_insights(analytics)
            
            return Response(analytics, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting feedback analytics: {str(e)}")
            return Response(
                {'error': 'Failed to get feedback analytics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _generate_insights(self, analytics):
        """Generate insights from analytics data"""
        insights = []
        
        satisfaction_rate = analytics.get('satisfaction_rate', 0)
        if satisfaction_rate >= 80:
            insights.append("Excellent recommendation performance! Users are highly satisfied.")
        elif satisfaction_rate >= 60:
            insights.append("Good recommendation performance with room for improvement.")
        else:
            insights.append("Recommendation system needs optimization to improve user satisfaction.")
        
        total_feedback = analytics.get('total_feedback', 0)
        if total_feedback < 10:
            insights.append("More user feedback needed for better recommendation accuracy.")
        elif total_feedback > 100:
            insights.append("Rich feedback data available for advanced personalization.")
        
        avg_rating = analytics.get('avg_rating', 0)
        if avg_rating and avg_rating >= 4.0:
            insights.append("Users are rating recommended content highly.")
        elif avg_rating and avg_rating < 3.0:
            insights.append("Consider improving content quality or recommendation relevance.")
        
        return insights
