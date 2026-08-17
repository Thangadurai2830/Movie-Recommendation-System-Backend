from celery import shared_task
from django.utils import timezone
from django.db.models import Count, Avg, Q
from django.db import models
from datetime import timedelta
import logging

from .ml_engine import recommendation_engine
from .models import Recommendation, TrendingMovie, UserMovieInteraction
from movies.models import Movie, Rating
from .cache_utils import cache_manager

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def retrain_ml_models(self):
    """
    Retrain ML models with latest data
    """
    try:
        logger.info("Starting ML model retraining task")
        
        # Check if we have enough new data to warrant retraining
        recent_ratings = Rating.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).count()
        
        if recent_ratings < 10:  # Only retrain if we have significant new data
            logger.info(f"Not enough new ratings ({recent_ratings}) to warrant retraining")
            return "Skipped - insufficient new data"
        
        # Clear existing models to force retraining
        recommendation_engine.svd_model = None
        recommendation_engine.nmf_model = None
        recommendation_engine.user_clusters = None
        recommendation_engine.user_similarity = None
        recommendation_engine.movie_similarity = None
        
        # Retrain models
        recommendation_engine._train_all_models()
        
        # Clear all cached recommendations to force fresh recommendations
        cache_manager.cache.clear()
        
        logger.info("ML model retraining completed successfully")
        return "ML models retrained successfully"
        
    except Exception as e:
        logger.error(f"Error retraining ML models: {str(e)}")
        # Retry the task
        raise self.retry(countdown=60 * (self.request.retries + 1))

@shared_task(bind=True, max_retries=3)
def generate_recommendations_for_user(self, user_id, algorithm='hybrid', count=10):
    """
    Generate recommendations for a specific user in the background
    """
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        user = User.objects.get(id=user_id)
        logger.info(f"Generating recommendations for user {user_id}")
        
        # Generate recommendations
        recommendations = recommendation_engine.get_recommendations(
            user=user,
            count=count,
            algorithm=algorithm
        )
        
        # Store recommendations in database
        for movie, confidence_score, reason in recommendations:
            Recommendation.objects.update_or_create(
                user=user,
                movie=movie,
                algorithm=algorithm,
                defaults={
                    'confidence_score': confidence_score,
                    'reason': reason
                }
            )
        
        logger.info(f"Generated {len(recommendations)} recommendations for user {user_id}")
        return f"Generated {len(recommendations)} recommendations"
        
    except Exception as e:
        logger.error(f"Error generating recommendations for user {user_id}: {str(e)}")
        raise self.retry(countdown=60 * (self.request.retries + 1))

@shared_task(bind=True, max_retries=3)
def update_trending_movies(self):
    """
    Update trending movies based on recent interactions and ratings
    """
    try:
        logger.info("Starting trending movies update task")
        
        # Calculate trending score based on recent activity
        cutoff_date = timezone.now() - timedelta(days=7)
        
        trending_data = Movie.objects.annotate(
            recent_ratings_count=Count(
                'ratings',
                filter=Q(ratings__created_at__gte=cutoff_date)
            ),
            recent_avg_rating=Avg(
                'ratings__rating',
                filter=Q(ratings__created_at__gte=cutoff_date)
            ),
            recent_interactions_count=Count(
                'interactions',
                filter=Q(interactions__created_at__gte=cutoff_date)
            )
        ).filter(
            recent_ratings_count__gte=5  # At least 5 recent ratings
        ).order_by('-recent_ratings_count', '-recent_avg_rating')[:50]
        
        # Clear existing trending movies
        TrendingMovie.objects.all().delete()
        
        # Create new trending movies
        trending_movies = []
        for rank, movie in enumerate(trending_data, 1):
            trending_score = (
                movie.recent_ratings_count * 0.4 +
                (movie.recent_avg_rating or 0) * 20 +
                movie.recent_interactions_count * 0.3
            )
            
            trending_movies.append(TrendingMovie(
                movie=movie,
                trending_score=trending_score,
                rank=rank
            ))
        
        TrendingMovie.objects.bulk_create(trending_movies)
        
        logger.info(f"Updated {len(trending_movies)} trending movies")
        return f"Updated {len(trending_movies)} trending movies"
        
    except Exception as e:
        logger.error(f"Error updating trending movies: {str(e)}")
        raise self.retry(countdown=60 * (self.request.retries + 1))

@shared_task(bind=True, max_retries=3)
def cleanup_old_recommendations(self):
    """
    Clean up old recommendations and cache entries
    """
    try:
        logger.info("Starting cleanup task")
        
        # Delete recommendations older than 30 days
        cutoff_date = timezone.now() - timedelta(days=30)
        deleted_count = Recommendation.objects.filter(
            created_at__lt=cutoff_date
        ).delete()[0]
        
        # Delete old user interactions older than 90 days
        interaction_cutoff = timezone.now() - timedelta(days=90)
        deleted_interactions = UserMovieInteraction.objects.filter(
            created_at__lt=interaction_cutoff
        ).delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} old recommendations and {deleted_interactions} old interactions")
        return f"Cleaned up {deleted_count} recommendations and {deleted_interactions} interactions"
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        raise self.retry(countdown=60 * (self.request.retries + 1))

@shared_task(bind=True, max_retries=3)
def precompute_user_recommendations(self, user_ids=None):
    """
    Precompute recommendations for active users
    """
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        if user_ids is None:
            # Get active users (users who have interacted in the last 7 days)
            cutoff_date = timezone.now() - timedelta(days=7)
            user_ids = UserMovieInteraction.objects.filter(
                created_at__gte=cutoff_date
            ).values_list('user_id', flat=True).distinct()
        
        logger.info(f"Precomputing recommendations for {len(user_ids)} users")
        
        success_count = 0
        for user_id in user_ids:
            try:
                user = User.objects.get(id=user_id)
                
                # Generate recommendations for different algorithms
                for algorithm in ['hybrid', 'collaborative', 'content']:
                    recommendations = recommendation_engine.get_recommendations(
                        user=user,
                        count=20,
                        algorithm=algorithm
                    )
                    
                    # Cache will be handled by the ML engine
                    
                success_count += 1
                
            except Exception as e:
                logger.warning(f"Failed to precompute recommendations for user {user_id}: {str(e)}")
                continue
        
        logger.info(f"Successfully precomputed recommendations for {success_count} users")
        return f"Precomputed recommendations for {success_count}/{len(user_ids)} users"
        
    except Exception as e:
        logger.error(f"Error precomputing recommendations: {str(e)}")
        raise self.retry(countdown=60 * (self.request.retries + 1))