import unittest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import transaction
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from recommendations.ml_engine import MovieRecommendationEngine
from movies.models import Movie, Genre, Rating
from recommendations.models import UserMovieInteraction

User = get_user_model()

class TestMovieRecommendationEngine(TestCase):
    def setUp(self):
        """Set up test data"""
        self.engine = MovieRecommendationEngine()
        
        # Create test users
        self.user1 = User.objects.create_user(
            username='testuser1',
            email='test1@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        
        # Create test genres
        self.action_genre = Genre.objects.create(name='Action')
        self.comedy_genre = Genre.objects.create(name='Comedy')
        self.drama_genre = Genre.objects.create(name='Drama')
        
        # Create test movies
        self.movie1 = Movie.objects.create(
            title='Test Movie 1',
            overview='Action movie description',
            release_date='2023-01-01',
            average_rating=8.5,
            vote_count=1000,
            popularity=85.0,
            tmdb_id=1001
        )
        self.movie1.genres.add(self.action_genre)
        
        self.movie2 = Movie.objects.create(
            title='Test Movie 2',
            overview='Comedy movie description',
            release_date='2023-02-01',
            average_rating=7.5,
            vote_count=800,
            popularity=75.0,
            tmdb_id=1002
        )
        self.movie2.genres.add(self.comedy_genre)
        
        self.movie3 = Movie.objects.create(
            title='Test Movie 3',
            overview='Drama movie description',
            release_date='2023-03-01',
            average_rating=9.0,
            vote_count=1200,
            popularity=90.0,
            tmdb_id=1003
        )
        self.movie3.genres.add(self.drama_genre)
        
        # Create test ratings
        Rating.objects.create(user=self.user1, movie=self.movie1, rating=5.0)
        Rating.objects.create(user=self.user1, movie=self.movie2, rating=3.0)
        Rating.objects.create(user=self.user2, movie=self.movie1, rating=4.0)
        Rating.objects.create(user=self.user2, movie=self.movie3, rating=5.0)
        
        # Create test interactions
        UserMovieInteraction.objects.create(
            user=self.user1,
            movie=self.movie1,
            interaction_type='view'
        )
        UserMovieInteraction.objects.create(
            user=self.user1,
            movie=self.movie2,
            interaction_type='like'
        )
    
    def test_get_user_movie_matrix(self):
        """Test user-movie matrix creation"""
        matrix, user_ids, movie_ids = self.engine._get_user_movie_matrix()
        
        self.assertIsInstance(matrix, np.ndarray)
        self.assertEqual(len(user_ids), 2)  # 2 users
        self.assertEqual(len(movie_ids), 3)  # 3 movies
        self.assertEqual(matrix.shape, (2, 3))
        
        # Check that ratings are correctly placed
        user1_idx = user_ids.index(self.user1.id)
        movie1_idx = movie_ids.index(self.movie1.id)
        self.assertEqual(matrix[user1_idx, movie1_idx], 5.0)
    
    def test_content_based_filtering(self):
        """Test content-based filtering"""
        recommendations = self.engine._content_based_filtering(
            user=self.user1,
            count=2
        )
        
        self.assertIsInstance(recommendations, list)
        self.assertLessEqual(len(recommendations), 2)
        
        # Each recommendation should be a tuple of (movie, score, reason)
        for rec in recommendations:
            self.assertIsInstance(rec, tuple)
            self.assertEqual(len(rec), 3)
            self.assertIsInstance(rec[0], Movie)
            self.assertIsInstance(rec[1], (int, float))
            self.assertIsInstance(rec[2], str)
    
    def test_collaborative_filtering_enhanced(self):
        """Test enhanced collaborative filtering"""
        with patch.object(self.engine, '_train_all_models'):
            recommendations = self.engine._collaborative_filtering_enhanced(
                user=self.user1,
                count=2
            )
            
            self.assertIsInstance(recommendations, list)
            self.assertLessEqual(len(recommendations), 2)
            
            # Each recommendation should be a tuple of (movie, score, reason)
            for rec in recommendations:
                self.assertIsInstance(rec, tuple)
                self.assertEqual(len(rec), 3)
                self.assertIsInstance(rec[0], Movie)
                self.assertIsInstance(rec[1], (int, float))
                self.assertIsInstance(rec[2], str)
    
    def test_hybrid_recommendations(self):
        """Test hybrid recommendation algorithm"""
        with patch.object(self.engine, '_content_based_filtering') as mock_content, \
             patch.object(self.engine, '_collaborative_filtering_enhanced') as mock_collab:
            
            # Mock return values
            mock_content.return_value = [(self.movie2, 0.8, 'Content-based')]
            mock_collab.return_value = [(self.movie3, 0.9, 'Collaborative')]
            
            recommendations = self.engine._hybrid_recommendations(
                user=self.user1,
                count=2
            )
            
            self.assertIsInstance(recommendations, list)
            self.assertLessEqual(len(recommendations), 2)
            
            # Verify both methods were called
            mock_content.assert_called_once()
            mock_collab.assert_called_once()
    
    def test_get_recommendations_with_cache(self):
        """Test recommendation retrieval with caching"""
        with patch('recommendations.ml_engine.cache') as mock_cache:
            mock_cache.get.return_value = None  # No cached results
            
            with patch.object(self.engine, '_hybrid_recommendations') as mock_hybrid:
                mock_hybrid.return_value = [(self.movie2, 0.8, 'Hybrid')]
                
                recommendations = self.engine.get_recommendations(
                    user=self.user1,
                    count=1,
                    algorithm='hybrid'
                )
                
                self.assertEqual(len(recommendations), 1)
                mock_hybrid.assert_called_once()
                mock_cache.set.assert_called_once()
    
    def test_get_recommendations_invalid_algorithm(self):
        """Test recommendation with invalid algorithm"""
        with self.assertRaises(ValueError):
            self.engine.get_recommendations(
                user=self.user1,
                count=5,
                algorithm='invalid_algorithm'
            )
    
    def test_apply_diversity_filter(self):
        """Test diversity filtering"""
        recommendations = [
            (self.movie1, 0.9, 'Test reason 1'),
            (self.movie2, 0.8, 'Test reason 2'),
            (self.movie3, 0.7, 'Test reason 3')
        ]
        
        filtered = self.engine._apply_diversity_filter(recommendations, diversity_threshold=0.5)
        
        self.assertIsInstance(filtered, list)
        self.assertLessEqual(len(filtered), len(recommendations))
        
        # All returned movies should be unique
        movie_ids = [rec[0].id for rec in filtered]
        self.assertEqual(len(movie_ids), len(set(movie_ids)))
    
    def test_enhance_explanations(self):
        """Test explanation enhancement"""
        recommendations = [
            (self.movie1, 0.9, 'Basic reason'),
            (self.movie2, 0.8, 'Another reason')
        ]
        
        enhanced = self.engine._enhance_explanations(recommendations, self.user1)
        
        self.assertEqual(len(enhanced), len(recommendations))
        
        for original, enhanced_rec in zip(recommendations, enhanced):
            self.assertEqual(original[0], enhanced_rec[0])  # Same movie
            self.assertEqual(original[1], enhanced_rec[1])  # Same score
            # Explanation should be enhanced (different or more detailed)
            self.assertIsInstance(enhanced_rec[2], str)
    
    def test_train_all_models(self):
        """Test model training"""
        # This test ensures the training doesn't crash
        try:
            self.engine._train_all_models()
        except Exception as e:
            self.fail(f"Model training failed with exception: {e}")
        
        # Check that models are created (they might be None if insufficient data)
        # This is expected behavior for small test datasets
        self.assertTrue(hasattr(self.engine, 'svd_model'))
        self.assertTrue(hasattr(self.engine, 'nmf_model'))
    
    def test_insufficient_data_handling(self):
        """Test handling of insufficient data scenarios"""
        # Create a user with no ratings
        new_user = User.objects.create_user(
            username='newuser',
            email='new@example.com',
            password='testpass123'
        )
        
        recommendations = self.engine.get_recommendations(
            user=new_user,
            count=5,
            algorithm='collaborative'
        )
        
        # Should return some recommendations (fallback to popular movies)
        self.assertIsInstance(recommendations, list)
    
    def test_recommendation_deduplication(self):
        """Test that recommendations don't include movies user has already rated"""
        recommendations = self.engine.get_recommendations(
            user=self.user1,
            count=10,
            algorithm='content'
        )
        
        # Get movies user has already rated
        rated_movie_ids = set(
            Rating.objects.filter(user=self.user1).values_list('movie_id', flat=True)
        )
        
        # Recommended movies should not include already rated movies
        recommended_movie_ids = {rec[0].id for rec in recommendations}
        self.assertEqual(len(rated_movie_ids.intersection(recommended_movie_ids)), 0)
    
    def test_recommendation_scoring(self):
        """Test that recommendation scores are within valid range"""
        recommendations = self.engine.get_recommendations(
            user=self.user1,
            count=5,
            algorithm='hybrid'
        )
        
        for movie, score, reason in recommendations:
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)
            self.assertIsInstance(reason, str)
            self.assertGreater(len(reason), 0)

