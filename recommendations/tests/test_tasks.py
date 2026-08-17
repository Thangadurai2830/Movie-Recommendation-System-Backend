from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch, Mock, MagicMock
from datetime import timedelta
from celery.exceptions import Retry

from recommendations.tasks import (
    retrain_ml_models,
    generate_recommendations_for_user,
    update_trending_movies,
    cleanup_old_recommendations,
    precompute_user_recommendations
)
from recommendations.models import (
    Recommendation, TrendingMovie, UserMovieInteraction, RecommendationFeedback
)
from movies.models import Movie, Genre, Rating

User = get_user_model()

class TestCeleryTasks(TestCase):
    """Test Celery background tasks"""
    
    def setUp(self):
        """Set up test data"""
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

class TestRetrainMLModelsTask(TestCeleryTasks):
    """Test ML model retraining task"""
    
    @patch('recommendations.tasks.recommendation_engine')
    @patch('recommendations.tasks.cache_manager')
    def test_retrain_models_with_sufficient_data(self, mock_cache_manager, mock_engine):
        """Test retraining when there's sufficient new data"""
        # Create recent ratings
        for i in range(15):
            Rating.objects.create(
                user=self.user,
                movie=self.movie,
                rating=4.0 + (i % 2),
                created_at=timezone.now() - timedelta(minutes=30)
            )
        
        # Mock the task
        task_mock = Mock()
        task_mock.request.retries = 0
        
        result = retrain_ml_models.apply(args=[], kwargs={})
        
        # Should complete successfully
        self.assertIn('retrained successfully', result.result)
    
    @patch('recommendations.tasks.Rating')
    def test_retrain_models_insufficient_data(self, mock_rating):
        """Test skipping retraining when there's insufficient new data"""
        # Mock insufficient recent ratings
        mock_rating.objects.filter.return_value.count.return_value = 5
        
        task_mock = Mock()
        task_mock.request.retries = 0
        
        result = retrain_ml_models.apply(args=[], kwargs={})
        
        # Should skip retraining
        self.assertIn('insufficient new data', result.result)
    
    @patch('recommendations.tasks.recommendation_engine')
    def test_retrain_models_error_handling(self, mock_engine):
        """Test error handling in retraining task"""
        # Create sufficient recent ratings
        for i in range(15):
            Rating.objects.create(
                user=self.user,
                movie=self.movie,
                rating=4.0,
                created_at=timezone.now() - timedelta(minutes=30)
            )
        
        # Mock engine to raise an exception
        mock_engine._train_all_models.side_effect = Exception("Training failed")
        
        # The task should handle the exception and retry
        with self.assertRaises(Exception):
            retrain_ml_models.apply(args=[], kwargs={})

class TestGenerateRecommendationsTask(TestCeleryTasks):
    """Test recommendation generation task"""
    
    @patch('recommendations.tasks.recommendation_engine')
    def test_generate_recommendations_success(self, mock_engine):
        """Test successful recommendation generation"""
        # Mock recommendation engine response
        mock_engine.get_recommendations.return_value = [
            (self.movie, 0.9, 'Test reason')
        ]
        
        result = generate_recommendations_for_user.apply(
            args=[self.user.id],
            kwargs={'algorithm': 'hybrid', 'count': 10}
        )
        
        # Should complete successfully
        self.assertIn('Generated 1 recommendations', result.result)
        
        # Verify recommendation was stored
        recommendation = Recommendation.objects.get(
            user=self.user,
            movie=self.movie
        )
        self.assertEqual(recommendation.confidence_score, 0.9)
        self.assertEqual(recommendation.reason, 'Test reason')
        self.assertEqual(recommendation.algorithm, 'hybrid')
    
    def test_generate_recommendations_invalid_user(self):
        """Test handling of invalid user ID"""
        with self.assertRaises(Exception):
            generate_recommendations_for_user.apply(
                args=[99999],  # Non-existent user ID
                kwargs={}
            )
    
    @patch('recommendations.tasks.recommendation_engine')
    def test_generate_recommendations_engine_error(self, mock_engine):
        """Test handling of recommendation engine errors"""
        # Mock engine to raise an exception
        mock_engine.get_recommendations.side_effect = Exception("Engine error")
        
        with self.assertRaises(Exception):
            generate_recommendations_for_user.apply(
                args=[self.user.id],
                kwargs={}
            )

