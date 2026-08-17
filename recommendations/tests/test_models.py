from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from decimal import Decimal

from recommendations.models import (
    UserPreference, UserMovieInteraction, RecommendationFeedback
)
from movies.models import Movie, Genre

User = get_user_model()

class TestUserPreference(TestCase):
    """Test UserPreference model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.genre1 = Genre.objects.create(name='Action')
        self.genre2 = Genre.objects.create(name='Comedy')
        self.genre3 = Genre.objects.create(name='Drama')
    
    def test_create_user_preference(self):
        """Test creating a user preference"""
        preference = UserPreference.objects.create(
            user=self.user,
            min_rating=7.0,
            max_rating=10.0,
            min_year=2000,
            max_year=2023
        )
        
        self.assertEqual(preference.user, self.user)
        self.assertEqual(preference.min_rating, 7.0)
        self.assertEqual(preference.max_rating, 10.0)
        self.assertEqual(preference.min_year, 2000)
        self.assertEqual(preference.max_year, 2023)
        self.assertIsNotNone(preference.created_at)
        self.assertIsNotNone(preference.updated_at)
    
    def test_user_preference_with_genres(self):
        """Test user preference with preferred genres"""
        preference = UserPreference.objects.create(
            user=self.user,
            min_rating=6.0,
            max_rating=9.0
        )
        
        preference.preferred_genres.add(self.genre1, self.genre2)
        
        self.assertEqual(preference.preferred_genres.count(), 2)
        self.assertIn(self.genre1, preference.preferred_genres.all())
        self.assertIn(self.genre2, preference.preferred_genres.all())
    
    def test_user_preference_unique_constraint(self):
        """Test that each user can have only one preference"""
        UserPreference.objects.create(
            user=self.user,
            min_rating=7.0
        )
        
        # Creating another preference for the same user should raise error
        with self.assertRaises(IntegrityError):
            UserPreference.objects.create(
                user=self.user,
                min_rating=8.0
            )
    
    def test_user_preference_str_method(self):
        """Test string representation of UserPreference"""
        preference = UserPreference.objects.create(
            user=self.user,
            min_rating=7.0
        )
        
        expected_str = f"Preferences for {self.user.username}"
        self.assertEqual(str(preference), expected_str)
    
    def test_user_preference_default_values(self):
        """Test default values for UserPreference fields"""
        preference = UserPreference.objects.create(user=self.user)
        
        self.assertIsNone(preference.min_rating)
        self.assertIsNone(preference.max_rating)
        self.assertIsNone(preference.min_year)
        self.assertIsNone(preference.max_year)
        self.assertEqual(preference.preferred_genres.count(), 0)
    
    def test_user_preference_rating_validation(self):
        """Test rating validation (should be between 0 and 10)"""
        # Valid ratings
        preference = UserPreference.objects.create(
            user=self.user,
            min_rating=0.0,
            max_rating=10.0
        )
        preference.full_clean()  # Should not raise ValidationError
        
        # Test invalid ratings would require custom validation
        # This depends on your model implementation
    
    def test_user_preference_year_validation(self):
        """Test year validation"""
        from datetime import datetime
        current_year = datetime.now().year
        
        # Valid years
        preference = UserPreference.objects.create(
            user=self.user,
            min_year=1900,
            max_year=current_year
        )
        preference.full_clean()  # Should not raise ValidationError

class TestUserMovieInteraction(TestCase):
    """Test UserMovieInteraction model"""
    
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
    
    def test_create_user_movie_interaction(self):
        """Test creating a user movie interaction"""
        interaction = UserMovieInteraction.objects.create(
            user=self.user,
            movie=self.movie,
            interaction_type='rating',
            rating=8.5
        )
        
        self.assertEqual(interaction.user, self.user)
        self.assertEqual(interaction.movie, self.movie)
        self.assertEqual(interaction.interaction_type, 'rating')
        self.assertEqual(interaction.rating, 8.5)
        self.assertIsNotNone(interaction.timestamp)
    
    def test_interaction_types(self):
        """Test different interaction types"""
        interaction_types = ['view', 'rating', 'like', 'dislike', 'watchlist']
        
        for i, interaction_type in enumerate(interaction_types):
            movie = Movie.objects.create(
                title=f'Test Movie {i}',
                overview='Test description',
                release_date='2023-01-01',
                average_rating=8.0,
                vote_count=100,
                popularity=80.0,
                tmdb_id=1001 + i
            )
            
            interaction = UserMovieInteraction.objects.create(
                user=self.user,
                movie=movie,
                interaction_type=interaction_type,
                rating=7.0 if interaction_type == 'rating' else None
            )
            
            self.assertEqual(interaction.interaction_type, interaction_type)
    
    def test_rating_interaction_with_rating(self):
        """Test rating interaction must have rating value"""
        interaction = UserMovieInteraction.objects.create(
            user=self.user,
            movie=self.movie,
            interaction_type='rating',
            rating=9.0
        )
        
        self.assertEqual(interaction.rating, 9.0)
    
    def test_non_rating_interaction_without_rating(self):
        """Test non-rating interactions can have null rating"""
        interaction = UserMovieInteraction.objects.create(
            user=self.user,
            movie=self.movie,
            interaction_type='view'
        )
        
        self.assertIsNone(interaction.rating)
    
    def test_user_movie_interaction_str_method(self):
        """Test string representation of UserMovieInteraction"""
        interaction = UserMovieInteraction.objects.create(
            user=self.user,
            movie=self.movie,
            interaction_type='rating',
            rating=8.5
        )
        
        expected_str = f"{self.user.username} - {self.movie.title} (rating)"
        self.assertEqual(str(interaction), expected_str)
    
    def test_multiple_interactions_same_user_movie(self):
        """Test multiple interactions for same user-movie pair"""
        # User can have multiple interactions with same movie
        interaction1 = UserMovieInteraction.objects.create(
            user=self.user,
            movie=self.movie,
            interaction_type='view'
        )
        
        interaction2 = UserMovieInteraction.objects.create(
            user=self.user,
            movie=self.movie,
            interaction_type='rating',
            rating=8.0
        )
        
        interactions = UserMovieInteraction.objects.filter(
            user=self.user,
            movie=self.movie
        )
        
        self.assertEqual(interactions.count(), 2)
    
    def test_interaction_ordering(self):
        """Test that interactions are ordered by timestamp"""
        import time
        
        interaction1 = UserMovieInteraction.objects.create(
            user=self.user,
            movie=self.movie,
            interaction_type='view'
        )
        
        time.sleep(0.01)  # Small delay to ensure different timestamps
        
        interaction2 = UserMovieInteraction.objects.create(
            user=self.user,
            movie=self.movie,
            interaction_type='rating',
            rating=8.0
        )
        
        interactions = UserMovieInteraction.objects.filter(
            user=self.user,
            movie=self.movie
        ).order_by('-timestamp')
        
        self.assertEqual(interactions.first(), interaction2)
        self.assertEqual(interactions.last(), interaction1)
    
    def test_get_user_ratings(self):
        """Test getting user ratings"""
        # Create some interactions
        UserMovieInteraction.objects.create(
            user=self.user,
            movie=self.movie,
            interaction_type='view'
        )
        
        movie2 = Movie.objects.create(
            title='Test Movie 2',
            overview='Test description',
            release_date='2023-01-01',
            average_rating=7.0,
            vote_count=50,
            popularity=70.0,
            tmdb_id=1002
        )
        
        UserMovieInteraction.objects.create(
            user=self.user,
            movie=movie2,
            interaction_type='rating',
            rating=9.0
        )
        
        # Get only rating interactions
        ratings = UserMovieInteraction.objects.filter(
            user=self.user,
            interaction_type='rating'
        )
        
        self.assertEqual(ratings.count(), 1)
        self.assertEqual(ratings.first().rating, 9.0)

class TestRecommendationFeedback(TestCase):
    """Test RecommendationFeedback model"""
    
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
    
    def test_create_recommendation_feedback(self):
        """Test creating recommendation feedback"""
        feedback = RecommendationFeedback.objects.create(
            user=self.user,
            movie=self.movie,
            feedback_type='helpful',
            rating=4
        )
        
        self.assertEqual(feedback.user, self.user)
        self.assertEqual(feedback.movie, self.movie)
        self.assertEqual(feedback.feedback_type, 'helpful')
        self.assertEqual(feedback.rating, 4)
        self.assertIsNotNone(feedback.timestamp)
    
    def test_feedback_types(self):
        """Test different feedback types"""
        feedback_types = ['helpful', 'not_helpful', 'irrelevant', 'inappropriate']
        
        for i, feedback_type in enumerate(feedback_types):
            movie = Movie.objects.create(
                title=f'Test Movie {i}',
                overview='Test description',
                release_date='2023-01-01',
                average_rating=8.0,
                vote_count=100,
                popularity=80.0,
                tmdb_id=1001 + i
            )
            
            feedback = RecommendationFeedback.objects.create(
                user=self.user,
                movie=movie,
                feedback_type=feedback_type,
                rating=3
            )
            
            self.assertEqual(feedback.feedback_type, feedback_type)
    
    def test_feedback_with_comment(self):
        """Test feedback with optional comment"""
        feedback = RecommendationFeedback.objects.create(
            user=self.user,
            movie=self.movie,
            feedback_type='helpful',
            rating=5,
            comment='Great recommendation! I loved this movie.'
        )
        
        self.assertEqual(
            feedback.comment,
            'Great recommendation! I loved this movie.'
        )
    
    def test_feedback_without_comment(self):
        """Test feedback without comment"""
        feedback = RecommendationFeedback.objects.create(
            user=self.user,
            movie=self.movie,
            feedback_type='not_helpful',
            rating=2
        )
        
        self.assertIsNone(feedback.comment)
    
    def test_recommendation_feedback_str_method(self):
        """Test string representation of RecommendationFeedback"""
        feedback = RecommendationFeedback.objects.create(
            user=self.user,
            movie=self.movie,
            feedback_type='helpful',
            rating=4
        )
        
        expected_str = f"{self.user.username} - {self.movie.title} (helpful)"
        self.assertEqual(str(feedback), expected_str)
    
    def test_feedback_rating_range(self):
        """Test feedback rating validation (1-5 range)"""
        # Valid ratings
        for rating in [1, 2, 3, 4, 5]:
            movie = Movie.objects.create(
                title=f'Test Movie {rating}',
                overview='Test description',
                release_date='2023-01-01',
                average_rating=8.0,
                vote_count=100,
                popularity=80.0,
                tmdb_id=1001 + rating
            )
            
            feedback = RecommendationFeedback.objects.create(
                user=self.user,
                movie=movie,
                feedback_type='helpful',
                rating=rating
            )
            
            self.assertEqual(feedback.rating, rating)
    
    def test_multiple_feedback_same_user_movie(self):
        """Test multiple feedback for same user-movie pair"""
        # User can provide multiple feedback for same movie
        feedback1 = RecommendationFeedback.objects.create(
            user=self.user,
            movie=self.movie,
            feedback_type='helpful',
            rating=4
        )
        
        feedback2 = RecommendationFeedback.objects.create(
            user=self.user,
            movie=self.movie,
            feedback_type='not_helpful',
            rating=2,
            comment='Changed my mind after watching'
        )
        
        feedbacks = RecommendationFeedback.objects.filter(
            user=self.user,
            movie=self.movie
        )
        
        self.assertEqual(feedbacks.count(), 2)
    
    def test_feedback_aggregation(self):
        """Test feedback aggregation for a movie"""
        # Create multiple users and feedback
        user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        
        user3 = User.objects.create_user(
            username='testuser3',
            email='test3@example.com',
            password='testpass123'
        )
        
        # Create feedback from different users
        RecommendationFeedback.objects.create(
            user=self.user,
            movie=self.movie,
            feedback_type='helpful',
            rating=5
        )
        
        RecommendationFeedback.objects.create(
            user=user2,
            movie=self.movie,
            feedback_type='helpful',
            rating=4
        )
        
        RecommendationFeedback.objects.create(
            user=user3,
            movie=self.movie,
            feedback_type='not_helpful',
            rating=2
        )
        
        # Test aggregation
        from django.db.models import Avg, Count
        
        feedback_stats = RecommendationFeedback.objects.filter(
            movie=self.movie
        ).aggregate(
            avg_rating=Avg('rating'),
            total_feedback=Count('id'),
            helpful_count=Count('id', filter=models.Q(feedback_type='helpful'))
        )
        
        self.assertEqual(feedback_stats['total_feedback'], 3)
        self.assertEqual(feedback_stats['helpful_count'], 2)
        self.assertAlmostEqual(feedback_stats['avg_rating'], 3.67, places=1)

class TestModelRelationships(TestCase):
    """Test relationships between models"""
    
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
    
    def test_user_interactions_relationship(self):
        """Test user to interactions relationship"""
        # Create interactions
        interaction1 = UserMovieInteraction.objects.create(
            user=self.user,
            movie=self.movie,
            interaction_type='view'
        )
        
        movie2 = Movie.objects.create(
            title='Test Movie 2',
            overview='Test description',
            release_date='2023-01-01',
            average_rating=7.0,
            vote_count=50,
            popularity=70.0,
            tmdb_id=1002
        )
        
        interaction2 = UserMovieInteraction.objects.create(
            user=self.user,
            movie=movie2,
            interaction_type='rating',
            rating=8.0
        )
        
        # Test reverse relationship
        user_interactions = self.user.usermovieinteraction_set.all()
        self.assertEqual(user_interactions.count(), 2)
        self.assertIn(interaction1, user_interactions)
        self.assertIn(interaction2, user_interactions)
    
    def test_movie_interactions_relationship(self):
        """Test movie to interactions relationship"""
        # Create interactions from different users
        user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        
        interaction1 = UserMovieInteraction.objects.create(
            user=self.user,
            movie=self.movie,
            interaction_type='view'
        )
        
        interaction2 = UserMovieInteraction.objects.create(
            user=user2,
            movie=self.movie,
            interaction_type='rating',
            rating=9.0
        )
        
        # Test reverse relationship
        movie_interactions = self.movie.usermovieinteraction_set.all()
        self.assertEqual(movie_interactions.count(), 2)
        self.assertIn(interaction1, movie_interactions)
        self.assertIn(interaction2, movie_interactions)
    
    def test_user_feedback_relationship(self):
        """Test user to feedback relationship"""
        feedback1 = RecommendationFeedback.objects.create(
            user=self.user,
            movie=self.movie,
            feedback_type='helpful',
            rating=5
        )
        
        movie2 = Movie.objects.create(
            title='Test Movie 2',
            overview='Test description',
            release_date='2023-01-01',
            average_rating=7.0,
            vote_count=50,
            popularity=70.0,
            tmdb_id=1002
        )
        
        feedback2 = RecommendationFeedback.objects.create(
            user=self.user,
            movie=movie2,
            feedback_type='not_helpful',
            rating=2
        )
        
        # Test reverse relationship
        user_feedback = self.user.recommendationfeedback_set.all()
        self.assertEqual(user_feedback.count(), 2)
        self.assertIn(feedback1, user_feedback)
        self.assertIn(feedback2, user_feedback)
    
    def test_cascade_deletion(self):
        """Test cascade deletion behavior"""
        # Create interactions and feedback
        interaction = UserMovieInteraction.objects.create(
            user=self.user,
            movie=self.movie,
            interaction_type='rating',
            rating=8.0
        )
        
        feedback = RecommendationFeedback.objects.create(
            user=self.user,
            movie=self.movie,
            feedback_type='helpful',
            rating=5
        )
        
        # Delete user - should cascade to interactions and feedback
        user_id = self.user.id
        self.user.delete()
        
        # Check that related objects are deleted
        self.assertFalse(
            UserMovieInteraction.objects.filter(user_id=user_id).exists()
        )
        self.assertFalse(
            RecommendationFeedback.objects.filter(user_id=user_id).exists()
        )
        
        # Movie should still exist
        self.assertTrue(Movie.objects.filter(id=self.movie.id).exists())