class TestMLEnginePerformance(TestCase):
    """Performance tests for ML engine"""
    
    def setUp(self):
        self.engine = MovieRecommendationEngine()
    
    @patch('recommendations.ml_engine.cache')
    def test_caching_performance(self, mock_cache):
        """Test that caching improves performance"""
        user = User.objects.create_user(
            username='perfuser',
            email='perf@example.com',
            password='testpass123'
        )
        
        # First call - cache miss
        mock_cache.get.return_value = None
        
        with patch.object(self.engine, '_hybrid_recommendations') as mock_hybrid:
            mock_hybrid.return_value = []
            
            self.engine.get_recommendations(user=user, count=5)
            
            # Verify cache was checked and set
            mock_cache.get.assert_called()
            mock_cache.set.assert_called()
    
    def test_large_dataset_handling(self):
        """Test engine handles larger datasets without crashing"""
        # This is a basic test to ensure the engine doesn't crash with more data
        # In a real scenario, you'd want to test with actual large datasets
        
        try:
            # Create multiple users and movies
            users = []
            movies = []
            
            for i in range(10):
                user = User.objects.create_user(
                    username=f'user{i}',
                    email=f'user{i}@example.com',
                    password='testpass123'
                )
                users.append(user)
                
                movie = Movie.objects.create(
                    title=f'Movie {i}',
                    overview=f'Description for movie {i}',
                    release_date='2023-01-01',
                    average_rating=7.0 + (i % 3),
                    vote_count=100 + i * 10,
                    popularity=50.0 + i * 5,
                    tmdb_id=2000 + i
                )
                movies.append(movie)
            
            # Create ratings
            for user in users[:5]:
                for movie in movies[:5]:
                    Rating.objects.create(
                        user=user,
                        movie=movie,
                        rating=3.0 + (hash(f'{user.id}{movie.id}') % 3)
                    )
            
            # Test recommendations
            recommendations = self.engine.get_recommendations(
                user=users[0],
                count=5,
                algorithm='hybrid'
            )
            
            self.assertIsInstance(recommendations, list)
            
        except Exception as e:
            self.fail(f"Large dataset handling failed: {e}")