class TestUpdateTrendingMoviesTask(TestCeleryTasks):
    """Test trending movies update task"""
    
    def test_update_trending_movies_success(self):
        """Test successful trending movies update"""
        # Create test data for trending calculation
        cutoff_date = timezone.now() - timedelta(days=7)
        
        # Create recent ratings and interactions
        for i in range(10):
            Rating.objects.create(
                user=self.user,
                movie=self.movie,
                rating=4.5,
                created_at=cutoff_date + timedelta(days=1)
            )
            
            UserMovieInteraction.objects.create(
                user=self.user,
                movie=self.movie,
                interaction_type='view',
                created_at=cutoff_date + timedelta(days=1)
            )
        
        result = update_trending_movies.apply(args=[], kwargs={})
        
        # Should complete successfully
        self.assertIn('Updated', result.result)
        
        # Verify trending movie was created
        trending_movie = TrendingMovie.objects.get(movie=self.movie)
        self.assertEqual(trending_movie.rank, 1)
        self.assertGreater(trending_movie.trending_score, 0)
    
    def test_update_trending_movies_no_data(self):
        """Test trending movies update with no qualifying data"""
        result = update_trending_movies.apply(args=[], kwargs={})
        
        # Should complete but with 0 trending movies
        self.assertIn('Updated 0 trending movies', result.result)
        
        # No trending movies should be created
        self.assertEqual(TrendingMovie.objects.count(), 0)
    
    @patch('recommendations.tasks.Movie')
    def test_update_trending_movies_error_handling(self, mock_movie):
        """Test error handling in trending movies update"""
        # Mock to raise an exception
        mock_movie.objects.annotate.side_effect = Exception("Database error")
        
        with self.assertRaises(Exception):
            update_trending_movies.apply(args=[], kwargs={})

class TestCleanupOldRecommendationsTask(TestCeleryTasks):
    """Test cleanup task"""
    
    def test_cleanup_old_recommendations(self):
        """Test cleanup of old recommendations"""
        # Create old recommendation
        old_date = timezone.now() - timedelta(days=35)
        old_recommendation = Recommendation.objects.create(
            user=self.user,
            movie=self.movie,
            algorithm='hybrid',
            confidence_score=0.8,
            reason='Test reason'
        )
        old_recommendation.created_at = old_date
        old_recommendation.save()
        
        # Create recent recommendation
        recent_recommendation = Recommendation.objects.create(
            user=self.user,
            movie=self.movie,
            algorithm='content',
            confidence_score=0.7,
            reason='Recent reason'
        )
        
        result = cleanup_old_recommendations.apply(args=[], kwargs={})
        
        # Should complete successfully
        self.assertIn('Cleaned up', result.result)
        
        # Old recommendation should be deleted, recent one should remain
        self.assertFalse(
            Recommendation.objects.filter(id=old_recommendation.id).exists()
        )
        self.assertTrue(
            Recommendation.objects.filter(id=recent_recommendation.id).exists()
        )
    
    def test_cleanup_old_interactions(self):
        """Test cleanup of old interactions"""
        # Create old interaction
        old_date = timezone.now() - timedelta(days=95)
        old_interaction = UserMovieInteraction.objects.create(
            user=self.user,
            movie=self.movie,
            interaction_type='view'
        )
        old_interaction.created_at = old_date
        old_interaction.save()
        
        # Create recent interaction
        recent_interaction = UserMovieInteraction.objects.create(
            user=self.user,
            movie=self.movie,
            interaction_type='like'
        )
        
        result = cleanup_old_recommendations.apply(args=[], kwargs={})
        
        # Should complete successfully
        self.assertIn('Cleaned up', result.result)
        
        # Old interaction should be deleted, recent one should remain
        self.assertFalse(
            UserMovieInteraction.objects.filter(id=old_interaction.id).exists()
        )
        self.assertTrue(
            UserMovieInteraction.objects.filter(id=recent_interaction.id).exists()
        )
    
    @patch('recommendations.tasks.Recommendation')
    def test_cleanup_error_handling(self, mock_recommendation):
        """Test error handling in cleanup task"""
        # Mock to raise an exception
        mock_recommendation.objects.filter.side_effect = Exception("Database error")
        
        with self.assertRaises(Exception):
            cleanup_old_recommendations.apply(args=[], kwargs={})

