from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from movies.models import Movie, Rating, Genre, Person, Cast, Crew
from users.models import User
from recommendations.models import UserPreference, UserMovieInteraction
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.feature_extraction.text import TfidfVectorizer
import pickle
import os

logger = logging.getLogger('recommendations')

class Command(BaseCommand):
    help = 'Preprocess and engineer features for ML models'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default='preprocessed_data',
            help='Directory to save preprocessed data'
        )
        parser.add_argument(
            '--min-interactions',
            type=int,
            default=5,
            help='Minimum interactions per user/movie'
        )
        parser.add_argument(
            '--feature-types',
            nargs='+',
            choices=['ratings', 'content', 'user_profiles', 'interactions', 'all'],
            default=['all'],
            help='Types of features to preprocess'
        )
        parser.add_argument(
            '--normalize',
            action='store_true',
            help='Normalize numerical features'
        )
        parser.add_argument(
            '--save-encoders',
            action='store_true',
            help='Save feature encoders for future use'
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
            self.stdout.write(self.style.SUCCESS('Starting data preprocessing...'))
            
            # Create output directory
            output_dir = settings.BASE_DIR / options['output_dir']
            output_dir.mkdir(exist_ok=True)
            
            feature_types = options['feature_types']
            if 'all' in feature_types:
                feature_types = ['ratings', 'content', 'user_profiles', 'interactions']
            
            # Process each feature type
            processed_data = {}
            
            if 'ratings' in feature_types:
                processed_data['ratings'] = self._preprocess_ratings(options)
            
            if 'content' in feature_types:
                processed_data['content'] = self._preprocess_content_features(options)
            
            if 'user_profiles' in feature_types:
                processed_data['user_profiles'] = self._preprocess_user_profiles(options)
            
            if 'interactions' in feature_types:
                processed_data['interactions'] = self._preprocess_interactions(options)
            
            # Save processed data
            self._save_processed_data(processed_data, output_dir, options)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Data preprocessing completed! Output saved to {output_dir}'
                )
            )
            
        except Exception as e:
            logger.error(f'Data preprocessing failed: {str(e)}')
            raise CommandError(f'Preprocessing failed: {str(e)}')
    
    def _preprocess_ratings(self, options):
        """Preprocess ratings data"""
        self.stdout.write('Preprocessing ratings data...')
        
        try:
            # Get ratings with user and movie info
            ratings_qs = Rating.objects.select_related(
                'user', 'movie'
            ).all()
            
            ratings_data = []
            for rating in ratings_qs:
                ratings_data.append({
                    'user_id': rating.user.id,
                    'movie_id': rating.movie.id,
                    'rating': rating.rating,
                    'timestamp': rating.created_at.timestamp(),
                    'user_age': self._calculate_user_age(rating.user),
                    'movie_year': rating.movie.release_date.year if rating.movie.release_date else None,
                    'movie_duration': rating.movie.duration or 0,
                    'movie_imdb_rating': rating.movie.imdb_rating or 0
                })
            
            ratings_df = pd.DataFrame(ratings_data)
            
            # Filter users and movies with minimum interactions
            min_interactions = options['min_interactions']
            
            user_counts = ratings_df['user_id'].value_counts()
            movie_counts = ratings_df['movie_id'].value_counts()
            
            valid_users = user_counts[user_counts >= min_interactions].index
            valid_movies = movie_counts[movie_counts >= min_interactions].index
            
            filtered_df = ratings_df[
                (ratings_df['user_id'].isin(valid_users)) &
                (ratings_df['movie_id'].isin(valid_movies))
            ]
            
            # Add temporal features
            filtered_df['rating_date'] = pd.to_datetime(
                filtered_df['timestamp'], unit='s'
            )
            filtered_df['day_of_week'] = filtered_df['rating_date'].dt.dayofweek
            filtered_df['hour'] = filtered_df['rating_date'].dt.hour
            filtered_df['month'] = filtered_df['rating_date'].dt.month
            
            # Add user rating statistics
            user_stats = filtered_df.groupby('user_id')['rating'].agg([
                'mean', 'std', 'count'
            ]).reset_index()
            user_stats.columns = ['user_id', 'user_avg_rating', 'user_rating_std', 'user_rating_count']
            
            # Add movie rating statistics
            movie_stats = filtered_df.groupby('movie_id')['rating'].agg([
                'mean', 'std', 'count'
            ]).reset_index()
            movie_stats.columns = ['movie_id', 'movie_avg_rating', 'movie_rating_std', 'movie_rating_count']
            
            # Merge statistics
            enriched_df = filtered_df.merge(user_stats, on='user_id')
            enriched_df = enriched_df.merge(movie_stats, on='movie_id')
            
            # Calculate rating deviation from user mean
            enriched_df['rating_deviation'] = (
                enriched_df['rating'] - enriched_df['user_avg_rating']
            )
            
            if self.verbose:
                self.stdout.write(f'Processed {len(enriched_df)} ratings')
                self.stdout.write(f'Valid users: {len(valid_users)}')
                self.stdout.write(f'Valid movies: {len(valid_movies)}')
            
            return enriched_df
            
        except Exception as e:
            logger.error(f'Ratings preprocessing failed: {str(e)}')
            raise
    
    def _preprocess_content_features(self, options):
        """Preprocess movie content features"""
        self.stdout.write('Preprocessing content features...')
        
        try:
            # Get movies with related data
            movies_qs = Movie.objects.prefetch_related(
                'genres', 'directors', 'cast__person', 'languages', 'countries'
            ).all()
            
            content_data = []
            for movie in movies_qs:
                # Basic features
                genres = [g.name for g in movie.genres.all()]
                directors = [d.person.name for d in movie.directors.all()]
                actors = [c.person.name for c in movie.cast.all()[:10]]  # Top 10 actors
                languages = [l.name for l in movie.languages.all()]
                countries = [c.name for c in movie.countries.all()]
                
                # Create feature vectors
                content_data.append({
                    'movie_id': movie.id,
                    'title': movie.title,
                    'year': movie.release_date.year if movie.release_date else 0,
                    'duration': movie.duration or 0,
                    'imdb_rating': movie.imdb_rating or 0,
                    'genres': '|'.join(genres),
                    'directors': '|'.join(directors),
                    'actors': '|'.join(actors),
                    'languages': '|'.join(languages),
                    'countries': '|'.join(countries),
                    'plot': movie.plot or '',
                    'genre_count': len(genres),
                    'director_count': len(directors),
                    'actor_count': len(actors),
                    'language_count': len(languages),
                    'country_count': len(countries)
                })
            
            content_df = pd.DataFrame(content_data)
            
            # Create TF-IDF features for text fields
            text_features = {}
            
            # Genre TF-IDF
            if not content_df['genres'].empty:
                genre_vectorizer = TfidfVectorizer(
                    max_features=100, 
                    stop_words='english',
                    token_pattern=r'[^|]+'
                )
                genre_tfidf = genre_vectorizer.fit_transform(
                    content_df['genres'].fillna('')
                )
                text_features['genre_tfidf'] = genre_tfidf
                text_features['genre_vectorizer'] = genre_vectorizer
            
            # Plot TF-IDF
            if not content_df['plot'].empty:
                plot_vectorizer = TfidfVectorizer(
                    max_features=200, 
                    stop_words='english'
                )
                plot_tfidf = plot_vectorizer.fit_transform(
                    content_df['plot'].fillna('')
                )
                text_features['plot_tfidf'] = plot_tfidf
                text_features['plot_vectorizer'] = plot_vectorizer
            
            # Normalize numerical features if requested
            if options['normalize']:
                numerical_cols = [
                    'year', 'duration', 'imdb_rating', 'genre_count',
                    'director_count', 'actor_count', 'language_count', 'country_count'
                ]
                
                scaler = StandardScaler()
                content_df[numerical_cols] = scaler.fit_transform(
                    content_df[numerical_cols]
                )
                text_features['numerical_scaler'] = scaler
            
            if self.verbose:
                self.stdout.write(f'Processed {len(content_df)} movies')
                self.stdout.write(f'Created {len(text_features)} text feature sets')
            
            return {
                'content_df': content_df,
                'text_features': text_features
            }
            
        except Exception as e:
            logger.error(f'Content features preprocessing failed: {str(e)}')
            raise
    
    def _preprocess_user_profiles(self, options):
        """Preprocess user profile features"""
        self.stdout.write('Preprocessing user profiles...')
        
        try:
            # Get user preferences
            user_prefs = UserPreference.objects.select_related('user').prefetch_related(
                'favorite_genres', 'favorite_directors', 'favorite_actors'
            ).all()
            
            user_data = []
            for pref in user_prefs:
                favorite_genres = [g.name for g in pref.favorite_genres.all()]
                favorite_directors = [d.name for d in pref.favorite_directors.all()]
                favorite_actors = [a.name for a in pref.favorite_actors.all()]
                
                user_data.append({
                    'user_id': pref.user.id,
                    'min_rating': pref.min_rating,
                    'max_duration': pref.max_duration or 0,
                    'favorite_genres': '|'.join(favorite_genres),
                    'favorite_directors': '|'.join(favorite_directors),
                    'favorite_actors': '|'.join(favorite_actors),
                    'genre_count': len(favorite_genres),
                    'director_count': len(favorite_directors),
                    'actor_count': len(favorite_actors),
                    'user_age': self._calculate_user_age(pref.user)
                })
            
            # Add users without preferences
            existing_user_ids = {data['user_id'] for data in user_data}
            all_users = User.objects.all()
            
            for user in all_users:
                if user.id not in existing_user_ids:
                    user_data.append({
                        'user_id': user.id,
                        'min_rating': 0,
                        'max_duration': 0,
                        'favorite_genres': '',
                        'favorite_directors': '',
                        'favorite_actors': '',
                        'genre_count': 0,
                        'director_count': 0,
                        'actor_count': 0,
                        'user_age': self._calculate_user_age(user)
                    })
            
            user_df = pd.DataFrame(user_data)
            
            # Create user preference TF-IDF features
            user_features = {}
            
            if not user_df['favorite_genres'].empty:
                genre_vectorizer = TfidfVectorizer(
                    max_features=50,
                    token_pattern=r'[^|]+'
                )
                genre_tfidf = genre_vectorizer.fit_transform(
                    user_df['favorite_genres'].fillna('')
                )
                user_features['user_genre_tfidf'] = genre_tfidf
                user_features['user_genre_vectorizer'] = genre_vectorizer
            
            if self.verbose:
                self.stdout.write(f'Processed {len(user_df)} user profiles')
            
            return {
                'user_df': user_df,
                'user_features': user_features
            }
            
        except Exception as e:
            logger.error(f'User profiles preprocessing failed: {str(e)}')
            raise
    
    def _preprocess_interactions(self, options):
        """Preprocess user-movie interactions"""
        self.stdout.write('Preprocessing user interactions...')
        
        try:
            # Get interactions
            interactions_qs = UserMovieInteraction.objects.select_related(
                'user', 'movie'
            ).all()
            
            interaction_data = []
            for interaction in interactions_qs:
                interaction_data.append({
                    'user_id': interaction.user.id,
                    'movie_id': interaction.movie.id,
                    'interaction_type': interaction.interaction_type,
                    'timestamp': interaction.created_at.timestamp(),
                    'interaction_score': self._get_interaction_score(
                        interaction.interaction_type
                    )
                })
            
            if not interaction_data:
                return pd.DataFrame()
            
            interactions_df = pd.DataFrame(interaction_data)
            
            # Add temporal features
            interactions_df['interaction_date'] = pd.to_datetime(
                interactions_df['timestamp'], unit='s'
            )
            interactions_df['day_of_week'] = interactions_df['interaction_date'].dt.dayofweek
            interactions_df['hour'] = interactions_df['interaction_date'].dt.hour
            
            # Aggregate interactions by user-movie pairs
            interaction_agg = interactions_df.groupby(['user_id', 'movie_id']).agg({
                'interaction_score': ['sum', 'mean', 'count'],
                'timestamp': ['min', 'max']
            }).reset_index()
            
            # Flatten column names
            interaction_agg.columns = [
                'user_id', 'movie_id', 'total_score', 'avg_score', 
                'interaction_count', 'first_interaction', 'last_interaction'
            ]
            
            # Calculate interaction duration
            interaction_agg['interaction_duration'] = (
                interaction_agg['last_interaction'] - 
                interaction_agg['first_interaction']
            )
            
            if self.verbose:
                self.stdout.write(f'Processed {len(interactions_df)} interactions')
                self.stdout.write(f'Aggregated to {len(interaction_agg)} user-movie pairs')
            
            return {
                'interactions_df': interactions_df,
                'interaction_agg': interaction_agg
            }
            
        except Exception as e:
            logger.error(f'Interactions preprocessing failed: {str(e)}')
            raise
    
    def _calculate_user_age(self, user):
        """Calculate user age from date_joined"""
        if hasattr(user, 'date_joined') and user.date_joined:
            return (timezone.now() - user.date_joined).days
        return 0
    
    def _get_interaction_score(self, interaction_type):
        """Get numerical score for interaction type"""
        scores = {
            'view': 1,
            'like': 3,
            'share': 2,
            'watchlist_add': 4,
            'watchlist_remove': -2,
            'rating': 5
        }
        return scores.get(interaction_type, 1)
    
    def _save_processed_data(self, processed_data, output_dir, options):
        """Save processed data to files"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            for data_type, data in processed_data.items():
                if isinstance(data, pd.DataFrame):
                    # Save DataFrame as CSV
                    filename = f'{data_type}_{timestamp}.csv'
                    filepath = output_dir / filename
                    data.to_csv(filepath, index=False)
                    
                    if self.verbose:
                        self.stdout.write(f'Saved {data_type} to {filepath}')
                
                elif isinstance(data, dict):
                    # Save complex data structures
                    for key, value in data.items():
                        if isinstance(value, pd.DataFrame):
                            filename = f'{data_type}_{key}_{timestamp}.csv'
                            filepath = output_dir / filename
                            value.to_csv(filepath, index=False)
                        
                        elif options['save_encoders'] and hasattr(value, 'fit'):
                            # Save sklearn objects (vectorizers, scalers, etc.)
                            filename = f'{data_type}_{key}_{timestamp}.pkl'
                            filepath = output_dir / filename
                            with open(filepath, 'wb') as f:
                                pickle.dump(value, f)
                        
                        if self.verbose:
                            self.stdout.write(f'Saved {data_type}.{key} to {filepath}')
            
            # Save metadata
            metadata = {
                'timestamp': timestamp,
                'options': options,
                'data_types': list(processed_data.keys()),
                'settings': {
                    'min_interactions': options['min_interactions'],
                    'normalize': options['normalize']
                }
            }
            
            metadata_path = output_dir / f'metadata_{timestamp}.json'
            import json
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)
            
            self.stdout.write(
                self.style.SUCCESS(f'Metadata saved to {metadata_path}')
            )
            
        except Exception as e:
            logger.error(f'Data saving failed: {str(e)}')
            raise