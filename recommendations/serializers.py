from rest_framework import serializers
from .models import (
    UserPreference, Recommendation, SimilarMovie, UserMovieInteraction,
    RecommendationFeedback, TrendingMovie
)
from movies.serializers import MovieListSerializer
from django.contrib.auth import get_user_model

User = get_user_model()

class UserPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = [
            'id', 'preferred_genres', 'preferred_languages',
            'min_rating', 'max_duration', 'min_year', 'max_year',
            'include_adult', 'recommendation_frequency',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['user']
    
    def validate(self, data):
        if data.get('min_year') and data.get('max_year'):
            if data['min_year'] > data['max_year']:
                raise serializers.ValidationError(
                    "Minimum year cannot be greater than maximum year."
                )
        
        return data

class RecommendationSerializer(serializers.ModelSerializer):
    movie = MovieListSerializer(read_only=True)
    
    class Meta:
        model = Recommendation
        fields = [
            'id', 'movie', 'algorithm_used', 'confidence_score', 'reason',
            'is_viewed', 'is_clicked', 'is_dismissed', 'created_at'
        ]

class SimilarMovieSerializer(serializers.ModelSerializer):
    movie1 = MovieListSerializer(read_only=True)
    movie2 = MovieListSerializer(read_only=True)
    
    class Meta:
        model = SimilarMovie
        fields = ['id', 'movie1', 'movie2', 'similarity_score', 'created_at']

class UserMovieInteractionSerializer(serializers.ModelSerializer):
    movie = MovieListSerializer(read_only=True)
    movie_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = UserMovieInteraction
        fields = [
            'id', 'movie', 'movie_id', 'interaction_type', 'duration',
            'context', 'created_at'
        ]
        read_only_fields = ['user']
    
    def validate_interaction_type(self, value):
        valid_types = ['view', 'like', 'share', 'bookmark', 'search']
        if value not in valid_types:
            raise serializers.ValidationError(
                f"Invalid interaction type. Must be one of: {', '.join(valid_types)}"
            )
        return value

class RecommendationFeedbackSerializer(serializers.ModelSerializer):
    recommendation = RecommendationSerializer(read_only=True)
    recommendation_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = RecommendationFeedback
        fields = [
            'id', 'recommendation', 'recommendation_id', 'feedback_type',
            'comment', 'created_at'
        ]
        read_only_fields = ['user']
    
    def validate_feedback_type(self, value):
        valid_types = ['like', 'dislike', 'not_interested', 'helpful', 'not_helpful']
        if value not in valid_types:
            raise serializers.ValidationError(
                f"Invalid feedback type. Must be one of: {', '.join(valid_types)}"
            )
        return value
    


class TrendingMovieSerializer(serializers.ModelSerializer):
    movie = MovieListSerializer(read_only=True)
    
    class Meta:
        model = TrendingMovie
        fields = [
            'id', 'movie', 'trending_score', 'popularity_rank', 'date', 
            'period_type', 'view_count', 'rating_count', 'watchlist_count', 
            'share_count', 'created_at', 'updated_at'
        ]

class RecommendationRequestSerializer(serializers.Serializer):
    """Serializer for recommendation request parameters"""
    count = serializers.IntegerField(default=10, min_value=1, max_value=50)
    recommendation_type = serializers.ChoiceField(
        choices=['collaborative', 'content_based', 'hybrid', 'trending'],
        default='hybrid'
    )
    include_watched = serializers.BooleanField(default=False)
    min_rating = serializers.FloatField(required=False, min_value=0, max_value=10)
    genres = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
    )
    exclude_genres = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
    )
    release_year_start = serializers.IntegerField(
        required=False,
        min_value=1900,
        max_value=2030
    )
    release_year_end = serializers.IntegerField(
        required=False,
        min_value=1900,
        max_value=2030
    )
    
    def validate(self, data):
        if data.get('release_year_start') and data.get('release_year_end'):
            if data['release_year_start'] > data['release_year_end']:
                raise serializers.ValidationError(
                    "Start year cannot be greater than end year."
                )
        return data

class UserStatsSerializer(serializers.Serializer):
    """Serializer for user statistics"""
    total_movies_watched = serializers.IntegerField()
    total_ratings_given = serializers.IntegerField()
    average_rating_given = serializers.FloatField()
    favorite_genres = serializers.ListField(child=serializers.CharField())
    total_watchlist_items = serializers.IntegerField()
    recommendations_received = serializers.IntegerField()
    recommendations_liked = serializers.IntegerField()
    most_watched_genre = serializers.CharField()
    watching_time_minutes = serializers.IntegerField()