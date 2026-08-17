from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from movies.models import Movie

User = get_user_model()


class UserPreference(models.Model):
    """User preferences for recommendation algorithm"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferences')
    
    # Genre preferences (weights)
    preferred_genres = models.JSONField(default=dict, blank=True)
    
    # Language preferences
    preferred_languages = models.JSONField(default=list, blank=True)
    
    # Content preferences
    min_rating = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(10.0)]
    )
    max_duration = models.PositiveIntegerField(null=True, blank=True)
    min_year = models.PositiveIntegerField(null=True, blank=True)
    max_year = models.PositiveIntegerField(null=True, blank=True)
    
    # Content filtering
    include_adult = models.BooleanField(default=False)
    
    # Recommendation settings
    recommendation_frequency = models.CharField(
        max_length=20,
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
        ],
        default='weekly'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_preferences'
        verbose_name = 'User Preference'
        verbose_name_plural = 'User Preferences'
        indexes = [
            models.Index(fields=['user']),  # For user preference lookups
            models.Index(fields=['recommendation_frequency']),  # For batch processing
            models.Index(fields=['updated_at']),  # For recent preference changes
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()}'s Preferences"


class Recommendation(models.Model):
    """Generated movie recommendations for users"""
    
    ALGORITHM_CHOICES = [
        ('collaborative', 'Collaborative Filtering'),
        ('content_based', 'Content-Based Filtering'),
        ('hybrid', 'Hybrid Approach'),
        ('popularity', 'Popularity-Based'),
        ('trending', 'Trending Movies'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recommendations')
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='recommended_to')
    
    # Recommendation metadata
    algorithm_used = models.CharField(max_length=20, choices=ALGORITHM_CHOICES)
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence score of the recommendation (0-1)"
    )
    reason = models.TextField(blank=True, help_text="Explanation for the recommendation")
    
    # User interaction
    is_viewed = models.BooleanField(default=False)
    is_clicked = models.BooleanField(default=False)
    is_dismissed = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    viewed_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'recommendations'
        verbose_name = 'Recommendation'
        verbose_name_plural = 'Recommendations'
        unique_together = ['user', 'movie']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['algorithm_used']),
            models.Index(fields=['confidence_score']),
            models.Index(fields=['is_viewed']),
        ]
    
    def __str__(self):
        return f"Recommend '{self.movie.title}' to {self.user.get_full_name()}"


class SimilarMovie(models.Model):
    """Pre-computed movie similarities for content-based recommendations"""
    
    movie1 = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='similar_to')
    movie2 = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='similar_from')
    
    similarity_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    
    # Similarity factors
    genre_similarity = models.FloatField(default=0.0)
    cast_similarity = models.FloatField(default=0.0)
    director_similarity = models.FloatField(default=0.0)
    year_similarity = models.FloatField(default=0.0)
    rating_similarity = models.FloatField(default=0.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'similar_movies'
        verbose_name = 'Similar Movie'
        verbose_name_plural = 'Similar Movies'
        unique_together = ['movie1', 'movie2']
        ordering = ['-similarity_score']
        indexes = [
            models.Index(fields=['movie1', 'similarity_score']),
            models.Index(fields=['similarity_score']),
        ]
    
    def __str__(self):
        return f"{self.movie1.title} similar to {self.movie2.title} ({self.similarity_score:.2f})"


class UserMovieInteraction(models.Model):
    """Track user interactions with movies for recommendation learning"""
    
    INTERACTION_CHOICES = [
        ('view', 'Viewed'),
        ('like', 'Liked'),
        ('dislike', 'Disliked'),
        ('watchlist_add', 'Added to Watchlist'),
        ('watchlist_remove', 'Removed from Watchlist'),
        ('rate', 'Rated'),
        ('share', 'Shared'),
        ('search', 'Searched'),
        ('click', 'Clicked'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='movie_interactions')
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='user_interactions')
    interaction_type = models.CharField(max_length=20, choices=INTERACTION_CHOICES)
    
    # Additional context
    duration = models.PositiveIntegerField(null=True, blank=True, help_text="Duration in seconds")
    context = models.JSONField(default=dict, blank=True)  # Additional context data
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'user_movie_interactions'
        verbose_name = 'User Movie Interaction'
        verbose_name_plural = 'User Movie Interactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'interaction_type']),
            models.Index(fields=['movie', 'interaction_type']),
            models.Index(fields=['created_at']),
            models.Index(fields=['user', 'created_at']),  # For user activity timeline
            models.Index(fields=['movie', 'created_at']),  # For movie interaction timeline
            models.Index(fields=['interaction_type', 'created_at']),  # For interaction analysis
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} {self.interaction_type} {self.movie.title}"


class RecommendationFeedback(models.Model):
    """User feedback on recommendations for algorithm improvement"""
    
    FEEDBACK_CHOICES = [
        ('helpful', 'Helpful'),
        ('not_helpful', 'Not Helpful'),
        ('irrelevant', 'Irrelevant'),
        ('already_seen', 'Already Seen'),
        ('not_interested', 'Not Interested'),
    ]
    
    recommendation = models.OneToOneField(
        Recommendation, 
        on_delete=models.CASCADE, 
        related_name='feedback'
    )
    feedback_type = models.CharField(max_length=20, choices=FEEDBACK_CHOICES)
    comment = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'recommendation_feedback'
        verbose_name = 'Recommendation Feedback'
        verbose_name_plural = 'Recommendation Feedback'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recommendation']),  # For feedback lookups
            models.Index(fields=['feedback_type']),  # For feedback analysis
            models.Index(fields=['created_at']),  # For chronological queries
            models.Index(fields=['feedback_type', 'created_at']),  # For feedback trends
        ]
    
    def __str__(self):
        return f"Feedback: {self.feedback_type} for {self.recommendation}"


class TrendingMovie(models.Model):
    """Track trending movies for popularity-based recommendations"""
    
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='trending_data')
    
    # Trending metrics
    view_count = models.PositiveIntegerField(default=0)
    rating_count = models.PositiveIntegerField(default=0)
    watchlist_count = models.PositiveIntegerField(default=0)
    share_count = models.PositiveIntegerField(default=0)
    
    # Calculated scores
    trending_score = models.FloatField(default=0.0)
    popularity_rank = models.PositiveIntegerField(null=True, blank=True)
    
    # Time period
    date = models.DateField()
    period_type = models.CharField(
        max_length=10,
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
        ],
        default='daily'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'trending_movies'
        verbose_name = 'Trending Movie'
        verbose_name_plural = 'Trending Movies'
        unique_together = ['movie', 'date', 'period_type']
        ordering = ['-trending_score', '-date']
        indexes = [
            models.Index(fields=['date', 'period_type']),
            models.Index(fields=['trending_score']),
            models.Index(fields=['popularity_rank']),
        ]
    
    def __str__(self):
        return f"{self.movie.title} trending on {self.date} ({self.period_type})"
