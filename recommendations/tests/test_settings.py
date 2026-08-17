"""Test settings for recommendations app tests"""

from django.test import TestCase
from django.conf import settings
from django.core.cache import cache
from django.test.utils import override_settings
import tempfile
import os

# Test database configuration
TEST_DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'OPTIONS': {
            'timeout': 20,
        },
        'TEST': {
            'NAME': ':memory:',
        }
    }
}

# Test cache configuration
TEST_CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-cache',
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
            'CULL_FREQUENCY': 3,
        }
    }
}

# Test Celery configuration
TEST_CELERY_SETTINGS = {
    'CELERY_TASK_ALWAYS_EAGER': True,
    'CELERY_TASK_EAGER_PROPAGATES': True,
    'CELERY_BROKER_URL': 'memory://',
    'CELERY_RESULT_BACKEND': 'cache+memory://',
}

# Test media and static files
TEST_MEDIA_ROOT = tempfile.mkdtemp()
TEST_STATIC_ROOT = tempfile.mkdtemp()

# Test logging configuration
TEST_LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'ERROR',  # Only show errors during tests
        },
    },
    'loggers': {
        'recommendations': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

# Test email configuration
TEST_EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

class BaseTestCase(TestCase):
    """Base test case with common setup for all recommendation tests"""
    
    @classmethod
    def setUpClass(cls):
        """Set up class-level test configuration"""
        super().setUpClass()
        
        # Ensure test settings are applied
        cls._original_databases = getattr(settings, 'DATABASES', {})
        cls._original_caches = getattr(settings, 'CACHES', {})
        cls._original_media_root = getattr(settings, 'MEDIA_ROOT', '')
        cls._original_static_root = getattr(settings, 'STATIC_ROOT', '')
    
    @classmethod
    def tearDownClass(cls):
        """Clean up class-level test configuration"""
        super().tearDownClass()
        
        # Clean up temporary directories
        import shutil
        try:
            if os.path.exists(TEST_MEDIA_ROOT):
                shutil.rmtree(TEST_MEDIA_ROOT)
            if os.path.exists(TEST_STATIC_ROOT):
                shutil.rmtree(TEST_STATIC_ROOT)
        except OSError:
            pass
    
    def setUp(self):
        """Set up test case"""
        super().setUp()
        
        # Clear cache before each test
        cache.clear()
        
        # Reset any global state
        self._reset_ml_models()
    
    def tearDown(self):
        """Clean up after test case"""
        super().tearDown()
        
        # Clear cache after each test
        cache.clear()
    
    def _reset_ml_models(self):
        """Reset ML models to clean state"""
        # Clear any cached models
        from recommendations.ml_engine import MovieRecommendationEngine
        
        # Reset engine state if needed
        try:
            engine = MovieRecommendationEngine()
            engine._models = {}
            engine._model_trained = {
                'collaborative': False,
                'content': False,
                'neural_cf': False
            }
        except Exception:
            # Engine might not be initialized, which is fine
            pass

class MLTestCase(BaseTestCase):
    """Test case specifically for ML-related tests"""
    
    def setUp(self):
        """Set up ML test case"""
        super().setUp()
        
        # Import required modules
        from django.contrib.auth import get_user_model
        from movies.models import Movie, Genre
        from recommendations.models import UserMovieInteraction
        
        User = get_user_model()
        
        # Create test users
        self.users = []
        for i in range(5):
            user = User.objects.create_user(
                username=f'testuser{i}',
                email=f'test{i}@example.com',
                password='testpass123'
            )
            self.users.append(user)
        
        # Create test genres
        self.genres = []
        genre_names = ['Action', 'Comedy', 'Drama', 'Thriller', 'Romance']
        for name in genre_names:
            genre = Genre.objects.create(name=name)
            self.genres.append(genre)
        
        # Create test movies
        self.movies = []
        for i in range(10):
            movie = Movie.objects.create(
                title=f'Test Movie {i}',
                overview=f'Description for test movie {i}',
                release_date='2023-01-01',
                average_rating=5.0 + (i % 5),
                vote_count=100 + i * 10,
                popularity=50.0 + i * 5,
                tmdb_id=1000 + i
            )
            
            # Add random genres
            movie.genres.add(self.genres[i % len(self.genres)])
            if i % 2 == 0:
                movie.genres.add(self.genres[(i + 1) % len(self.genres)])
            
            self.movies.append(movie)
        
        # Create test interactions
        self._create_test_interactions()
    
    def _create_test_interactions(self):
        """Create test user-movie interactions"""
        from recommendations.models import UserMovieInteraction
        
        # Create rating interactions
        for user_idx, user in enumerate(self.users):
            for movie_idx in range(min(5, len(self.movies))):
                movie = self.movies[movie_idx]
                rating = 3.0 + (user_idx + movie_idx) % 3  # Ratings between 3-5
                
                UserMovieInteraction.objects.create(
                    user=user,
                    movie=movie,
                    interaction_type='rating',
                    rating=rating
                )
        
        # Create view interactions
        for user_idx, user in enumerate(self.users):
            for movie_idx in range(5, min(8, len(self.movies))):
                movie = self.movies[movie_idx]
                
                UserMovieInteraction.objects.create(
                    user=user,
                    movie=movie,
                    interaction_type='view'
                )

class APITestCase(BaseTestCase):
    """Test case specifically for API-related tests"""
    
    def setUp(self):
        """Set up API test case"""
        super().setUp()
        
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework.authtoken.models import Token
        
        User = get_user_model()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create API client
        self.client = APIClient()
        
        # Create and set authentication token
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
    
    def authenticate_user(self, user=None):
        """Authenticate a specific user"""
        if user is None:
            user = self.user
        
        from rest_framework.authtoken.models import Token
        
        token, created = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        return token
    
    def unauthenticate(self):
        """Remove authentication"""
        self.client.credentials()

class CacheTestCase(BaseTestCase):
    """Test case specifically for cache-related tests"""
    
    def setUp(self):
        """Set up cache test case"""
        super().setUp()
        
        from recommendations.cache_utils import CacheManager
        
        # Initialize cache manager
        self.cache_manager = CacheManager()
    
    def assert_cache_hit(self, cache_key):
        """Assert that a cache key exists"""
        self.assertIsNotNone(cache.get(cache_key))
    
    def assert_cache_miss(self, cache_key):
        """Assert that a cache key does not exist"""
        self.assertIsNone(cache.get(cache_key))
    
    def get_cache_stats(self):
        """Get cache statistics (if available)"""
        # This would depend on your cache backend
        # For testing purposes, we'll return a mock stats object
        return {
            'hits': 0,
            'misses': 0,
            'keys': len(cache._cache) if hasattr(cache, '_cache') else 0
        }

class TaskTestCase(BaseTestCase):
    """Test case specifically for Celery task tests"""
    
    def setUp(self):
        """Set up task test case"""
        super().setUp()
        
        # Ensure Celery is in eager mode for testing
        from django.conf import settings
        
        self._original_celery_eager = getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False)
        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.CELERY_TASK_EAGER_PROPAGATES = True
    
    def tearDown(self):
        """Clean up task test case"""
        super().tearDown()
        
        # Restore original Celery settings
        from django.conf import settings
        settings.CELERY_TASK_ALWAYS_EAGER = self._original_celery_eager
    
    def assert_task_success(self, task_result):
        """Assert that a task completed successfully"""
        self.assertTrue(task_result.successful())
    
    def assert_task_failure(self, task_result):
        """Assert that a task failed"""
        self.assertTrue(task_result.failed())
    
    def assert_task_retry(self, task_result):
        """Assert that a task was retried"""
        # This would depend on your task implementation
        # For now, we'll check if the task is in a retry state
        self.assertIn(task_result.state, ['RETRY', 'PENDING'])

