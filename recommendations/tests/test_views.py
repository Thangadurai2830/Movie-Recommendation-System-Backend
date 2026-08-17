from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch, Mock
import json

from movies.models import Movie, Genre, Rating
from recommendations.models import (
    UserPreference, UserMovieInteraction, 
    RecommendationFeedback, TrendingMovie
)

User = get_user_model()

class RecommendationAPITestCase(APITestCase):
    """Base test case for recommendation API tests"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create JWT token for authentication
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)
        
        # Set up API client with authentication
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
        
        # Create test genres
        self.action_genre = Genre.objects.create(name='Action')
        self.comedy_genre = Genre.objects.create(name='Comedy')
        
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
        
        # Create user preferences
        self.user_preference = UserPreference.objects.create(
            user=self.user,
            preferred_genres='Action,Comedy',
            min_rating=7.0,
            max_rating=10.0,
            preferred_decade='2020s'
        )

class TestUserPreferenceView(RecommendationAPITestCase):
    """Test user preference API endpoints"""
    
    def test_get_user_preferences(self):
        """Test retrieving user preferences"""
        url = reverse('user-preferences')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['preferred_genres'], 'Action,Comedy')
        self.assertEqual(float(data['min_rating']), 7.0)
    
    def test_update_user_preferences(self):
        """Test updating user preferences"""
        url = reverse('user-preferences')
        data = {
            'preferred_genres': 'Drama,Thriller',
            'min_rating': 8.0,
            'max_rating': 10.0,
            'preferred_decade': '2010s'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify preferences were updated
        self.user_preference.refresh_from_db()
        self.assertEqual(self.user_preference.preferred_genres, 'Drama,Thriller')
        self.assertEqual(float(self.user_preference.min_rating), 8.0)
    
    def test_create_user_preferences_if_not_exist(self):
        """Test creating preferences for user without existing preferences"""
        # Delete existing preferences
        self.user_preference.delete()
        
        url = reverse('user-preferences')
        data = {
            'preferred_genres': 'Sci-Fi,Fantasy',
            'min_rating': 6.0,
            'max_rating': 9.0,
            'preferred_decade': '1990s'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify new preferences were created
        new_preference = UserPreference.objects.get(user=self.user)
        self.assertEqual(new_preference.preferred_genres, 'Sci-Fi,Fantasy')
    
    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access preferences"""
        self.client.credentials()  # Remove authentication
        url = reverse('user-preferences')
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

