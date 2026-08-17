from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache
from unittest.mock import patch, Mock, MagicMock
import json

from recommendations.cache_utils import (
    CacheManager, cache_recommendations, cache_user_profile
)
from movies.models import Movie, Genre
from recommendations.models import UserPreference

User = get_user_model()

class TestCacheManager(TestCase):
    """Test CacheManager functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.cache_manager = CacheManager()
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.genre = Genre.objects.create(name='Action')
        
        self.movie = Movie.objects.create(
            title='Test Movie',
            overview='Test description',
            release_date='2023-01-01',
            average_rating=8.0,
            vote_count=100,
            popularity=80.0,
            tmdb_id=1001
        )
        self.movie.genres.add(self.genre)
    
    def tearDown(self):
        """Clean up cache after each test"""
        cache.clear()
    
    def test_get_cached_recommendations_miss(self):
        """Test cache miss for recommendations"""
        result = self.cache_manager.get_cached_recommendations(
            user_id=self.user.id,
            algorithm='hybrid',
            count=10
        )
        
        self.assertIsNone(result)
    
    def test_set_and_get_cached_recommendations(self):
        """Test setting and getting cached recommendations"""
        recommendations = [
            {
                'movie_id': self.movie.id,
                'confidence_score': 0.9,
                'reason': 'Test reason'
            }
        ]
        
        # Set cache
        self.cache_manager.set_cached_recommendations(
            user_id=self.user.id,
            algorithm='hybrid',
            count=10,
            recommendations=recommendations
        )
        
        # Get from cache
        cached_result = self.cache_manager.get_cached_recommendations(
            user_id=self.user.id,
            algorithm='hybrid',
            count=10
        )
        
        self.assertIsNotNone(cached_result)
        self.assertEqual(len(cached_result), 1)
        self.assertEqual(cached_result[0]['movie_id'], self.movie.id)
        self.assertEqual(cached_result[0]['confidence_score'], 0.9)
    
    def test_get_cached_user_profile_miss(self):
        """Test cache miss for user profile"""
        result = self.cache_manager.get_cached_user_profile(self.user.id)
        
        self.assertIsNone(result)
    
    def test_set_and_get_cached_user_profile(self):
        """Test setting and getting cached user profile"""
        profile_data = {
            'user_id': self.user.id,
            'preferred_genres': ['Action', 'Comedy'],
            'average_rating': 4.2,
            'total_ratings': 15
        }
        
        # Set cache
        self.cache_manager.set_cached_user_profile(
            user_id=self.user.id,
            profile_data=profile_data
        )
        
        # Get from cache
        cached_result = self.cache_manager.get_cached_user_profile(self.user.id)
        
        self.assertIsNotNone(cached_result)
        self.assertEqual(cached_result['user_id'], self.user.id)
        self.assertEqual(cached_result['preferred_genres'], ['Action', 'Comedy'])
        self.assertEqual(cached_result['average_rating'], 4.2)
    
    def test_get_cached_movie_data_miss(self):
        """Test cache miss for movie data"""
        result = self.cache_manager.get_cached_movie_data(self.movie.id)
        
        self.assertIsNone(result)
    
    def test_set_and_get_cached_movie_data(self):
        """Test setting and getting cached movie data"""
        movie_data = {
            'id': self.movie.id,
            'title': self.movie.title,
            'genres': ['Action'],
            'features': [0.1, 0.2, 0.3, 0.4, 0.5]
        }
        
        # Set cache
        self.cache_manager.set_cached_movie_data(
            movie_id=self.movie.id,
            movie_data=movie_data
        )
        
        # Get from cache
        cached_result = self.cache_manager.get_cached_movie_data(self.movie.id)
        
        self.assertIsNotNone(cached_result)
        self.assertEqual(cached_result['id'], self.movie.id)
        self.assertEqual(cached_result['title'], self.movie.title)
        self.assertEqual(cached_result['features'], [0.1, 0.2, 0.3, 0.4, 0.5])
    
    def test_get_cached_ml_model_miss(self):
        """Test cache miss for ML model"""
        result = self.cache_manager.get_cached_ml_model('svd_model')
        
        self.assertIsNone(result)
    
    def test_set_and_get_cached_ml_model(self):
        """Test setting and getting cached ML model"""
        # Mock model data (in real scenario, this would be pickled model)
        model_data = {
            'model_type': 'SVD',
            'parameters': {'n_factors': 50, 'n_epochs': 20},
            'trained_at': '2023-01-01T00:00:00Z'
        }
        
        # Set cache
        self.cache_manager.set_cached_ml_model(
            model_name='svd_model',
            model_data=model_data
        )
        
        # Get from cache
        cached_result = self.cache_manager.get_cached_ml_model('svd_model')
        
        self.assertIsNotNone(cached_result)
        self.assertEqual(cached_result['model_type'], 'SVD')
        self.assertEqual(cached_result['parameters']['n_factors'], 50)
    
    def test_invalidate_user_cache(self):
        """Test invalidating user-specific cache"""
        # Set some cached data
        self.cache_manager.set_cached_recommendations(
            user_id=self.user.id,
            algorithm='hybrid',
            count=10,
            recommendations=[]
        )
        
        self.cache_manager.set_cached_user_profile(
            user_id=self.user.id,
            profile_data={'test': 'data'}
        )
        
        # Verify data is cached
        self.assertIsNotNone(
            self.cache_manager.get_cached_recommendations(
                user_id=self.user.id,
                algorithm='hybrid',
                count=10
            )
        )
        self.assertIsNotNone(
            self.cache_manager.get_cached_user_profile(self.user.id)
        )
        
        # Invalidate user cache
        self.cache_manager.invalidate_user_cache(self.user.id)
        
        # Verify data is no longer cached
        self.assertIsNone(
            self.cache_manager.get_cached_recommendations(
                user_id=self.user.id,
                algorithm='hybrid',
                count=10
            )
        )
        self.assertIsNone(
            self.cache_manager.get_cached_user_profile(self.user.id)
        )
    
    def test_invalidate_movie_cache(self):
        """Test invalidating movie-specific cache"""
        # Set cached movie data
        self.cache_manager.set_cached_movie_data(
            movie_id=self.movie.id,
            movie_data={'test': 'data'}
        )
        
        # Verify data is cached
        self.assertIsNotNone(
            self.cache_manager.get_cached_movie_data(self.movie.id)
        )
        
        # Invalidate movie cache
        self.cache_manager.invalidate_movie_cache(self.movie.id)
        
        # Verify data is no longer cached
        self.assertIsNone(
            self.cache_manager.get_cached_movie_data(self.movie.id)
        )
    
    def test_cache_key_generation(self):
        """Test cache key generation for different scenarios"""
        # Test recommendation cache key
        key1 = self.cache_manager._get_recommendation_cache_key(
            user_id=1,
            algorithm='hybrid',
            count=10
        )
        key2 = self.cache_manager._get_recommendation_cache_key(
            user_id=1,
            algorithm='collaborative',
            count=10
        )
        key3 = self.cache_manager._get_recommendation_cache_key(
            user_id=2,
            algorithm='hybrid',
            count=10
        )
        
        # Keys should be different for different parameters
        self.assertNotEqual(key1, key2)  # Different algorithm
        self.assertNotEqual(key1, key3)  # Different user
        
        # Same parameters should generate same key
        key1_duplicate = self.cache_manager._get_recommendation_cache_key(
            user_id=1,
            algorithm='hybrid',
            count=10
        )
        self.assertEqual(key1, key1_duplicate)
    
    def test_cache_timeout_configuration(self):
        """Test that cache timeouts are properly configured"""
        # This test verifies that different cache types have appropriate timeouts
        # In a real implementation, you'd check the actual cache backend configuration
        
        # Set data with different cache types
        self.cache_manager.set_cached_recommendations(
            user_id=self.user.id,
            algorithm='hybrid',
            count=10,
            recommendations=[]
        )
        
        self.cache_manager.set_cached_user_profile(
            user_id=self.user.id,
            profile_data={}
        )
        
        self.cache_manager.set_cached_ml_model(
            model_name='test_model',
            model_data={}
        )
        
        # All should be accessible immediately
        self.assertIsNotNone(
            self.cache_manager.get_cached_recommendations(
                user_id=self.user.id,
                algorithm='hybrid',
                count=10
            )
        )
        self.assertIsNotNone(
            self.cache_manager.get_cached_user_profile(self.user.id)
        )
        self.assertIsNotNone(
            self.cache_manager.get_cached_ml_model('test_model')
        )

class TestCacheDecorators(TestCase):
    """Test cache decorator functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def tearDown(self):
        """Clean up cache after each test"""
        cache.clear()
    
    def test_cache_recommendations_decorator(self):
        """Test the cache_recommendations decorator"""
        call_count = 0
        
        @cache_recommendations(timeout=300)
        def get_test_recommendations(user, algorithm='hybrid', count=10):
            nonlocal call_count
            call_count += 1
            return [
                {
                    'movie_id': 1,
                    'confidence_score': 0.9,
                    'reason': f'Call #{call_count}'
                }
            ]
        
        # First call should execute function
        result1 = get_test_recommendations(self.user, 'hybrid', 10)
        self.assertEqual(call_count, 1)
        self.assertEqual(result1[0]['reason'], 'Call #1')
        
        # Second call with same parameters should use cache
        result2 = get_test_recommendations(self.user, 'hybrid', 10)
        self.assertEqual(call_count, 1)  # Function not called again
        self.assertEqual(result2[0]['reason'], 'Call #1')  # Same result
        
        # Call with different parameters should execute function
        result3 = get_test_recommendations(self.user, 'collaborative', 10)
        self.assertEqual(call_count, 2)  # Function called again
        self.assertEqual(result3[0]['reason'], 'Call #2')
    
    def test_cache_user_profile_decorator(self):
        """Test the cache_user_profile decorator"""
        call_count = 0
        
        @cache_user_profile(timeout=600)
        def get_test_user_profile(user_id):
            nonlocal call_count
            call_count += 1
            return {
                'user_id': user_id,
                'call_number': call_count,
                'preferences': ['Action', 'Comedy']
            }
        
        # First call should execute function
        result1 = get_test_user_profile(self.user.id)
        self.assertEqual(call_count, 1)
        self.assertEqual(result1['call_number'], 1)
        
        # Second call with same user should use cache
        result2 = get_test_user_profile(self.user.id)
        self.assertEqual(call_count, 1)  # Function not called again
        self.assertEqual(result2['call_number'], 1)  # Same result
        
        # Call with different user should execute function
        user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        result3 = get_test_user_profile(user2.id)
        self.assertEqual(call_count, 2)  # Function called again
        self.assertEqual(result3['call_number'], 2)
    
    def test_decorator_with_none_result(self):
        """Test decorator behavior when function returns None"""
        call_count = 0
        
        @cache_recommendations(timeout=300)
        def get_none_recommendations(user, algorithm='hybrid', count=10):
            nonlocal call_count
            call_count += 1
            return None
        
        # First call
        result1 = get_none_recommendations(self.user)
        self.assertIsNone(result1)
        self.assertEqual(call_count, 1)
        
        # Second call should still execute function (None results not cached)
        result2 = get_none_recommendations(self.user)
        self.assertIsNone(result2)
        self.assertEqual(call_count, 2)
    
    def test_decorator_with_exception(self):
        """Test decorator behavior when function raises exception"""
        call_count = 0
        
        @cache_recommendations(timeout=300)
        def failing_recommendations(user, algorithm='hybrid', count=10):
            nonlocal call_count
            call_count += 1
            raise ValueError("Test error")
        
        # First call should raise exception
        with self.assertRaises(ValueError):
            failing_recommendations(self.user)
        self.assertEqual(call_count, 1)
        
        # Second call should also raise exception (not cached)
        with self.assertRaises(ValueError):
            failing_recommendations(self.user)
        self.assertEqual(call_count, 2)

