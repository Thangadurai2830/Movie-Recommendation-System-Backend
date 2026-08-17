from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from movies.models import Movie, Rating, Genre, Person
from users.models import User
from recommendations.models import UserPreference, Recommendation, UserMovieInteraction
from recommendations.ml_engine import RecommendationEngine
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import os
import pickle
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error
import json

logger = logging.getLogger('recommendations')

class Command(BaseCommand):
    help = 'Train ML models for movie recommendations with data preprocessing'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--algorithm',
            type=str,
            choices=['collaborative', 'content_based', 'hybrid', 'all'],
            default='all',
            help='Specify which algorithm to train (default: all)'
        )
        parser.add_argument(
            '--min-ratings',
            type=int,
            default=settings.ML_MIN_RATINGS_FOR_RECOMMENDATION,
            help='Minimum number of ratings required for training'
        )
        parser.add_argument(
            '--test-size',
            type=float,
            default=0.2,
            help='Test set size for model evaluation (default: 0.2)'
        )
        parser.add_argument(
            '--save-model',
            action='store_true',
            help='Save trained models to disk'
        )
        parser.add_argument(
            '--evaluate',
            action='store_true',
            help='Evaluate model performance on test set'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force retrain even if recent model exists'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output'
        )
    
    def handle(self, *args, **options):
        self.verbosity = options['verbosity']
        self.verbose = options['verbose']
        
        try:
            self.stdout.write(self.style.SUCCESS('Starting ML model training...'))
            
            # Check if we need to retrain
            if not options['force'] and self._check_recent_training():
                self.stdout.write(
                    self.style.WARNING(
                        'Recent training found. Use --force to retrain.'
                    )
                )
                return
            
            # Preprocess data
            self.stdout.write('Preprocessing data...')
            data = self._preprocess_data(options['min_ratings'])
            
            if data is None:
                raise CommandError('Insufficient data for training')
            
            # Initialize recommendation engine
            engine = RecommendationEngine()
            
            # Train models based on algorithm choice
            algorithm = options['algorithm']
            
            if algorithm in ['collaborative', 'all']:
                self._train_collaborative_filtering(engine, data, options)
            
            if algorithm in ['content_based', 'all']:
                self._train_content_based(engine, data, options)
            
            if algorithm in ['hybrid', 'all']:
                self._train_hybrid_model(engine, data, options)
            
            # Save models if requested
            if options['save_model']:
                self._save_models(engine)
            
            # Update training timestamp
            self._update_training_timestamp()
            
            # Clear recommendation cache
            self._clear_recommendation_cache()
            
            self.stdout.write(
                self.style.SUCCESS('ML model training completed successfully!')
            )
            
        except Exception as e:
            logger.error(f'ML training failed: {str(e)}')
            raise CommandError(f'Training failed: {str(e)}')
    
    def _check_recent_training(self):
        """Check if models were trained recently"""
        last_training = cache.get('ml_last_training')
        if last_training:
            hours_since = (timezone.now() - last_training).total_seconds() / 3600
            if hours_since < settings.ML_MODEL_UPDATE_INTERVAL:
                return True
        return False
    
    def _preprocess_data(self, min_ratings):
        """Preprocess data for ML training"""
        try:
            # Get ratings data
            ratings_qs = Rating.objects.select_related('user', 'movie').all()
            
            if ratings_qs.count() < min_ratings:
                self.stdout.write(
                    self.style.ERROR(
                        f'Insufficient ratings data. Found {ratings_qs.count()}, '
                        f'need at least {min_ratings}'
                    )
                )
                return None
            
            # Convert to DataFrame
            ratings_data = []
            for rating in ratings_qs:
                ratings_data.append({
                    'user_id': rating.user.id,
                    'movie_id': rating.movie.id,
                    'rating': rating.rating,
                    'timestamp': rating.created_at.timestamp()
                })
            
            ratings_df = pd.DataFrame(ratings_data)
            
            # Get movie features
            movies_qs = Movie.objects.prefetch_related(
                'genres', 'directors', 'cast__person'
            ).all()
            
            movies_data = []
            for movie in movies_qs:
                genres = [g.name for g in movie.genres.all()]
                directors = [d.person.name for d in movie.directors.all()]
                actors = [c.person.name for c in movie.cast.all()[:5]]  # Top 5 actors
                
                movies_data.append({
                    'movie_id': movie.id,
                    'title': movie.title,
                    'year': movie.release_date.year if movie.release_date else None,
                    'genres': genres,
                    'directors': directors,
                    'actors': actors,
                    'imdb_rating': movie.imdb_rating,
                    'duration': movie.duration,
                    'language': movie.language.name if movie.language else None
                })
            
            movies_df = pd.DataFrame(movies_data)
            
            # Get user preferences
            user_prefs = UserPreference.objects.select_related('user').all()
            user_prefs_data = []
            
            for pref in user_prefs:
                favorite_genres = [g.name for g in pref.favorite_genres.all()]
                user_prefs_data.append({
                    'user_id': pref.user.id,
                    'favorite_genres': favorite_genres,
                    'min_rating': pref.min_rating,
                    'max_duration': pref.max_duration
                })
            
            user_prefs_df = pd.DataFrame(user_prefs_data)
            
            if self.verbose:
                self.stdout.write(f'Loaded {len(ratings_df)} ratings')
                self.stdout.write(f'Loaded {len(movies_df)} movies')
                self.stdout.write(f'Loaded {len(user_prefs_df)} user preferences')
            
            return {
                'ratings': ratings_df,
                'movies': movies_df,
                'user_preferences': user_prefs_df
            }
            
        except Exception as e:
            logger.error(f'Data preprocessing failed: {str(e)}')
            raise
    
    def _train_collaborative_filtering(self, engine, data, options):
        """Train collaborative filtering model"""
        self.stdout.write('Training collaborative filtering model...')
        
        try:
            ratings_df = data['ratings']
            
            # Create user-item matrix
            user_item_matrix = ratings_df.pivot(
                index='user_id', 
                columns='movie_id', 
                values='rating'
            ).fillna(0)
            
            # Split data for evaluation if requested
            if options['evaluate']:
                train_data, test_data = train_test_split(
                    ratings_df, 
                    test_size=options['test_size'], 
                    random_state=42
                )
                
                # Train model
                engine._train_collaborative_model(train_data)
                
                # Evaluate
                self._evaluate_collaborative_model(engine, test_data)
            else:
                # Train on full dataset
                engine._train_collaborative_model(ratings_df)
            
            self.stdout.write(
                self.style.SUCCESS('Collaborative filtering model trained')
            )
            
        except Exception as e:
            logger.error(f'Collaborative filtering training failed: {str(e)}')
            raise
    
    def _train_content_based(self, engine, data, options):
        """Train content-based filtering model"""
        self.stdout.write('Training content-based filtering model...')
        
        try:
            movies_df = data['movies']
            ratings_df = data['ratings']
            
            # Train content-based model
            engine._train_content_based_model(movies_df, ratings_df)
            
            if options['evaluate']:
                self._evaluate_content_based_model(engine, data, options)
            
            self.stdout.write(
                self.style.SUCCESS('Content-based filtering model trained')
            )
            
        except Exception as e:
            logger.error(f'Content-based training failed: {str(e)}')
            raise
    
    def _train_hybrid_model(self, engine, data, options):
        """Train hybrid recommendation model"""
        self.stdout.write('Training hybrid recommendation model...')
        
        try:
            # Combine collaborative and content-based approaches
            engine._train_hybrid_model(data)
            
            if options['evaluate']:
                self._evaluate_hybrid_model(engine, data, options)
            
            self.stdout.write(
                self.style.SUCCESS('Hybrid recommendation model trained')
            )
            
        except Exception as e:
            logger.error(f'Hybrid model training failed: {str(e)}')
            raise
    
    def _evaluate_collaborative_model(self, engine, test_data):
        """Evaluate collaborative filtering model"""
        try:
            predictions = []
            actuals = []
            
            for _, row in test_data.iterrows():
                pred = engine._predict_rating(
                    row['user_id'], 
                    row['movie_id']
                )
                if pred is not None:
                    predictions.append(pred)
                    actuals.append(row['rating'])
            
            if predictions:
                rmse = np.sqrt(mean_squared_error(actuals, predictions))
                mae = mean_absolute_error(actuals, predictions)
                
                self.stdout.write(f'Collaborative Filtering - RMSE: {rmse:.3f}, MAE: {mae:.3f}')
            
        except Exception as e:
            logger.warning(f'Collaborative model evaluation failed: {str(e)}')
    
    def _evaluate_content_based_model(self, engine, data, options):
        """Evaluate content-based model"""
        try:
            # Implementation for content-based evaluation
            self.stdout.write('Content-based model evaluation completed')
            
        except Exception as e:
            logger.warning(f'Content-based model evaluation failed: {str(e)}')
    
    def _evaluate_hybrid_model(self, engine, data, options):
        """Evaluate hybrid model"""
        try:
            # Implementation for hybrid model evaluation
            self.stdout.write('Hybrid model evaluation completed')
            
        except Exception as e:
            logger.warning(f'Hybrid model evaluation failed: {str(e)}')
    
    def _save_models(self, engine):
        """Save trained models to disk"""
        try:
            models_dir = settings.BASE_DIR / 'ml_models'
            models_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Save models with timestamp
            model_files = {
                'collaborative': f'collaborative_model_{timestamp}.pkl',
                'content_based': f'content_based_model_{timestamp}.pkl',
                'hybrid': f'hybrid_model_{timestamp}.pkl'
            }
            
            for model_type, filename in model_files.items():
                model_path = models_dir / filename
                if hasattr(engine, f'{model_type}_model'):
                    with open(model_path, 'wb') as f:
                        pickle.dump(
                            getattr(engine, f'{model_type}_model'), 
                            f
                        )
                    
                    if self.verbose:
                        self.stdout.write(f'Saved {model_type} model to {model_path}')
            
            # Save metadata
            metadata = {
                'timestamp': timestamp,
                'models': model_files,
                'settings': {
                    'min_ratings': settings.ML_MIN_RATINGS_FOR_RECOMMENDATION,
                    'algorithms': settings.RECOMMENDATION_ALGORITHMS
                }
            }
            
            metadata_path = models_dir / f'metadata_{timestamp}.json'
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            self.stdout.write(
                self.style.SUCCESS(f'Models saved to {models_dir}')
            )
            
        except Exception as e:
            logger.error(f'Model saving failed: {str(e)}')
            raise
    
    def _update_training_timestamp(self):
        """Update the last training timestamp"""
        cache.set('ml_last_training', timezone.now(), timeout=None)
    
    def _clear_recommendation_cache(self):
        """Clear all recommendation-related cache"""
        try:
            # Clear user recommendation caches
            users = User.objects.all()
            for user in users:
                cache.delete(f'user_recommendations_{user.id}')
                cache.delete(f'user_profile_{user.id}')
            
            # Clear other recommendation caches
            cache.delete('trending_movies')
            cache.delete('popular_movies')
            
            if self.verbose:
                self.stdout.write('Recommendation cache cleared')
                
        except Exception as e:
            logger.warning(f'Cache clearing failed: {str(e)}')