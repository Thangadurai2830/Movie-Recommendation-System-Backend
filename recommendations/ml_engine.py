import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity, euclidean_distances
from sklearn.decomposition import TruncatedSVD, NMF
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
from sklearn.cluster import KMeans, DBSCAN
from sklearn.neighbors import NearestNeighbors
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge, Lasso
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from django.db import models
from django.db.models import Avg, Count, Q, F, StdDev, Max, Min
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from movies.models import Movie, Rating, Genre
from .models import UserPreference, UserMovieInteraction, Recommendation
from .cache_utils import cache_manager, cache_recommendations, cache_user_profile
import logging
from typing import List, Tuple, Dict, Any, Optional
from datetime import datetime, timedelta
import json
import math
import warnings
from collections import defaultdict, Counter
import pickle
import os

warnings.filterwarnings('ignore')

User = get_user_model()
logger = logging.getLogger(__name__)

class MovieRecommendationEngine:
    """
    Advanced Movie Recommendation Engine using multiple ML approaches
    with enhanced algorithms and sophisticated feature engineering
    """
    
    def __init__(self):
        # Enhanced Text processing with multiple vectorizers
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=15000, 
            stop_words='english',
            ngram_range=(1, 3),
            min_df=2,
            max_df=0.95,
            sublinear_tf=True
        )
        
        # Additional vectorizers for different text features
        self.genre_vectorizer = TfidfVectorizer(
            max_features=500,
            ngram_range=(1, 2)
        )
        
        self.cast_vectorizer = TfidfVectorizer(
            max_features=2000,
            ngram_range=(1, 2)
        )
        
        # Matrix factorization models
        self.svd_model = TruncatedSVD(n_components=100, random_state=42, n_iter=10)
        self.nmf_model = NMF(n_components=50, random_state=42, max_iter=200)
        
        # Enhanced scalers and clustering
        self.scaler = StandardScaler()
        self.robust_scaler = RobustScaler()
        self.minmax_scaler = MinMaxScaler()
        self.user_clusters = None
        self.movie_clusters = None
        self.kmeans_users = KMeans(n_clusters=15, random_state=42, n_init=15)
        self.kmeans_movies = KMeans(n_clusters=25, random_state=42, n_init=15)
        self.dbscan_users = DBSCAN(eps=0.5, min_samples=5)
        
        # Enhanced nearest neighbors for similarity
        self.user_nn = NearestNeighbors(n_neighbors=30, metric='cosine', algorithm='brute')
        self.movie_nn = NearestNeighbors(n_neighbors=60, metric='cosine', algorithm='brute')
        self.content_nn = NearestNeighbors(n_neighbors=25, metric='euclidean')
        
        # Advanced ML models for feature importance and prediction
        self.rf_model = RandomForestRegressor(n_estimators=200, random_state=42, max_depth=15)
        self.gradient_boost_model = GradientBoostingRegressor(
            n_estimators=150,
            learning_rate=0.1,
            max_depth=8,
            random_state=42
        )
        self.ridge_model = Ridge(alpha=1.0)
        self.lasso_model = Lasso(alpha=0.1)
        
        # Configuration
        self.cache_timeout = getattr(settings, 'RECOMMENDATION_CACHE_TIMEOUT', 3600)
        self.min_ratings_for_collaborative = 3
        self.similarity_threshold = 0.05
        self.diversity_factor = 0.3
        
        # Cached matrices and features
        self._user_item_matrix = None
        self._movie_features = None
        self._content_similarity_matrix = None
        self._user_similarity_matrix = None
        self._movie_similarity_matrix = None
        self._models_trained = False
        
        # Model persistence
        self.model_cache_dir = getattr(settings, 'BASE_DIR', '.') / 'ml_models'
        os.makedirs(self.model_cache_dir, exist_ok=True)
        
    def get_recommendations(self, user, count: int = 10, algorithm: str = 'hybrid', 
                          diversity: bool = True, explain: bool = True) -> List[Tuple[Movie, float, str]]:
        """
        Get personalized movie recommendations for a user with enhanced algorithms
        
        Args:
            user: Django User object
            count: Number of recommendations to return
            algorithm: 'collaborative', 'content', 'hybrid', 'ensemble', 'neural_cf'
            diversity: Whether to apply diversity filtering
            explain: Whether to generate detailed explanations
            
        Returns:
            List of tuples (movie, confidence_score, reason)
        """
        # Input validation
        if not user or not hasattr(user, 'id'):
            logger.error("Invalid user object provided")
            return self._popularity_based_recommendations(min(count, 10))
            
        if count <= 0 or count > 100:
            logger.warning(f"Invalid count {count}, using default of 10")
            count = 10
            
        valid_algorithms = ['collaborative', 'content', 'hybrid', 'ensemble', 'neural_cf']
        if algorithm not in valid_algorithms:
            logger.warning(f"Invalid algorithm {algorithm}, using hybrid")
            algorithm = 'hybrid'
        
        # Check cache first using cache manager
        cached_recommendations = cache_manager.get_cached_recommendations(
            user.id, algorithm, count, diversity, explain
        )
        if cached_recommendations:
            logger.info(f"Returning cached recommendations for user {user.id}")
            return cached_recommendations
        
        try:
            # Ensure models are trained
            self._ensure_models_trained()
            
            # Get base recommendations
            if algorithm == 'collaborative':
                recommendations = self._collaborative_filtering_enhanced(user, count * 2)
            elif algorithm == 'content':
                recommendations = self._content_based_enhanced(user, count * 2)
            elif algorithm == 'neural_cf':
                recommendations = self._neural_collaborative_filtering(user, count * 2)
            elif algorithm == 'ensemble':
                recommendations = self._ensemble_recommendations(user, count * 2)
            else:  # hybrid
                recommendations = self._hybrid_enhanced(user, count * 2)
            
            # Apply diversity filtering if requested
            if diversity and len(recommendations) > count:
                recommendations = self._apply_diversity_filter(recommendations, count)
            else:
                recommendations = recommendations[:count]
            
            # Enhance explanations if requested
            if explain:
                recommendations = self._enhance_explanations(user, recommendations)
            
            # Cache the results using cache manager
            if recommendations:
                cache_manager.set_cached_recommendations(
                    user.id, algorithm, count, diversity, explain, recommendations
                )
                
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating {algorithm} recommendations for user {user.id}: {str(e)}")
            return self._fallback_recommendations(user, count)
    
    def _ensure_models_trained(self):
        """
        Ensure all ML models are trained and ready
        """
        if not self._models_trained:
            try:
                self._train_all_models()
                self._models_trained = True
            except Exception as e:
                logger.warning(f"Could not train models: {str(e)}")
    
    def _train_all_models(self):
        """
        Train all ML models with current data
        """
        logger.info("Training ML models...")
        
        # Build matrices
        self._user_item_matrix = self._build_user_item_matrix_enhanced()
        
        if self._user_item_matrix is not None and not self._user_item_matrix.empty:
            # Train matrix factorization models
            matrix_filled = self._user_item_matrix.fillna(0)
            
            # SVD
            if matrix_filled.shape[1] > self.svd_model.n_components:
                self.svd_model.fit(matrix_filled)
            
            # NMF (requires non-negative values)
            matrix_positive = np.maximum(matrix_filled.values, 0)
            if matrix_positive.shape[1] > self.nmf_model.n_components:
                self.nmf_model.fit(matrix_positive)
            
            # User clustering
            if len(matrix_filled) > self.kmeans_users.n_clusters:
                self.user_clusters = self.kmeans_users.fit_predict(matrix_filled)
            
            # Nearest neighbors for users
            if len(matrix_filled) > 1:
                self.user_nn.fit(matrix_filled)
        
        # Movie features and clustering
        movie_features_df = self._get_movie_features_dataframe_enhanced()
        if movie_features_df is not None and not movie_features_df.empty:
            # Movie clustering
            if len(movie_features_df) > self.kmeans_movies.n_clusters:
                self.movie_clusters = self.kmeans_movies.fit_predict(movie_features_df)
            
            # Nearest neighbors for movies
            if len(movie_features_df) > 1:
                self.movie_nn.fit(movie_features_df)
        
        logger.info("ML models training completed")
    
    def incorporate_feedback(self, user, movie, feedback_type, rating=None):
        """
        Incorporate user feedback to improve future recommendations
        """
        try:
            from .models import RecommendationFeedback
            
            # Weight feedback based on type
            feedback_weights = {
                'helpful': 1.0,
                'like': 1.2,
                'not_helpful': -0.5,
                'dislike': -0.8,
                'irrelevant': -0.3,
                'already_seen': 0.0,
                'not_interested': -0.6
            }
            
            weight = feedback_weights.get(feedback_type, 0.0)
            
            # Update user preferences based on feedback
            self._update_user_preferences_from_feedback(user, movie, weight, rating)
            
            # Invalidate cached recommendations
            cache_manager.invalidate_user_cache(user.id)
            
            # Trigger model retraining if enough feedback accumulated
            feedback_count = RecommendationFeedback.objects.filter(
                user=user,
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count()
            
            if feedback_count >= 5:  # Retrain after 5 feedback items in a week
                self._retrain_user_model(user)
                
            logger.info(f"Incorporated {feedback_type} feedback for user {user.id} on movie {movie.id}")
            
        except Exception as e:
            logger.error(f"Error incorporating feedback: {str(e)}")
    
    def _update_user_preferences_from_feedback(self, user, movie, weight, rating):
        """
        Update user preferences based on feedback
        """
        try:
            from movies.models import UserPreference
            
            # Get or create user preferences
            preferences, created = UserPreference.objects.get_or_create(
                user=user,
                defaults={
                    'preferred_genres': [],
                    'disliked_genres': [],
                    'preferred_actors': [],
                    'preferred_directors': [],
                    'min_rating': 0.0,
                    'max_runtime': 180
                }
            )
            
            # Update genre preferences based on feedback
            movie_genres = movie.genres.all()
            for genre in movie_genres:
                if weight > 0:  # Positive feedback
                    if genre.name not in preferences.preferred_genres:
                        preferences.preferred_genres.append(genre.name)
                    if genre.name in preferences.disliked_genres:
                        preferences.disliked_genres.remove(genre.name)
                elif weight < -0.5:  # Strong negative feedback
                    if genre.name not in preferences.disliked_genres:
                        preferences.disliked_genres.append(genre.name)
                    if genre.name in preferences.preferred_genres:
                        preferences.preferred_genres.remove(genre.name)
            
            # Update rating preferences
            if rating and weight > 0:
                current_min = preferences.min_rating or 0.0
                preferences.min_rating = max(current_min, rating - 1.0)
            
            preferences.save()
            
        except Exception as e:
            logger.error(f"Error updating user preferences from feedback: {str(e)}")
    
    def _retrain_user_model(self, user):
        """
        Retrain model for specific user based on accumulated feedback
        """
        try:
            # Get user's recent feedback
            from .models import RecommendationFeedback
            
            recent_feedback = RecommendationFeedback.objects.filter(
                user=user,
                created_at__gte=timezone.now() - timedelta(days=30)
            ).select_related('recommendation__movie')
            
            # Create feedback-weighted ratings
            feedback_ratings = []
            for feedback in recent_feedback:
                movie = feedback.recommendation.movie
                
                # Convert feedback to rating
                feedback_to_rating = {
                    'helpful': 4.0,
                    'like': 5.0,
                    'not_helpful': 2.0,
                    'dislike': 1.0,
                    'irrelevant': 2.5,
                    'not_interested': 1.5
                }
                
                implicit_rating = feedback_to_rating.get(feedback.feedback_type, 3.0)
                if feedback.rating:
                    implicit_rating = (implicit_rating + feedback.rating) / 2
                
                feedback_ratings.append({
                    'movie_id': movie.id,
                    'rating': implicit_rating,
                    'weight': 2.0  # Higher weight for feedback-based ratings
                })
            
            # Update user's implicit ratings in the system
            self._update_implicit_ratings(user, feedback_ratings)
            
            # Mark models as needing retraining
            self._models_trained = False
            
            logger.info(f"Scheduled model retraining for user {user.id} based on feedback")
            
        except Exception as e:
            logger.error(f"Error retraining user model: {str(e)}")
    
    def _update_implicit_ratings(self, user, feedback_ratings):
        """
        Update implicit ratings based on feedback
        """
        try:
            from movies.models import Rating
            
            for rating_data in feedback_ratings:
                # Check if explicit rating exists
                existing_rating = Rating.objects.filter(
                    user=user,
                    movie_id=rating_data['movie_id']
                ).first()
                
                if not existing_rating:
                    # Create implicit rating based on feedback
                    Rating.objects.create(
                        user=user,
                        movie_id=rating_data['movie_id'],
                        rating=rating_data['rating'],
                        is_implicit=True  # Mark as implicit rating
                    )
                elif existing_rating.is_implicit:
                    # Update existing implicit rating
                    existing_rating.rating = (
                        existing_rating.rating + rating_data['rating']
                    ) / 2
                    existing_rating.save()
                    
        except Exception as e:
            logger.error(f"Error updating implicit ratings: {str(e)}")
    
    def get_feedback_analytics(self, user=None):
        """
        Get analytics on recommendation feedback
        """
        try:
            from .models import RecommendationFeedback
            from django.db.models import Count, Avg
            
            queryset = RecommendationFeedback.objects.all()
            if user:
                queryset = queryset.filter(user=user)
            
            analytics = queryset.aggregate(
                total_feedback=Count('id'),
                avg_rating=Avg('rating'),
                helpful_count=Count('id', filter=models.Q(feedback_type='helpful')),
                like_count=Count('id', filter=models.Q(feedback_type='like')),
                dislike_count=Count('id', filter=models.Q(feedback_type='dislike')),
                irrelevant_count=Count('id', filter=models.Q(feedback_type='irrelevant'))
            )
            
            # Calculate satisfaction rate
            positive_feedback = (analytics['helpful_count'] or 0) + (analytics['like_count'] or 0)
            total_feedback = analytics['total_feedback'] or 1
            analytics['satisfaction_rate'] = (positive_feedback / total_feedback) * 100
            
            return analytics
            
        except Exception as e:
            logger.error(f"Error getting feedback analytics: {str(e)}")
            return {}
    
    def _build_user_item_matrix_enhanced(self):
        """
        Build enhanced user-item matrix with better handling
        """
        try:
            ratings = Rating.objects.select_related('user', 'movie').all()
            if not ratings.exists():
                return None
            
            # Create pivot table
            ratings_data = []
            for rating in ratings:
                ratings_data.append({
                    'user_id': rating.user.id,
                    'movie_id': rating.movie.id,
                    'rating': rating.rating
                })
            
            df = pd.DataFrame(ratings_data)
            user_item_matrix = df.pivot_table(
                index='user_id',
                columns='movie_id',
                values='rating',
                fill_value=0
            )
            
            return user_item_matrix
            
        except Exception as e:
            logger.error(f"Error building user-item matrix: {str(e)}")
            return None
    
    def _get_movie_features_dataframe_enhanced(self):
        """
        Get enhanced movie features as DataFrame
        """
        try:
            movies = Movie.objects.prefetch_related('genres', 'ratings').all()
            if not movies.exists():
                return None
            
            features_data = []
            for movie in movies:
                avg_rating = movie.ratings.aggregate(avg=Avg('rating'))['avg'] or 0
                rating_count = movie.ratings.count()
                genre_count = movie.genres.count()
                
                features_data.append({
                    'movie_id': movie.id,
                    'year': movie.year or 2000,
                    'duration': movie.duration or 120,
                    'avg_rating': avg_rating,
                    'rating_count': rating_count,
                    'genre_count': genre_count
                })
            
            df = pd.DataFrame(features_data)
            df = df.set_index('movie_id')
            
            # Scale features
            numeric_columns = ['year', 'duration', 'avg_rating', 'rating_count', 'genre_count']
            df[numeric_columns] = self.scaler.fit_transform(df[numeric_columns])
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting movie features: {str(e)}")
            return None
    
    def _collaborative_filtering_enhanced(self, user, count: int) -> List[Tuple[Movie, float, str]]:
        """
        Enhanced collaborative filtering using multiple matrix factorization techniques
        and advanced similarity measures
        """
        try:
            if self._user_item_matrix is None or self._user_item_matrix.empty:
                logger.warning("No user-item matrix available")
                return self._content_based_enhanced(user, count)
                
            if user.id not in self._user_item_matrix.index:
                logger.info(f"User {user.id} has no ratings, using content-based")
                return self._content_based_enhanced(user, count)
            
            # Multiple collaborative filtering approaches
            recommendations = []
            
            # 1. SVD-based recommendations
            svd_recs = self._svd_recommendations(user, count)
            recommendations.extend(svd_recs)
            
            # 2. NMF-based recommendations
            nmf_recs = self._nmf_recommendations(user, count)
            recommendations.extend(nmf_recs)
            
            # 3. User-based collaborative filtering with clustering
            user_based_recs = self._user_based_cf_with_clustering(user, count)
            recommendations.extend(user_based_recs)
            
            # 4. Item-based collaborative filtering
            item_based_recs = self._item_based_collaborative_filtering(user, count)
            recommendations.extend(item_based_recs)
            
            # Combine and deduplicate
            movie_scores = {}
            for movie, score, reason in recommendations:
                if movie.id not in movie_scores:
                    movie_scores[movie.id] = {'movie': movie, 'scores': [], 'reasons': []}
                movie_scores[movie.id]['scores'].append(score)
                movie_scores[movie.id]['reasons'].append(reason)
            
            # Calculate final scores and select top recommendations
            final_recommendations = []
            for movie_id, data in movie_scores.items():
                # Use weighted average of scores
                final_score = np.mean(data['scores']) * (1 + 0.1 * len(data['scores']))
                reason = f"Collaborative filtering (confidence: {final_score:.2f})"
                final_recommendations.append((data['movie'], final_score, reason))
            
            # Sort by score and return top results
            final_recommendations.sort(key=lambda x: x[1], reverse=True)
            return final_recommendations[:count]
            
        except Exception as e:
            logger.error(f"Error in enhanced collaborative filtering: {str(e)}")
            return self._content_based_enhanced(user, count)
    
    def _svd_recommendations(self, user, count: int) -> List[Tuple[Movie, float, str]]:
        """
        SVD-based matrix factorization recommendations
        """
        try:
            if not hasattr(self.svd_model, 'components_'):
                return []
            
            user_idx = list(self._user_item_matrix.index).index(user.id)
            user_ratings = self._user_item_matrix.iloc[user_idx].fillna(0)
            
            # Transform user ratings to latent space
            user_latent = self.svd_model.transform([user_ratings.values])[0]
            
            # Predict ratings for all movies
            all_movies_latent = self.svd_model.components_.T
            predicted_ratings = np.dot(user_latent, self.svd_model.components_)
            
            # Get movies user hasn't rated
            user_movies = set(Rating.objects.filter(user=user).values_list('movie_id', flat=True))
            movie_ids = self._user_item_matrix.columns
            
            recommendations = []
            for i, movie_id in enumerate(movie_ids):
                if movie_id not in user_movies and predicted_ratings[i] > 0:
                    try:
                        movie = Movie.objects.get(id=movie_id)
                        score = min(predicted_ratings[i] / 10.0, 1.0)
                        reason = f"SVD prediction: {predicted_ratings[i]:.1f}/10"
                        recommendations.append((movie, score, reason))
                    except Movie.DoesNotExist:
                        continue
            
            recommendations.sort(key=lambda x: x[1], reverse=True)
            return recommendations[:count]
            
        except Exception as e:
            logger.warning(f"SVD recommendations failed: {str(e)}")
            return []
    
    def _nmf_recommendations(self, user, count: int) -> List[Tuple[Movie, float, str]]:
        """
        Non-negative Matrix Factorization recommendations
        """
        try:
            if not hasattr(self.nmf_model, 'components_'):
                return []
            
            user_idx = list(self._user_item_matrix.index).index(user.id)
            user_ratings = self._user_item_matrix.iloc[user_idx].fillna(0)
            
            # Ensure non-negative values for NMF
            user_ratings_positive = np.maximum(user_ratings.values, 0)
            
            # Transform to latent space
            user_latent = self.nmf_model.transform([user_ratings_positive])[0]
            
            # Predict ratings
            predicted_ratings = np.dot(user_latent, self.nmf_model.components_)
            
            # Get recommendations
            user_movies = set(Rating.objects.filter(user=user).values_list('movie_id', flat=True))
            movie_ids = self._user_item_matrix.columns
            
            recommendations = []
            for i, movie_id in enumerate(movie_ids):
                if movie_id not in user_movies and predicted_ratings[i] > 0:
                    try:
                        movie = Movie.objects.get(id=movie_id)
                        score = min(predicted_ratings[i] / 10.0, 1.0)
                        reason = f"NMF prediction: {predicted_ratings[i]:.1f}/10"
                        recommendations.append((movie, score, reason))
                    except Movie.DoesNotExist:
                        continue
            
            recommendations.sort(key=lambda x: x[1], reverse=True)
            return recommendations[:count]
            
        except Exception as e:
            logger.warning(f"NMF recommendations failed: {str(e)}")
            return []
    
    def _user_based_cf_with_clustering(self, user, count: int) -> List[Tuple[Movie, float, str]]:
        """
        User-based collaborative filtering enhanced with clustering
        """
        try:
            if self.user_clusters is None:
                return []
            
            user_idx = list(self._user_item_matrix.index).index(user.id)
            user_cluster = self.user_clusters[user_idx]
            
            # Find users in the same cluster
            cluster_users = []
            for i, cluster in enumerate(self.user_clusters):
                if cluster == user_cluster and i != user_idx:
                    cluster_users.append(self._user_item_matrix.index[i])
            
            if not cluster_users:
                return []
            
            # Get highly rated movies from cluster users
            user_movies = set(Rating.objects.filter(user=user).values_list('movie_id', flat=True))
            
            candidate_movies = Rating.objects.filter(
                user_id__in=cluster_users,
                rating__gte=7
            ).exclude(
                movie_id__in=user_movies
            ).values('movie_id').annotate(
                avg_rating=Avg('rating'),
                rating_count=Count('rating')
            ).filter(
                rating_count__gte=2
            ).order_by('-avg_rating')[:count]
            
            recommendations = []
            for item in candidate_movies:
                try:
                    movie = Movie.objects.get(id=item['movie_id'])
                    score = min(item['avg_rating'] / 10.0, 1.0)
                    reason = f"Users in your cluster rated this {item['avg_rating']:.1f}/10"
                    recommendations.append((movie, score, reason))
                except Movie.DoesNotExist:
                    continue
            
            return recommendations
            
        except Exception as e:
            logger.warning(f"Cluster-based CF failed: {str(e)}")
            return []
    
    def _item_based_collaborative_filtering(self, user, count: int) -> List[Tuple[Movie, float, str]]:
        """
        Item-based collaborative filtering using movie similarities
        """
        try:
            # Get user's highly rated movies
            user_movies = Rating.objects.filter(
                user=user, rating__gte=7
            ).select_related('movie')
            
            if not user_movies.exists():
                return []
            
            # Calculate item-item similarities
            movie_similarities = {}
            for user_rating in user_movies:
                similar_movies = self._find_similar_movies(user_rating.movie, count * 2)
                for similar_movie, similarity in similar_movies:
                    if similar_movie.id not in movie_similarities:
                        movie_similarities[similar_movie.id] = {
                            'movie': similar_movie,
                            'total_similarity': 0,
                            'count': 0
                        }
                    movie_similarities[similar_movie.id]['total_similarity'] += similarity * user_rating.rating
                    movie_similarities[similar_movie.id]['count'] += 1
            
            # Calculate final scores
            recommendations = []
            user_movie_ids = set(Rating.objects.filter(user=user).values_list('movie_id', flat=True))
            
            for movie_id, data in movie_similarities.items():
                if movie_id not in user_movie_ids:
                    avg_similarity = data['total_similarity'] / data['count']
                    score = min(avg_similarity / 10.0, 1.0)
                    reason = f"Similar to movies you liked (similarity: {avg_similarity:.1f})"
                    recommendations.append((data['movie'], score, reason))
            
            recommendations.sort(key=lambda x: x[1], reverse=True)
            return recommendations[:count]
            
        except Exception as e:
            logger.warning(f"Item-based CF failed: {str(e)}")
            return []
    
    def _content_based_enhanced(self, user, count: int) -> List[Tuple[Movie, float, str]]:
        """
        Enhanced content-based filtering with advanced feature engineering
        and multiple similarity measures
        """
        try:
            # Get user's rating history with broader range
            user_ratings = Rating.objects.filter(user=user, rating__gte=6).select_related('movie')
            
            if not user_ratings.exists():
                logger.info(f"User {user.id} has no ratings, using popularity-based")
                return self._popularity_based_recommendations(count)
            
            # Analyze user preferences
            user_profile = self._build_user_content_profile(user)
            
            if not user_profile or not any(user_profile.values()):
                logger.warning(f"Could not build content profile for user {user.id}")
                return self._popularity_based_recommendations(count)
            
            # Get candidate movies (not rated by user) with better filtering
            user_movie_ids = set(Rating.objects.filter(user=user).values_list('movie_id', flat=True))
            
            candidate_movies = Movie.objects.exclude(
                id__in=user_movie_ids
            ).filter(
                ratings__isnull=False
            ).prefetch_related(
                'genres', 'languages', 'countries', 'cast__person'
            ).distinct()
            
            if not candidate_movies.exists():
                logger.warning("No candidate movies available for content-based filtering")
                return self._popularity_based_recommendations(count)
            
            # Calculate content similarity scores with improved algorithm
            movie_scores = []
            processed_count = 0
            batch_size = 100
            
            # Process movies in batches for better performance
            for i in range(0, min(1000, candidate_movies.count()), batch_size):
                batch = candidate_movies[i:i+batch_size]
                
                for movie in batch:
                    try:
                        similarity_score = self._calculate_content_similarity(movie, user_profile)
                        if similarity_score > 0.2:  # Lower threshold for more variety
                            movie_scores.append((movie, similarity_score))
                        processed_count += 1
                    except Exception as e:
                        logger.warning(f"Error calculating similarity for movie {movie.id}: {str(e)}")
                        continue
                
                # Break if we have enough candidates
                if len(movie_scores) >= count * 3:
                    break
            
            if not movie_scores:
                logger.warning("No movies met similarity threshold")
                return self._popularity_based_recommendations(count)
            
            # Sort by similarity and get top recommendations
            movie_scores.sort(key=lambda x: x[1], reverse=True)
            
            recommendations = []
            for movie, score in movie_scores[:count]:
                try:
                    reason = self._generate_content_reason(movie, user_profile)
                    recommendations.append((movie, score, reason))
                except Exception as e:
                    logger.warning(f"Error generating reason for movie {movie.id}: {str(e)}")
                    recommendations.append((movie, score, "Based on your viewing preferences"))
                    
            return recommendations
            
        except Exception as e:
            logger.error(f"Error in content-based filtering: {str(e)}")
            return self._popularity_based_recommendations(count)
    
    def _deep_learning_recommendations(self, user, count: int) -> List[Tuple[Movie, float, str]]:
        """
        Advanced neural network-based recommendations using neural collaborative filtering
        and enhanced feature engineering
        """
        try:
            # Extract comprehensive user features
            user_features = self._extract_user_features(user)
            
            if not user_features or not any(user_features.values()):
                logger.warning(f"Could not extract features for user {user.id}")
                return self._content_based_advanced(user, count)
            
            # Get candidate movies with better filtering
            user_movie_ids = set(Rating.objects.filter(user=user).values_list('movie_id', flat=True))
            
            candidate_movies = Movie.objects.exclude(
                id__in=user_movie_ids
            ).filter(
                ratings__isnull=False
            ).prefetch_related(
                'genres', 'languages', 'countries', 'cast__person', 'crew__person'
            ).distinct()[:2000]  # Increased limit for better variety
            
            if not candidate_movies.exists():
                logger.warning("No candidate movies for deep learning")
                return self._content_based_advanced(user, count)
            
            # Calculate scores using enhanced feature-based approach
            movie_scores = []
            batch_size = 50
            
            for i in range(0, min(len(candidate_movies), 1500), batch_size):
                batch = candidate_movies[i:i+batch_size]
                
                for movie in batch:
                    try:
                        movie_features = self._extract_movie_features(movie)
                        if movie_features:
                            # Calculate multiple scoring components
                            feature_score = self._calculate_deep_learning_score(user_features, movie_features)
                            popularity_score = self._calculate_popularity_score(movie)
                            recency_score = self._calculate_recency_score(movie)
                            
                            # Weighted combination of scores
                            final_score = (
                                0.6 * feature_score +
                                0.2 * popularity_score +
                                0.2 * recency_score
                            )
                            
                            if final_score > 0.4:  # Lower threshold for more variety
                                movie_scores.append((movie, final_score, feature_score))
                    except Exception as e:
                        logger.warning(f"Error processing movie {movie.id}: {str(e)}")
                        continue
                
                # Break if we have enough high-scoring candidates
                if len([s for s in movie_scores if s[1] > 0.6]) >= count * 2:
                    break
            
            if not movie_scores:
                logger.warning("No movies could be scored with deep learning")
                return self._content_based_advanced(user, count)
            
            # Sort by final score and return top recommendations
            movie_scores.sort(key=lambda x: x[1], reverse=True)
            
            recommendations = []
            for movie, final_score, feature_score in movie_scores[:count]:
                confidence_level = "high" if feature_score > 0.7 else "medium" if feature_score > 0.4 else "low"
                reason = f"AI-powered recommendation with {confidence_level} confidence ({final_score:.2f})"
                recommendations.append((movie, final_score, reason))
                
            return recommendations
            
        except Exception as e:
            logger.error(f"Error in deep learning recommendations: {str(e)}")
            return self._content_based_advanced(user, count)
    
    def _hybrid_advanced(self, user, count: int) -> List[Tuple[Movie, float, str]]:
        """
        Advanced hybrid approach combining multiple algorithms with weighted scoring
        """
        try:
            # Get recommendations from different algorithms
            collab_recs = self._collaborative_filtering_advanced(user, count)
            content_recs = self._content_based_advanced(user, count)
            deep_recs = self._deep_learning_recommendations(user, count)
            
            # Validate that we have at least some recommendations
            total_recs = len(collab_recs) + len(content_recs) + len(deep_recs)
            if total_recs == 0:
                logger.warning(f"No recommendations from any algorithm for user {user.id}")
                return self._popularity_based_recommendations(count)
            
            # Combine recommendations with weighted scoring
            movie_scores = {}
            
            # Collaborative filtering weight: 0.4
            for movie, score, reason in collab_recs:
                if movie and hasattr(movie, 'id'):
                    movie_scores[movie.id] = movie_scores.get(movie.id, 0) + (score * 0.4)
            
            # Content-based weight: 0.35
            for movie, score, reason in content_recs:
                if movie and hasattr(movie, 'id'):
                    movie_scores[movie.id] = movie_scores.get(movie.id, 0) + (score * 0.35)
            
            # Deep learning weight: 0.25
            for movie, score, reason in deep_recs:
                if movie and hasattr(movie, 'id'):
                    movie_scores[movie.id] = movie_scores.get(movie.id, 0) + (score * 0.25)
            
            if not movie_scores:
                logger.warning("No valid movies found in hybrid scoring")
                return self._popularity_based_recommendations(count)
            
            # Sort by combined score
            sorted_movies = sorted(movie_scores.items(), key=lambda x: x[1], reverse=True)
            
            recommendations = []
            for movie_id, combined_score in sorted_movies[:count]:
                try:
                    movie = Movie.objects.get(id=movie_id)
                    reason = "Hybrid AI recommendation combining multiple algorithms"
                    recommendations.append((movie, combined_score, reason))
                except Movie.DoesNotExist:
                    logger.warning(f"Movie {movie_id} not found in hybrid recommendations")
                    continue
                    
            if not recommendations:
                logger.warning("No valid hybrid recommendations found")
                return self._popularity_based_recommendations(count)
                    
            return recommendations
            
        except Exception as e:
            logger.error(f"Error in hybrid recommendations: {str(e)}")
            return self._popularity_based_recommendations(count)
    
    def _build_user_item_matrix(self) -> pd.DataFrame:
        """
        Build user-item rating matrix for collaborative filtering
        """
        ratings = Rating.objects.all().values('user_id', 'movie_id', 'rating')
        df = pd.DataFrame(ratings)
        
        if df.empty:
            return pd.DataFrame()
            
        return df.pivot(index='user_id', columns='movie_id', values='rating')
    
    def _build_user_content_profile(self, user) -> Dict[str, Any]:
        """
        Build comprehensive user content profile based on rating history and preferences
        """
        user_ratings = Rating.objects.filter(user=user).select_related('movie').prefetch_related(
            'movie__genres', 'movie__languages', 'movie__countries',
            'movie__cast__person', 'movie__crew__person'
        )
        
        if not user_ratings.exists():
            return {}
        
        profile = {
            'genres': {},
            'languages': {},
            'countries': {},
            'cast': {},
            'directors': {},
            'years': {},
            'durations': [],
            'avg_rating': 0,
            'rating_variance': 0
        }
        
        # Calculate user's rating statistics
        ratings_list = [r.rating for r in user_ratings]
        profile['avg_rating'] = sum(ratings_list) / len(ratings_list)
        profile['rating_variance'] = sum((r - profile['avg_rating']) ** 2 for r in ratings_list) / len(ratings_list)
        
        # Focus on movies rated above user's average
        threshold = max(6, profile['avg_rating'] - 0.5)
        high_rated_movies = [r for r in user_ratings if r.rating >= threshold]
        
        total_weight = 0
        for rating in high_rated_movies:
            movie = rating.movie
            # Use exponential weighting for higher ratings
            weight = math.exp((rating.rating - profile['avg_rating']) / 2.0)
            total_weight += weight
            
            # Genre preferences with stronger weighting
            for genre in movie.genres.all():
                profile['genres'][genre.name] = profile['genres'].get(genre.name, 0) + weight
            
            # Language preferences
            for language in movie.languages.all():
                profile['languages'][language.name] = profile['languages'].get(language.name, 0) + weight
            
            # Country preferences
            for country in movie.countries.all():
                profile['countries'][country.name] = profile['countries'].get(country.name, 0) + weight
            
            # Cast preferences (top cast members)
            for cast_member in movie.cast.all()[:8]:  # Increased to top 8
                person_name = cast_member.person.name
                profile['cast'][person_name] = profile['cast'].get(person_name, 0) + weight * 0.8
            
            # Director preferences with higher weight
            directors = movie.crew.filter(role='Director')
            for director in directors:
                director_name = director.person.name
                profile['directors'][director_name] = profile['directors'].get(director_name, 0) + weight * 1.2
            
            # Year preferences with decade grouping
            if movie.year:
                decade = (movie.year // 10) * 10
                profile['years'][decade] = profile['years'].get(decade, 0) + weight
            
            # Duration preferences
            if movie.duration:
                profile['durations'].append(movie.duration)
        
        # Normalize preferences
        if total_weight > 0:
            for category in ['genres', 'languages', 'countries', 'cast', 'directors', 'years']:
                for key in profile[category]:
                    profile[category][key] /= total_weight
        
        # Calculate preferred duration range
        if profile['durations']:
            profile['avg_duration'] = sum(profile['durations']) / len(profile['durations'])
            profile['duration_std'] = math.sqrt(sum((d - profile['avg_duration']) ** 2 for d in profile['durations']) / len(profile['durations']))
        
        # Legacy compatibility
        profile['genre_preferences'] = profile['genres']
        profile['average_rating'] = profile['avg_rating']
        profile['preferred_years'] = [year for year in profile['years'].keys()]
        profile['total_ratings'] = len(ratings_list)
        
        return profile
    
    def _calculate_content_similarity(self, movie, user_profile: Dict[str, Any]) -> float:
        """
        Calculate comprehensive similarity between movie and user profile using multiple factors
        """
        similarity = 0.0
        weights = {
            'genres': 0.25,
            'cast': 0.15,
            'directors': 0.15,
            'rating': 0.15,
            'years': 0.10,
            'languages': 0.08,
            'countries': 0.07,
            'duration': 0.05
        }
        
        # Genre similarity (enhanced)
        genre_score = 0.0
        movie_genres = [g.name for g in movie.genres.all()]
        genre_preferences = user_profile.get('genres', {})
        
        if movie_genres and genre_preferences:
            genre_matches = [genre_preferences.get(genre, 0) for genre in movie_genres]
            if genre_matches:
                genre_score = sum(genre_matches) / len(movie_genres)
                # Bonus for multiple matching genres
                if len([g for g in genre_matches if g > 0.1]) > 1:
                    genre_score *= 1.2
        
        similarity += genre_score * weights['genres']
        
        # Cast similarity
        cast_score = 0.0
        movie_cast = [c.person.name for c in movie.cast.all()[:10]]
        cast_preferences = user_profile.get('cast', {})
        
        if movie_cast and cast_preferences:
            cast_matches = [cast_preferences.get(actor, 0) for actor in movie_cast]
            if cast_matches:
                cast_score = max(cast_matches)  # Best matching actor
        
        similarity += cast_score * weights['cast']
        
        # Director similarity
        director_score = 0.0
        movie_directors = [c.person.name for c in movie.crew.filter(role='Director')]
        director_preferences = user_profile.get('directors', {})
        
        if movie_directors and director_preferences:
            director_matches = [director_preferences.get(director, 0) for director in movie_directors]
            if director_matches:
                director_score = max(director_matches)
        
        similarity += director_score * weights['directors']
        
        # Rating similarity (improved)
        movie_avg_rating = movie.ratings.aggregate(avg=Avg('rating'))['avg'] or 0
        user_avg_rating = user_profile.get('avg_rating', 0)
        
        if movie_avg_rating > 0 and user_avg_rating > 0:
            rating_diff = abs(movie_avg_rating - user_avg_rating)
            rating_similarity = max(0, 1 - (rating_diff / 4.0))  # More lenient
            # Bonus for high-quality movies
            if movie_avg_rating >= 7.5:
                rating_similarity *= 1.1
            similarity += rating_similarity * weights['rating']
        
        # Year/decade similarity
        year_score = 0.0
        if movie.year:
            movie_decade = (movie.year // 10) * 10
            year_preferences = user_profile.get('years', {})
            year_score = year_preferences.get(movie_decade, 0)
        
        similarity += year_score * weights['years']
        
        # Language similarity
        language_score = 0.0
        movie_languages = [l.name for l in movie.languages.all()]
        language_preferences = user_profile.get('languages', {})
        
        if movie_languages and language_preferences:
            language_matches = [language_preferences.get(lang, 0) for lang in movie_languages]
            if language_matches:
                language_score = max(language_matches)
        
        similarity += language_score * weights['languages']
        
        # Country similarity
        country_score = 0.0
        movie_countries = [c.name for c in movie.countries.all()]
        country_preferences = user_profile.get('countries', {})
        
        if movie_countries and country_preferences:
            country_matches = [country_preferences.get(country, 0) for country in movie_countries]
            if country_matches:
                country_score = max(country_matches)
        
        similarity += country_score * weights['countries']
        
        # Duration similarity
        duration_score = 0.0
        if movie.duration and 'avg_duration' in user_profile:
            duration_diff = abs(movie.duration - user_profile['avg_duration'])
            duration_tolerance = user_profile.get('duration_std', 30)
            duration_score = max(0, 1 - (duration_diff / (duration_tolerance * 2)))
        
        similarity += duration_score * weights['duration']
        
        # Quality and popularity adjustments
        rating_count = movie.ratings.count()
        if rating_count >= 50 and movie_avg_rating >= 7.0:
            similarity *= 1.05  # Small boost for well-rated popular movies
        elif rating_count < 10:
            similarity *= 0.95  # Small penalty for movies with few ratings
        
        return min(similarity, 1.0)
    
    def _generate_content_reason(self, movie, user_profile: Dict[str, Any]) -> str:
        """
        Generate detailed explanation for content-based recommendation
        """
        reasons = []
        
        # Check genre matches
        movie_genres = [genre.name for genre in movie.genres.all()]
        genre_prefs = user_profile.get('genres', {})
        
        matching_genres = []
        for genre in movie_genres:
            if genre in genre_prefs and genre_prefs[genre] > 0.2:
                matching_genres.append(genre)
        
        if matching_genres:
            if len(matching_genres) == 1:
                reasons.append(f"you enjoy {matching_genres[0]} movies")
            elif len(matching_genres) == 2:
                reasons.append(f"you enjoy {matching_genres[0]} and {matching_genres[1]} movies")
            else:
                reasons.append(f"you enjoy {', '.join(matching_genres[:2])} and other similar genres")
        
        # Check cast matches
        movie_cast = [c.person.name for c in movie.cast.all()[:5]]
        cast_prefs = user_profile.get('cast', {})
        
        matching_actors = []
        for actor in movie_cast:
            if actor in cast_prefs and cast_prefs[actor] > 0.3:
                matching_actors.append(actor)
        
        if matching_actors:
            if len(matching_actors) == 1:
                reasons.append(f"you like movies with {matching_actors[0]}")
            else:
                reasons.append(f"it features actors you enjoy")
        
        # Check director matches
        movie_directors = [c.person.name for c in movie.crew.filter(role='Director')]
        director_prefs = user_profile.get('directors', {})
        
        matching_directors = []
        for director in movie_directors:
            if director in director_prefs and director_prefs[director] > 0.3:
                matching_directors.append(director)
        
        if matching_directors:
            reasons.append(f"you appreciate {matching_directors[0]}'s work")
        
        # Check decade preference
        if movie.year:
            movie_decade = (movie.year // 10) * 10
            year_prefs = user_profile.get('years', {})
            if movie_decade in year_prefs and year_prefs[movie_decade] > 0.2:
                decade_str = f"{movie_decade}s"
                reasons.append(f"you enjoy movies from the {decade_str}")
        
        # Check rating alignment
        movie_avg_rating = movie.ratings.aggregate(avg=Avg('rating'))['avg'] or 0
        user_avg_rating = user_profile.get('avg_rating', 0)
        
        if movie_avg_rating >= 7.5 and user_avg_rating >= 7.0:
            reasons.append("it's highly rated like movies you enjoy")
        elif abs(movie_avg_rating - user_avg_rating) < 1.0:
            reasons.append("it matches your rating preferences")
        
        # Check language preference
        movie_languages = [l.name for l in movie.languages.all()]
        lang_prefs = user_profile.get('languages', {})
        
        for language in movie_languages:
            if language in lang_prefs and lang_prefs[language] > 0.3:
                if language != 'English':  # Don't mention English as it's common
                    reasons.append(f"you enjoy {language} films")
                break
        
        if not reasons:
            return "Based on your viewing preferences and history"
        
        # Limit to top 3 reasons for readability
        top_reasons = reasons[:3]
        
        if len(top_reasons) == 1:
            return f"Because {top_reasons[0]}"
        elif len(top_reasons) == 2:
            return f"Because {top_reasons[0]} and {top_reasons[1]}"
        else:
            return f"Because {', '.join(top_reasons[:-1])}, and {top_reasons[-1]}"
    
    def _extract_user_features(self, user) -> Dict[str, float]:
        """
        Extract comprehensive numerical features for deep learning approach
        """
        # User behavior features
        total_ratings = Rating.objects.filter(user=user).count()
        avg_rating = Rating.objects.filter(user=user).aggregate(avg=Avg('rating'))['avg'] or 0
        
        # Genre diversity and preferences
        rated_genres = Genre.objects.filter(
            movies__ratings__user=user
        ).distinct().count()
        
        # Rating distribution analysis
        high_ratings = Rating.objects.filter(user=user, rating__gte=8).count()
        low_ratings = Rating.objects.filter(user=user, rating__lte=5).count()
        
        # Temporal patterns
        recent_interactions = UserMovieInteraction.objects.filter(
            user=user,
            created_at__gte=datetime.now() - timedelta(days=30)
        ).count()
        
        # User engagement metrics
        days_since_joined = max(1, (datetime.now() - user.date_joined).days)
        rating_frequency = total_ratings / days_since_joined
        
        # Movie year preferences
        recent_movie_ratings = Rating.objects.filter(
            user=user,
            movie__year__gte=2010
        ).count()
        
        return {
            'total_ratings': min(total_ratings / 100.0, 1.0),  # Normalized
            'avg_rating': avg_rating / 10.0,  # Normalized to 0-1
            'genre_diversity': min(rated_genres / 20.0, 1.0),  # Normalized
            'recent_activity': min(recent_interactions / 50.0, 1.0),  # Normalized
            'rating_frequency': min(rating_frequency * 10, 1.0),  # Normalized
            'high_rating_ratio': high_ratings / max(1, total_ratings),
            'low_rating_ratio': low_ratings / max(1, total_ratings),
            'modern_movie_preference': recent_movie_ratings / max(1, total_ratings)
        }
    
    def _get_movie_features_dataframe(self) -> pd.DataFrame:
        """
        Get movie features as DataFrame for ML processing
        """
        movies = Movie.objects.all().prefetch_related('genres', 'ratings')
        
        data = []
        for movie in movies:
            avg_rating = movie.ratings.aggregate(avg=Avg('rating'))['avg'] or 0
            rating_count = movie.ratings.count()
            
            data.append({
                'movie_id': movie.id,
                'year': movie.year or 2000,
                'avg_rating': avg_rating,
                'rating_count': rating_count,
                'genre_count': movie.genres.count(),
                'duration': movie.duration or 120
            })
        
        return pd.DataFrame(data)
    
    def _extract_movie_features(self, movie) -> Dict[str, float]:
        """
        Extract comprehensive movie features for deep learning
        """
        try:
            # Basic movie metrics
            avg_rating = movie.ratings.aggregate(avg=Avg('rating'))['avg'] or 0
            rating_count = movie.ratings.count()
            
            # Genre features
            genre_count = movie.genres.count()
            
            # Temporal features
            current_year = datetime.now().year
            movie_age = current_year - (movie.year or current_year)
            
            # Cast and crew features
            cast_count = movie.cast.count() if hasattr(movie, 'cast') else 0
            crew_count = movie.crew.count() if hasattr(movie, 'crew') else 0
            
            return {
                'avg_rating': avg_rating / 10.0,  # Normalized
                'rating_count': min(rating_count / 1000.0, 1.0),  # Normalized
                'genre_count': min(genre_count / 5.0, 1.0),  # Normalized
                'movie_age': max(0, 1 - (movie_age / 50.0)),  # Recency factor
                'duration': min((movie.duration or 120) / 180.0, 1.0),  # Normalized
                'cast_size': min(cast_count / 20.0, 1.0),  # Normalized
                'crew_size': min(crew_count / 50.0, 1.0),  # Normalized
                'popularity_score': min(math.log(rating_count + 1) / 10.0, 1.0)  # Log-normalized
            }
        except Exception as e:
            logger.warning(f"Error extracting features for movie {movie.id}: {str(e)}")
            return {}
    
    def _calculate_deep_learning_score(self, user_features: Dict[str, float], movie_features: Dict[str, float]) -> float:
        """
        Calculate recommendation score using enhanced feature-based neural approach
        """
        score = 0.0
        
        # Rating alignment with user preferences
        rating_alignment = 1 - abs(user_features['avg_rating'] - movie_features['avg_rating'])
        score += rating_alignment * 0.25
        
        # Popularity matching based on user's rating frequency
        popularity_match = min(movie_features['popularity_score'] + user_features['rating_frequency'], 1.0)
        score += popularity_match * 0.2
        
        # Genre diversity matching
        genre_match = min(movie_features['genre_count'] * user_features['genre_diversity'], 1.0)
        score += genre_match * 0.15
        
        # Quality threshold based on user's high rating ratio
        quality_bonus = movie_features['avg_rating'] * user_features['high_rating_ratio']
        score += quality_bonus * 0.2
        
        # Recency preference
        recency_match = movie_features['movie_age'] * user_features['modern_movie_preference']
        score += recency_match * 0.1
        
        # Activity-based boost
        activity_boost = user_features['recent_activity'] * 0.1
        score += activity_boost
        
        return min(score, 1.0)
    
    def _calculate_popularity_score(self, movie) -> float:
        """
        Calculate popularity score for a movie
        """
        try:
            rating_count = movie.ratings.count()
            avg_rating = movie.ratings.aggregate(avg=Avg('rating'))['avg'] or 0
            
            # Combine rating count and average rating
            popularity = (math.log(rating_count + 1) / 10.0) * (avg_rating / 10.0)
            return min(popularity, 1.0)
        except Exception:
            return 0.0
    
    def _calculate_recency_score(self, movie) -> float:
        """
        Calculate recency score based on movie release year
        """
        try:
            current_year = datetime.now().year
            movie_year = movie.year or current_year - 10
            
            # Movies from last 5 years get higher scores
            years_old = current_year - movie_year
            if years_old <= 5:
                return 1.0
            elif years_old <= 15:
                return max(0.3, 1.0 - (years_old - 5) / 20.0)
            else:
                return 0.1
        except Exception:
            return 0.5
    
    def _popularity_based_recommendations(self, count: int) -> List[Tuple[Movie, float, str]]:
        """
        Fallback to popularity-based recommendations
        """
        try:
            popular_movies = Movie.objects.annotate(
                avg_rating=Avg('ratings__rating'),
                rating_count=Count('ratings')
            ).filter(
                rating_count__gte=10,
                avg_rating__gte=7.0
            ).order_by('-rating_count', '-avg_rating')[:count]
            
            recommendations = []
            for movie in popular_movies:
                try:
                    confidence = min(movie.avg_rating / 10.0, 1.0) if movie.avg_rating else 0.7
                    recommendations.append((movie, confidence, "Popular and highly rated"))
                except Exception as e:
                    logger.warning(f"Error processing popular movie {movie.id}: {str(e)}")
                    continue
            
            # If we don't have enough popular movies, get any movies with ratings
            if len(recommendations) < count:
                additional_movies = Movie.objects.annotate(
                    avg_rating=Avg('ratings__rating'),
                    rating_count=Count('ratings')
                ).filter(
                    rating_count__gte=1
                ).exclude(
                    id__in=[rec[0].id for rec in recommendations]
                ).order_by('-rating_count')[:count - len(recommendations)]
                
                for movie in additional_movies:
                    try:
                        confidence = min(movie.avg_rating / 10.0, 1.0) if movie.avg_rating else 0.5
                        recommendations.append((movie, confidence, "Recommended movie"))
                    except Exception as e:
                        logger.warning(f"Error processing additional movie {movie.id}: {str(e)}")
                        continue
            
            # Final fallback - get any movies if we still don't have enough
            if len(recommendations) < min(count, 5):  # At least try to get 5 movies
                fallback_movies = Movie.objects.exclude(
                    id__in=[rec[0].id for rec in recommendations]
                ).order_by('id')[:count - len(recommendations)]
                
                for movie in fallback_movies:
                    recommendations.append((movie, 0.3, "Available movie"))
            
            return recommendations[:count]
            
        except Exception as e:
            logger.error(f"Error in popularity-based recommendations: {str(e)}")
            # Ultimate fallback - return empty list rather than crash
            return []
    
    def _hybrid_enhanced(self, user, count: int) -> List[Tuple[Movie, float, str]]:
        """
        Enhanced hybrid approach with better algorithm integration
        """
        return self._hybrid_advanced(user, count)
    
    def _ensemble_recommendations(self, user, count: int) -> List[Tuple[Movie, float, str]]:
        """
        Ensemble method combining multiple algorithms with advanced weighting
        """
        try:
            # Get recommendations from multiple algorithms
            algorithms = {
                'collaborative': self._collaborative_filtering_enhanced,
                'content': self._content_based_enhanced,
                'deep_learning': self._deep_learning_recommendations
            }
            
            all_recommendations = {}
            algorithm_weights = {'collaborative': 0.4, 'content': 0.35, 'deep_learning': 0.25}
            
            for algo_name, algo_func in algorithms.items():
                try:
                    recs = algo_func(user, count * 2)  # Get more for better ensemble
                    for movie, score, reason in recs:
                        if movie.id not in all_recommendations:
                            all_recommendations[movie.id] = {
                                'movie': movie,
                                'scores': {},
                                'reasons': []
                            }
                        all_recommendations[movie.id]['scores'][algo_name] = score
                        all_recommendations[movie.id]['reasons'].append(reason)
                except Exception as e:
                    logger.warning(f"Error in {algo_name} for ensemble: {str(e)}")
                    continue
            
            # Calculate ensemble scores
            final_recommendations = []
            for movie_id, data in all_recommendations.items():
                ensemble_score = 0.0
                total_weight = 0.0
                
                for algo_name, weight in algorithm_weights.items():
                    if algo_name in data['scores']:
                        ensemble_score += data['scores'][algo_name] * weight
                        total_weight += weight
                
                if total_weight > 0:
                    ensemble_score /= total_weight
                    # Bonus for movies recommended by multiple algorithms
                    algorithm_count = len(data['scores'])
                    if algorithm_count > 1:
                        ensemble_score *= (1 + 0.1 * (algorithm_count - 1))
                    
                    reason = f"Ensemble recommendation (confidence: {ensemble_score:.2f})"
                    final_recommendations.append((data['movie'], ensemble_score, reason))
            
            # Sort by ensemble score
            final_recommendations.sort(key=lambda x: x[1], reverse=True)
            return final_recommendations[:count]
            
        except Exception as e:
            logger.error(f"Error in ensemble recommendations: {str(e)}")
            return self._hybrid_advanced(user, count)
    
    def _gradient_boost_recommendations(self, user, count: int) -> List[Tuple[Movie, float, str]]:
        """
        Gradient Boosting based recommendations using advanced feature engineering
        """
        try:
            # Get user's rating history for training
            user_ratings = Rating.objects.filter(user=user).select_related('movie')
            
            if user_ratings.count() < 5:
                return self._content_based_enhanced(user, count)
            
            # Prepare training data
            X_train = []
            y_train = []
            
            for rating in user_ratings:
                movie_features = self._extract_movie_features(rating.movie)
                user_features = self._extract_user_features(user)
                
                # Combine features
                combined_features = list(movie_features.values()) + list(user_features.values())
                X_train.append(combined_features)
                y_train.append(rating.rating)
            
            if len(X_train) < 3:
                return self._content_based_enhanced(user, count)
            
            # Train gradient boosting model
            X_train = np.array(X_train)
            y_train = np.array(y_train)
            
            # Scale features
            X_train_scaled = self.robust_scaler.fit_transform(X_train)
            
            # Train model
            self.gradient_boost_model.fit(X_train_scaled, y_train)
            
            # Get candidate movies
            rated_movies = set(user_ratings.values_list('movie_id', flat=True))
            candidate_movies = Movie.objects.exclude(id__in=rated_movies)[:1000]
            
            recommendations = []
            user_features = self._extract_user_features(user)
            
            for movie in candidate_movies:
                try:
                    movie_features = self._extract_movie_features(movie)
                    combined_features = list(movie_features.values()) + list(user_features.values())
                    
                    # Predict rating
                    features_scaled = self.robust_scaler.transform([combined_features])
                    predicted_rating = self.gradient_boost_model.predict(features_scaled)[0]
                    
                    if predicted_rating > 3.5:  # Only recommend highly rated predictions
                        reason = f"Gradient Boost prediction: {predicted_rating:.2f}/5.0 based on your preferences"
                        recommendations.append((movie, predicted_rating, reason))
                        
                except Exception as e:
                    continue
            
            # Sort by predicted rating
            recommendations.sort(key=lambda x: x[1], reverse=True)
            return recommendations[:count]
            
        except Exception as e:
            logger.error(f"Gradient boost recommendations failed: {e}")
            return self._content_based_enhanced(user, count)
    
    def _neural_collaborative_filtering(self, user, count: int) -> List[Tuple[Movie, float, str]]:
        """
        Neural Collaborative Filtering implementation
        """
        try:
            # Extract user and movie embeddings
            user_features = self._extract_user_features(user)
            if not user_features:
                return self._content_based_enhanced(user, count)
            
            # Get candidate movies
            user_movie_ids = set(Rating.objects.filter(user=user).values_list('movie_id', flat=True))
            candidate_movies = Movie.objects.exclude(
                id__in=user_movie_ids
            ).filter(
                ratings__isnull=False
            ).distinct()[:1000]
            
            movie_scores = []
            for movie in candidate_movies:
                try:
                    movie_features = self._extract_movie_features(movie)
                    if movie_features:
                        # Neural CF score calculation
                        ncf_score = self._calculate_ncf_score(user_features, movie_features)
                        if ncf_score > 0.3:
                            movie_scores.append((movie, ncf_score, "Neural collaborative filtering"))
                except Exception as e:
                    logger.warning(f"Error in NCF for movie {movie.id}: {str(e)}")
                    continue
            
            movie_scores.sort(key=lambda x: x[1], reverse=True)
            return movie_scores[:count]
            
        except Exception as e:
            logger.error(f"Error in neural collaborative filtering: {str(e)}")
            return self._deep_learning_recommendations(user, count)
    
    def _calculate_ncf_score(self, user_features: Dict[str, float], movie_features: Dict[str, float]) -> float:
        """
        Calculate Neural Collaborative Filtering score
        """
        try:
            # Generalized Matrix Factorization component
            gmf_score = 0.0
            for key in user_features:
                if key in movie_features:
                    gmf_score += user_features[key] * movie_features[key]
            
            # Multi-Layer Perceptron component
            mlp_features = []
            for key in user_features:
                mlp_features.append(user_features[key])
            for key in movie_features:
                mlp_features.append(movie_features[key])
            
            # Simple MLP simulation with non-linear activation
            mlp_score = sum(mlp_features) / len(mlp_features)
            mlp_score = 1 / (1 + math.exp(-mlp_score))  # Sigmoid activation
            
            # Combine GMF and MLP
            final_score = 0.5 * gmf_score + 0.5 * mlp_score
            return min(final_score, 1.0)
            
        except Exception as e:
            logger.warning(f"Error calculating NCF score: {str(e)}")
            return 0.0
    
    def _apply_diversity_filter(self, recommendations: List[Tuple[Movie, float, str]], count: int) -> List[Tuple[Movie, float, str]]:
        """
        Apply diversity filtering to recommendations to avoid too similar movies
        """
        try:
            if len(recommendations) <= count:
                return recommendations
            
            diverse_recs = []
            used_genres = set()
            used_years = set()
            used_directors = set()
            
            # Sort by score first
            sorted_recs = sorted(recommendations, key=lambda x: x[1], reverse=True)
            
            for movie, score, reason in sorted_recs:
                if len(diverse_recs) >= count:
                    break
                
                # Check diversity criteria
                movie_genres = set(g.name for g in movie.genres.all())
                movie_decade = (movie.year // 10) * 10 if movie.year else None
                movie_directors = set(c.person.name for c in movie.crew.filter(role='Director'))
                
                # Diversity scoring
                diversity_score = 1.0
                
                # Genre diversity
                genre_overlap = len(movie_genres.intersection(used_genres))
                if genre_overlap > 0:
                    diversity_score *= (1 - genre_overlap * 0.2)
                
                # Year diversity
                if movie_decade in used_years:
                    diversity_score *= 0.8
                
                # Director diversity
                director_overlap = len(movie_directors.intersection(used_directors))
                if director_overlap > 0:
                    diversity_score *= 0.7
                
                # Accept if diversity score is acceptable or we need more recommendations
                if diversity_score > 0.5 or len(diverse_recs) < count // 2:
                    diverse_recs.append((movie, score * diversity_score, reason))
                    used_genres.update(movie_genres)
                    if movie_decade:
                        used_years.add(movie_decade)
                    used_directors.update(movie_directors)
            
            # Fill remaining slots with highest scored movies if needed
            if len(diverse_recs) < count:
                remaining_recs = [rec for rec in sorted_recs if rec not in diverse_recs]
                diverse_recs.extend(remaining_recs[:count - len(diverse_recs)])
            
            return diverse_recs[:count]
            
        except Exception as e:
            logger.warning(f"Error applying diversity filter: {str(e)}")
            return recommendations[:count]
    
    def _enhance_explanations(self, user, recommendations: List[Tuple[Movie, float, str]]) -> List[Tuple[Movie, float, str]]:
        """
        Enhance recommendation explanations with more detailed reasoning
        """
        try:
            enhanced_recs = []
            user_profile = self._build_user_content_profile(user)
            
            for movie, score, reason in recommendations:
                try:
                    # Generate enhanced explanation
                    enhanced_reason = self._generate_enhanced_explanation(movie, user_profile, score)
                    enhanced_recs.append((movie, score, enhanced_reason))
                except Exception as e:
                    logger.warning(f"Error enhancing explanation for movie {movie.id}: {str(e)}")
                    enhanced_recs.append((movie, score, reason))
            
            return enhanced_recs
            
        except Exception as e:
            logger.warning(f"Error enhancing explanations: {str(e)}")
            return recommendations
    
    def _generate_enhanced_explanation(self, movie, user_profile: Dict[str, Any], score: float) -> str:
        """
        Generate enhanced explanation for a recommendation
        """
        try:
            explanations = []
            
            # Confidence level
            confidence = "high" if score > 0.8 else "medium" if score > 0.6 else "moderate"
            
            # Genre matching
            movie_genres = [g.name for g in movie.genres.all()]
            genre_prefs = user_profile.get('genres', {})
            matching_genres = [g for g in movie_genres if genre_prefs.get(g, 0) > 0.2]
            
            if matching_genres:
                explanations.append(f"matches your {', '.join(matching_genres[:2])} preferences")
            
            # Rating quality
            avg_rating = movie.ratings.aggregate(avg=Avg('rating'))['avg'] or 0
            if avg_rating >= 8.0:
                explanations.append("highly rated by critics and audiences")
            elif avg_rating >= 7.0:
                explanations.append("well-received by viewers")
            
            # Popularity factor
            rating_count = movie.ratings.count()
            if rating_count >= 100:
                explanations.append("popular choice")
            elif rating_count >= 50:
                explanations.append("well-known movie")
            
            # Recency
            if movie.year and movie.year >= datetime.now().year - 3:
                explanations.append("recent release")
            
            if not explanations:
                return f"Recommended with {confidence} confidence based on your viewing history"
            
            explanation_text = ", ".join(explanations[:3])
            return f"Recommended with {confidence} confidence: {explanation_text}"
            
        except Exception as e:
            logger.warning(f"Error generating enhanced explanation: {str(e)}")
            return f"Recommended based on your preferences (confidence: {score:.2f})"
    
    def _fallback_recommendations(self, user, count: int) -> List[Tuple[Movie, float, str]]:
        """
        Fallback recommendations when ML algorithms fail
        """
        logger.warning(f"Using fallback recommendations for user {user.id}")
        return self._popularity_based_recommendations(count)

# Global instance
recommendation_engine = MovieRecommendationEngine()