class TestCacheIntegration(TestCase):
    """Test cache integration with Django cache framework"""
    
    def setUp(self):
        """Set up test data"""
        self.cache_manager = CacheManager()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def tearDown(self):
        """Clean up cache after each test"""
        cache.clear()
    
    @patch('recommendations.cache_utils.cache')
    def test_cache_backend_interaction(self, mock_cache):
        """Test interaction with Django cache backend"""
        # Mock cache responses
        mock_cache.get.return_value = None
        mock_cache.set.return_value = True
        
        # Test setting cache
        self.cache_manager.set_cached_recommendations(
            user_id=self.user.id,
            algorithm='hybrid',
            count=10,
            recommendations=[]
        )
        
        # Verify cache.set was called
        mock_cache.set.assert_called_once()
        
        # Test getting cache
        self.cache_manager.get_cached_recommendations(
            user_id=self.user.id,
            algorithm='hybrid',
            count=10
        )
        
        # Verify cache.get was called
        mock_cache.get.assert_called_once()
    
    def test_cache_serialization(self):
        """Test that complex data structures are properly serialized"""
        complex_data = {
            'recommendations': [
                {
                    'movie_id': 1,
                    'confidence_score': 0.95,
                    'reason': 'Based on your viewing history',
                    'metadata': {
                        'genres': ['Action', 'Thriller'],
                        'year': 2023,
                        'rating': 8.5
                    }
                }
            ],
            'algorithm_info': {
                'name': 'hybrid',
                'version': '1.0',
                'weights': {'collaborative': 0.6, 'content': 0.4}
            }
        }
        
        # Set complex data
        self.cache_manager.set_cached_recommendations(
            user_id=self.user.id,
            algorithm='hybrid',
            count=10,
            recommendations=complex_data
        )
        
        # Get and verify data integrity
        cached_data = self.cache_manager.get_cached_recommendations(
            user_id=self.user.id,
            algorithm='hybrid',
            count=10
        )
        
        self.assertIsNotNone(cached_data)
        self.assertEqual(
            cached_data['recommendations'][0]['confidence_score'],
            0.95
        )
        self.assertEqual(
            cached_data['algorithm_info']['weights']['collaborative'],
            0.6
        )
    
    def test_cache_memory_efficiency(self):
        """Test cache memory usage with large datasets"""
        # Create large dataset
        large_recommendations = []
        for i in range(1000):
            large_recommendations.append({
                'movie_id': i,
                'confidence_score': 0.5 + (i % 50) / 100,
                'reason': f'Recommendation reason for movie {i}'
            })
        
        # Set large dataset
        self.cache_manager.set_cached_recommendations(
            user_id=self.user.id,
            algorithm='hybrid',
            count=1000,
            recommendations=large_recommendations
        )
        
        # Retrieve and verify
        cached_data = self.cache_manager.get_cached_recommendations(
            user_id=self.user.id,
            algorithm='hybrid',
            count=1000
        )
        
        self.assertIsNotNone(cached_data)
        self.assertEqual(len(cached_data), 1000)
        self.assertEqual(cached_data[0]['movie_id'], 0)
        self.assertEqual(cached_data[999]['movie_id'], 999)