# Test data fixtures
class TestDataMixin:
    """Mixin providing common test data creation methods"""
    
    def create_test_user(self, username='testuser', email='test@example.com'):
        """Create a test user"""
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        return User.objects.create_user(
            username=username,
            email=email,
            password='testpass123'
        )
    
    def create_test_movie(self, title='Test Movie', tmdb_id=1001):
        """Create a test movie"""
        from movies.models import Movie
        
        return Movie.objects.create(
            title=title,
            overview='Test movie description',
            release_date='2023-01-01',
            average_rating=7.5,
            vote_count=100,
            popularity=75.0,
            tmdb_id=tmdb_id
        )
    
    def create_test_genre(self, name='Action'):
        """Create a test genre"""
        from movies.models import Genre
        
        return Genre.objects.create(name=name)
    
    def create_test_interaction(self, user, movie, interaction_type='rating', rating=8.0):
        """Create a test user-movie interaction"""
        from recommendations.models import UserMovieInteraction
        
        return UserMovieInteraction.objects.create(
            user=user,
            movie=movie,
            interaction_type=interaction_type,
            rating=rating if interaction_type == 'rating' else None
        )
    
    def create_test_feedback(self, user, movie, feedback_type='helpful', rating=4):
        """Create a test recommendation feedback"""
        from recommendations.models import RecommendationFeedback
        
        return RecommendationFeedback.objects.create(
            user=user,
            movie=movie,
            feedback_type=feedback_type,
            rating=rating
        )
    
    def create_test_preference(self, user, min_rating=7.0, max_rating=10.0):
        """Create a test user preference"""
        from recommendations.models import UserPreference
        
        return UserPreference.objects.create(
            user=user,
            min_rating=min_rating,
            max_rating=max_rating,
            min_year=2000,
            max_year=2023
        )