class TestRecommendationListView(RecommendationAPITestCase):
    """Test recommendation list API endpoint"""
    
    @patch('recommendations.views.recommendation_engine')
    def test_get_recommendations(self, mock_engine):
        """Test getting recommendations"""
        # Mock recommendation engine response
        mock_engine.get_recommendations.return_value = [
            (self.movie1, 0.9, 'Based on your preferences'),
            (self.movie2, 0.8, 'Similar to movies you liked')
        ]
        
        url = reverse('recommendations')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertIn('results', data)
        self.assertEqual(len(data['results']), 2)
        
        # Check first recommendation
        first_rec = data['results'][0]
        self.assertEqual(first_rec['movie']['id'], self.movie1.id)
        self.assertEqual(first_rec['confidence_score'], 0.9)
        self.assertEqual(first_rec['reason'], 'Based on your preferences')
    
    @patch('recommendations.views.recommendation_engine')
    def test_get_recommendations_with_algorithm_parameter(self, mock_engine):
        """Test getting recommendations with specific algorithm"""
        mock_engine.get_recommendations.return_value = [
            (self.movie1, 0.85, 'Collaborative filtering')
        ]
        
        url = reverse('recommendations')
        response = self.client.get(url, {'algorithm': 'collaborative'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify the engine was called with correct algorithm
        mock_engine.get_recommendations.assert_called_once()
        call_args = mock_engine.get_recommendations.call_args
        self.assertEqual(call_args[1]['algorithm'], 'collaborative')
    
    @patch('recommendations.views.recommendation_engine')
    def test_get_recommendations_with_count_parameter(self, mock_engine):
        """Test getting recommendations with specific count"""
        mock_engine.get_recommendations.return_value = []
        
        url = reverse('recommendations')
        response = self.client.get(url, {'count': 15})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify the engine was called with correct count
        call_args = mock_engine.get_recommendations.call_args
        self.assertEqual(call_args[1]['count'], 15)
    
    def test_invalid_algorithm_parameter(self):
        """Test handling of invalid algorithm parameter"""
        url = reverse('recommendations')
        response = self.client.get(url, {'algorithm': 'invalid_algo'})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn('error', data)
    
    def test_invalid_count_parameter(self):
        """Test handling of invalid count parameter"""
        url = reverse('recommendations')
        response = self.client.get(url, {'count': 'invalid'})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class TestUserMovieInteractionView(RecommendationAPITestCase):
    """Test user movie interaction API endpoints"""
    
    def test_create_interaction(self):
        """Test creating a new user movie interaction"""
        url = reverse('user-interactions')
        data = {
            'movie': self.movie1.id,
            'interaction_type': 'view'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify interaction was created
        interaction = UserMovieInteraction.objects.get(
            user=self.user,
            movie=self.movie1
        )
        self.assertEqual(interaction.interaction_type, 'view')
    
    def test_list_user_interactions(self):
        """Test listing user interactions"""
        # Create test interactions
        UserMovieInteraction.objects.create(
            user=self.user,
            movie=self.movie1,
            interaction_type='view'
        )
        UserMovieInteraction.objects.create(
            user=self.user,
            movie=self.movie2,
            interaction_type='like'
        )
        
        url = reverse('user-interactions')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertEqual(len(data['results']), 2)
    
    def test_invalid_interaction_type(self):
        """Test creating interaction with invalid type"""
        url = reverse('user-interactions')
        data = {
            'movie': self.movie1.id,
            'interaction_type': 'invalid_type'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_nonexistent_movie_interaction(self):
        """Test creating interaction with nonexistent movie"""
        url = reverse('user-interactions')
        data = {
            'movie': 99999,  # Nonexistent movie ID
            'interaction_type': 'view'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class TestRecommendationFeedbackView(RecommendationAPITestCase):
    """Test recommendation feedback API endpoints"""
    
    def test_create_feedback(self):
        """Test creating recommendation feedback"""
        url = reverse('recommendation-feedback')
        data = {
            'movie': self.movie1.id,
            'feedback_type': 'like',
            'rating': 5
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify feedback was created
        feedback = RecommendationFeedback.objects.get(
            user=self.user,
            movie=self.movie1
        )
        self.assertEqual(feedback.feedback_type, 'like')
        self.assertEqual(feedback.rating, 5)
    
    def test_list_user_feedback(self):
        """Test listing user feedback"""
        # Create test feedback
        RecommendationFeedback.objects.create(
            user=self.user,
            movie=self.movie1,
            feedback_type='like',
            rating=5
        )
        
        url = reverse('recommendation-feedback')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['feedback_type'], 'like')
    
    def test_invalid_feedback_type(self):
        """Test creating feedback with invalid type"""
        url = reverse('recommendation-feedback')
        data = {
            'movie': self.movie1.id,
            'feedback_type': 'invalid_feedback',
            'rating': 3
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_invalid_rating_range(self):
        """Test creating feedback with invalid rating"""
        url = reverse('recommendation-feedback')
        data = {
            'movie': self.movie1.id,
            'feedback_type': 'like',
            'rating': 11  # Invalid rating (should be 1-10)
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class TestTrendingMoviesView(RecommendationAPITestCase):
    """Test trending movies API endpoint"""
    
    def test_get_trending_movies(self):
        """Test getting trending movies"""
        # Create trending movies
        TrendingMovie.objects.create(
            movie=self.movie1,
            trending_score=95.0,
            rank=1
        )
        TrendingMovie.objects.create(
            movie=self.movie2,
            trending_score=85.0,
            rank=2
        )
        
        url = reverse('trending-movies')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertEqual(len(data['results']), 2)
        
        # Check ordering (should be by rank)
        self.assertEqual(data['results'][0]['movie']['id'], self.movie1.id)
        self.assertEqual(data['results'][1]['movie']['id'], self.movie2.id)
    
    def test_trending_movies_pagination(self):
        """Test trending movies pagination"""
        # Create multiple trending movies
        for i in range(25):
            movie = Movie.objects.create(
                title=f'Trending Movie {i}',
                overview=f'Description {i}',
                release_date='2023-01-01',
                average_rating=7.0,
                vote_count=100,
                popularity=50.0,
                tmdb_id=3000 + i
            )
            TrendingMovie.objects.create(
                movie=movie,
                trending_score=90.0 - i,
                rank=i + 1
            )
        
        url = reverse('trending-movies')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Should have pagination
        self.assertIn('next', data)
        self.assertIn('previous', data)
        self.assertIn('count', data)
        self.assertLessEqual(len(data['results']), 20)  # Default page size

class TestRecommendationStatsView(RecommendationAPITestCase):
    """Test recommendation statistics API endpoint"""
    
    def test_get_user_stats(self):
        """Test getting user recommendation statistics"""
        # Create test data
        Rating.objects.create(user=self.user, movie=self.movie1, rating=5.0)
        UserMovieInteraction.objects.create(
            user=self.user,
            movie=self.movie1,
            interaction_type='view'
        )
        RecommendationFeedback.objects.create(
            user=self.user,
            movie=self.movie1,
            feedback_type='like',
            rating=5
        )
        
        url = reverse('user-recommendation-stats')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertIn('total_ratings', data)
        self.assertIn('total_interactions', data)
        self.assertIn('total_feedback', data)
        self.assertIn('average_rating', data)
        
        self.assertEqual(data['total_ratings'], 1)
        self.assertEqual(data['total_interactions'], 1)
        self.assertEqual(data['total_feedback'], 1)

class TestSimilarMoviesView(RecommendationAPITestCase):
    """Test similar movies API endpoint"""
    
    @patch('recommendations.views.recommendation_engine')
    def test_get_similar_movies(self, mock_engine):
        """Test getting similar movies"""
        # Mock similar movies response
        mock_engine.get_similar_movies.return_value = [
            (self.movie2, 0.85, 'Similar genre and rating')
        ]
        
        url = reverse('similar-movies', kwargs={'movie_id': self.movie1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['movie']['id'], self.movie2.id)
        self.assertEqual(data[0]['similarity_score'], 0.85)
    
    def test_similar_movies_nonexistent_movie(self):
        """Test getting similar movies for nonexistent movie"""
        url = reverse('similar-movies', kwargs={'movie_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

class TestRecordInteractionView(RecommendationAPITestCase):
    """Test record interaction API endpoint"""
    
    def test_record_interaction(self):
        """Test recording a user interaction"""
        url = reverse('record-interaction')
        data = {
            'movie_id': self.movie1.id,
            'interaction_type': 'view'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify interaction was recorded
        interaction = UserMovieInteraction.objects.get(
            user=self.user,
            movie=self.movie1
        )
        self.assertEqual(interaction.interaction_type, 'view')
    
    def test_record_interaction_invalid_movie(self):
        """Test recording interaction for invalid movie"""
        url = reverse('record-interaction')
        data = {
            'movie_id': 99999,
            'interaction_type': 'view'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class TestAPIThrottling(RecommendationAPITestCase):
    """Test API rate limiting and throttling"""
    
    @patch('recommendations.views.recommendation_engine')
    def test_recommendation_throttling(self, mock_engine):
        """Test that recommendation endpoint has rate limiting"""
        mock_engine.get_recommendations.return_value = []
        
        url = reverse('recommendations')
        
        # Make multiple requests rapidly
        responses = []
        for i in range(10):
            response = self.client.get(url)
            responses.append(response.status_code)
        
        # At least some requests should succeed
        success_count = sum(1 for status_code in responses if status_code == 200)
        self.assertGreater(success_count, 0)

class TestAPIErrorHandling(RecommendationAPITestCase):
    """Test API error handling"""
    
    @patch('recommendations.views.recommendation_engine')
    def test_recommendation_engine_error_handling(self, mock_engine):
        """Test handling of recommendation engine errors"""
        # Mock engine to raise an exception
        mock_engine.get_recommendations.side_effect = Exception("Engine error")
        
        url = reverse('recommendations')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        data = response.json()
        self.assertIn('error', data)
    
    def test_malformed_request_handling(self):
        """Test handling of malformed requests"""
        url = reverse('user-interactions')
        
        # Send malformed JSON
        response = self.client.post(
            url,
            'invalid json',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)