class TestPrecomputeUserRecommendationsTask(TestCeleryTasks):
    """Test precompute recommendations task"""
    
    @patch('recommendations.tasks.recommendation_engine')
    def test_precompute_recommendations_success(self, mock_engine):
        """Test successful precomputation of recommendations"""
        # Create recent interaction to make user "active"
        UserMovieInteraction.objects.create(
            user=self.user,
            movie=self.movie,
            interaction_type='view',
            created_at=timezone.now() - timedelta(days=1)
        )
        
        # Mock recommendation engine
        mock_engine.get_recommendations.return_value = [
            (self.movie, 0.8, 'Precomputed recommendation')
        ]
        
        result = precompute_user_recommendations.apply(args=[], kwargs={})
        
        # Should complete successfully
        self.assertIn('Precomputed recommendations', result.result)
        
        # Verify engine was called for different algorithms
        self.assertEqual(mock_engine.get_recommendations.call_count, 3)  # hybrid, collaborative, content
    
    @patch('recommendations.tasks.recommendation_engine')
    def test_precompute_recommendations_specific_users(self, mock_engine):
        """Test precomputation for specific user IDs"""
        mock_engine.get_recommendations.return_value = []
        
        result = precompute_user_recommendations.apply(
            args=[],
            kwargs={'user_ids': [self.user.id]}
        )
        
        # Should complete successfully
        self.assertIn('Precomputed recommendations', result.result)
        
        # Verify engine was called
        self.assertGreater(mock_engine.get_recommendations.call_count, 0)
    
    def test_precompute_recommendations_no_active_users(self):
        """Test precomputation when no active users exist"""
        result = precompute_user_recommendations.apply(args=[], kwargs={})
        
        # Should complete but with 0 users processed
        self.assertIn('0/0 users', result.result)
    
    @patch('recommendations.tasks.recommendation_engine')
    def test_precompute_recommendations_partial_failure(self, mock_engine):
        """Test precomputation with some user failures"""
        # Create another user
        user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        
        # Mock engine to fail for first user, succeed for second
        def side_effect(*args, **kwargs):
            user = kwargs.get('user') or args[0] if args else None
            if user and user.id == self.user.id:
                raise Exception("Engine error for user 1")
            return [(self.movie, 0.8, 'Success')]
        
        mock_engine.get_recommendations.side_effect = side_effect
        
        result = precompute_user_recommendations.apply(
            args=[],
            kwargs={'user_ids': [self.user.id, user2.id]}
        )
        
        # Should complete with partial success
        self.assertIn('1/2 users', result.result)
    
    @patch('recommendations.tasks.UserMovieInteraction')
    def test_precompute_recommendations_error_handling(self, mock_interaction):
        """Test error handling in precompute task"""
        # Mock to raise an exception
        mock_interaction.objects.filter.side_effect = Exception("Database error")
        
        with self.assertRaises(Exception):
            precompute_user_recommendations.apply(args=[], kwargs={})

class TestTaskRetryMechanism(TestCeleryTasks):
    """Test task retry mechanisms"""
    
    @patch('recommendations.tasks.recommendation_engine')
    def test_retrain_task_retry(self, mock_engine):
        """Test that retrain task retries on failure"""
        # Create sufficient data
        for i in range(15):
            Rating.objects.create(
                user=self.user,
                movie=self.movie,
                rating=4.0,
                created_at=timezone.now() - timedelta(minutes=30)
            )
        
        # Mock engine to raise an exception
        mock_engine._train_all_models.side_effect = Exception("Training failed")
        
        # Task should raise exception (which triggers retry in Celery)
        with self.assertRaises(Exception):
            retrain_ml_models.apply(args=[], kwargs={})
    
    @patch('recommendations.tasks.recommendation_engine')
    def test_generate_recommendations_retry(self, mock_engine):
        """Test that generate recommendations task retries on failure"""
        # Mock engine to raise an exception
        mock_engine.get_recommendations.side_effect = Exception("Engine error")
        
        # Task should raise exception (which triggers retry in Celery)
        with self.assertRaises(Exception):
            generate_recommendations_for_user.apply(
                args=[self.user.id],
                kwargs={}
            )

class TestTaskLogging(TestCeleryTasks):
    """Test task logging functionality"""
    
    @patch('recommendations.tasks.logger')
    @patch('recommendations.tasks.recommendation_engine')
    def test_task_logging(self, mock_engine, mock_logger):
        """Test that tasks log appropriately"""
        # Create sufficient data for retraining
        for i in range(15):
            Rating.objects.create(
                user=self.user,
                movie=self.movie,
                rating=4.0,
                created_at=timezone.now() - timedelta(minutes=30)
            )
        
        retrain_ml_models.apply(args=[], kwargs={})
        
        # Verify logging calls were made
        mock_logger.info.assert_called()
        
        # Check for specific log messages
        log_calls = [call.args[0] for call in mock_logger.info.call_args_list]
        self.assertTrue(
            any('Starting ML model retraining' in msg for msg in log_calls)
        )
        self.assertTrue(
            any('completed successfully' in msg for msg in log_calls)
        )

class TestTaskPerformance(TestCeleryTasks):
    """Test task performance characteristics"""
    
    @patch('recommendations.tasks.recommendation_engine')
    def test_precompute_task_efficiency(self, mock_engine):
        """Test that precompute task handles multiple users efficiently"""
        # Create multiple users with interactions
        users = []
        for i in range(5):
            user = User.objects.create_user(
                username=f'user{i}',
                email=f'user{i}@example.com',
                password='testpass123'
            )
            users.append(user)
            
            UserMovieInteraction.objects.create(
                user=user,
                movie=self.movie,
                interaction_type='view',
                created_at=timezone.now() - timedelta(days=1)
            )
        
        # Mock engine to return quickly
        mock_engine.get_recommendations.return_value = []
        
        result = precompute_user_recommendations.apply(args=[], kwargs={})
        
        # Should complete successfully for all users
        self.assertIn('5/5 users', result.result)
        
        # Should have called engine for each user and algorithm combination
        expected_calls = len(users) * 3  # 3 algorithms per user
        self.assertEqual(mock_engine.get_recommendations.call_count, expected_calls)