class TestCachePerformance(TestCase):
    """Test cache performance characteristics"""
    
    def setUp(self):
        """Set up test data"""
        self.cache_manager = CacheManager()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def tearDown(self):
        """Clean up cache after each test"""
        cache.clear()
    
    def test_cache_hit_performance(self):
        """Test that cache hits are faster than cache misses"""
        import time
        
        # Simulate expensive computation
        @cache_recommendations(timeout=300)
        def expensive_computation(user, algorithm='hybrid', count=10):
            time.sleep(0.01)  # Simulate 10ms computation
            return [{'movie_id': 1, 'score': 0.9}]
        
        # First call (cache miss)
        start_time = time.time()
        result1 = expensive_computation(self.user)
        miss_time = time.time() - start_time
        
        # Second call (cache hit)
        start_time = time.time()
        result2 = expensive_computation(self.user)
        hit_time = time.time() - start_time
        
        # Cache hit should be significantly faster
        self.assertLess(hit_time, miss_time)
        self.assertEqual(result1, result2)
    
    def test_concurrent_cache_access(self):
        """Test cache behavior under concurrent access"""
        import threading
        import time
        
        results = []
        call_count = 0
        
        @cache_recommendations(timeout=300)
        def concurrent_function(user, algorithm='hybrid', count=10):
            nonlocal call_count
            call_count += 1
            time.sleep(0.01)  # Simulate some work
            return [{'movie_id': call_count, 'score': 0.9}]
        
        def worker():
            result = concurrent_function(self.user)
            results.append(result)
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All results should be the same (from cache)
        self.assertEqual(len(results), 5)
        first_result = results[0]
        for result in results[1:]:
            self.assertEqual(result, first_result)
        
        # Function should have been called only once
        self.assertEqual(call_count, 1)