# Performance testing utilities
class PerformanceTestMixin:
    """Mixin providing performance testing utilities"""
    
    def assert_execution_time(self, func, max_time_seconds=1.0, *args, **kwargs):
        """Assert that a function executes within a time limit"""
        import time
        
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        
        self.assertLess(
            execution_time,
            max_time_seconds,
            f"Function took {execution_time:.3f}s, expected < {max_time_seconds}s"
        )
        
        return result
    
    def measure_execution_time(self, func, *args, **kwargs):
        """Measure and return execution time of a function"""
        import time
        
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        
        return result, execution_time
    
    def assert_memory_usage(self, func, max_memory_mb=100, *args, **kwargs):
        """Assert that a function uses less than specified memory"""
        import tracemalloc
        
        tracemalloc.start()
        result = func(*args, **kwargs)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        peak_mb = peak / 1024 / 1024
        
        self.assertLess(
            peak_mb,
            max_memory_mb,
            f"Function used {peak_mb:.2f}MB, expected < {max_memory_mb}MB"
        )
        
        return result

# Mock utilities
class MockUtilities:
    """Utilities for creating mocks in tests"""
    
    @staticmethod
    def mock_ml_model():
        """Create a mock ML model"""
        from unittest.mock import Mock
        
        model = Mock()
        model.predict.return_value = [0.8, 0.6, 0.9, 0.7, 0.5]
        model.fit.return_value = model
        return model
    
    @staticmethod
    def mock_recommendation_data():
        """Create mock recommendation data"""
        return [
            {
                'movie_id': 1,
                'confidence_score': 0.95,
                'reason': 'Based on your viewing history'
            },
            {
                'movie_id': 2,
                'confidence_score': 0.87,
                'reason': 'Similar to movies you liked'
            },
            {
                'movie_id': 3,
                'confidence_score': 0.82,
                'reason': 'Popular in your preferred genres'
            }
        ]
    
    @staticmethod
    def mock_user_profile():
        """Create mock user profile data"""
        return {
            'user_id': 1,
            'preferred_genres': ['Action', 'Thriller'],
            'average_rating': 4.2,
            'total_ratings': 25,
            'favorite_actors': ['Actor 1', 'Actor 2'],
            'viewing_patterns': {
                'preferred_time': 'evening',
                'session_length': 'long'
            }
        }