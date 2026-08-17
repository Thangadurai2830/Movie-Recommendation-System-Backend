from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Avg
from .models import (
    UserPreference, Recommendation, SimilarMovie, UserMovieInteraction,
    RecommendationFeedback, TrendingMovie
)

@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'min_rating', 'max_duration', 'recommendation_frequency', 
        'get_preferred_genres_count', 'include_adult', 'created_at'
    ]
    search_fields = ['user__username']
    list_filter = ['min_rating', 'recommendation_frequency', 'include_adult', 'created_at']
    autocomplete_fields = ['user']
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 25
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Content Preferences', {
            'fields': ('min_rating', 'max_duration', 'min_year', 'max_year', 'include_adult')
        }),
        ('Genre & Language Preferences', {
            'fields': ('preferred_genres', 'preferred_languages')
        }),
        ('Recommendation Settings', {
            'fields': ('recommendation_frequency',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_preferred_genres_count(self, obj):
        if obj.preferred_genres:
            return f"{len(obj.preferred_genres)} genres"
        return "No preferences"
    get_preferred_genres_count.short_description = "Genre Preferences"

@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'get_movie_title', 'algorithm_used', 'get_confidence_display', 
        'is_viewed', 'get_feedback_status', 'created_at'
    ]
    search_fields = ['user__username', 'movie__title']
    list_filter = ['algorithm_used', 'confidence_score', 'is_viewed', 'created_at']
    autocomplete_fields = ['user', 'movie']
    readonly_fields = ['created_at']
    list_per_page = 25
    ordering = ['-created_at']
    
    def get_movie_title(self, obj):
        return obj.movie.title
    get_movie_title.short_description = "Movie"
    get_movie_title.admin_order_field = 'movie__title'
    
    def get_confidence_display(self, obj):
        confidence = obj.confidence_score
        if confidence >= 0.8:
            color = "green"
            icon = "🟢"
        elif confidence >= 0.6:
            color = "orange"
            icon = "🟡"
        else:
            color = "red"
            icon = "🔴"
        return format_html(
            '<span style="color: {}">{} {:.2f}</span>',
            color, icon, confidence
        )
    get_confidence_display.short_description = "Confidence"
    get_confidence_display.admin_order_field = 'confidence_score'
    
    def get_feedback_status(self, obj):
        try:
            feedback = obj.feedback
            if feedback.feedback_type == 'like':
                return "👍 Liked"
            elif feedback.feedback_type == 'dislike':
                return "👎 Disliked"
            else:
                return "ℹ️ Neutral"
        except:
            return "No feedback"
    get_feedback_status.short_description = "Feedback"

@admin.register(SimilarMovie)
class SimilarMovieAdmin(admin.ModelAdmin):
    list_display = ['get_movie1_title', 'get_movie2_title', 'get_similarity_display', 'created_at']
    search_fields = ['movie1__title', 'movie2__title']
    list_filter = ['similarity_score', 'created_at']
    autocomplete_fields = ['movie1', 'movie2']
    ordering = ['-similarity_score']
    list_per_page = 25
    
    def get_movie1_title(self, obj):
        return obj.movie1.title
    get_movie1_title.short_description = "Movie 1"
    get_movie1_title.admin_order_field = 'movie1__title'
    
    def get_movie2_title(self, obj):
        return obj.movie2.title
    get_movie2_title.short_description = "Movie 2"
    get_movie2_title.admin_order_field = 'movie2__title'
    
    def get_similarity_display(self, obj):
        score = obj.similarity_score
        if score >= 0.8:
            return format_html('<span style="color: green">🟢 {:.3f}</span>', score)
        elif score >= 0.6:
            return format_html('<span style="color: orange">🟡 {:.3f}</span>', score)
        else:
            return format_html('<span style="color: red">🔴 {:.3f}</span>', score)
    get_similarity_display.short_description = "Similarity"
    get_similarity_display.admin_order_field = 'similarity_score'

@admin.register(UserMovieInteraction)
class UserMovieInteractionAdmin(admin.ModelAdmin):
    list_display = ['user', 'get_movie_title', 'get_interaction_display', 'duration', 'created_at']
    search_fields = ['user__username', 'movie__title']
    list_filter = ['interaction_type', 'created_at']
    autocomplete_fields = ['user', 'movie']
    ordering = ['-created_at']
    list_per_page = 25
    
    def get_movie_title(self, obj):
        return obj.movie.title
    get_movie_title.short_description = "Movie"
    get_movie_title.admin_order_field = 'movie__title'
    
    def get_interaction_display(self, obj):
        interaction_icons = {
            'view': '👁️ View',
            'like': '👍 Like',
            'dislike': '👎 Dislike',
            'share': '📤 Share',
            'bookmark': '🔖 Bookmark',
            'click': '🖱️ Click'
        }
        return interaction_icons.get(obj.interaction_type, obj.interaction_type)
    get_interaction_display.short_description = "Interaction"
    get_interaction_display.admin_order_field = 'interaction_type'

@admin.register(RecommendationFeedback)
class RecommendationFeedbackAdmin(admin.ModelAdmin):
    list_display = [
        'get_user', 'get_movie', 'get_feedback_display', 
        'get_algorithm', 'created_at'
    ]
    search_fields = ['recommendation__user__username', 'recommendation__movie__title']
    list_filter = ['feedback_type', 'created_at']
    autocomplete_fields = ['recommendation']
    list_per_page = 25
    ordering = ['-created_at']
    
    def get_user(self, obj):
        return obj.recommendation.user.username
    get_user.short_description = "User"
    get_user.admin_order_field = 'recommendation__user__username'
    
    def get_movie(self, obj):
        return obj.recommendation.movie.title
    get_movie.short_description = "Movie"
    get_movie.admin_order_field = 'recommendation__movie__title'
    
    def get_feedback_display(self, obj):
        feedback_icons = {
            'like': '👍 Liked',
            'dislike': '👎 Disliked',
            'neutral': 'ℹ️ Neutral'
        }
        return feedback_icons.get(obj.feedback_type, obj.feedback_type)
    get_feedback_display.short_description = "Feedback"
    get_feedback_display.admin_order_field = 'feedback_type'
    
    def get_algorithm(self, obj):
        return obj.recommendation.algorithm_used
    get_algorithm.short_description = "Algorithm"
    get_algorithm.admin_order_field = 'recommendation__algorithm_used'

@admin.register(TrendingMovie)
class TrendingMovieAdmin(admin.ModelAdmin):
    list_display = [
        'get_movie_title', 'date', 'get_trending_score_display', 
        'popularity_rank', 'period_type'
    ]
    search_fields = ['movie__title']
    list_filter = ['period_type', 'date']
    autocomplete_fields = ['movie']
    list_per_page = 25
    ordering = ['-trending_score']
    
    def get_movie_title(self, obj):
        return obj.movie.title
    get_movie_title.short_description = "Movie"
    get_movie_title.admin_order_field = 'movie__title'
    
    def get_trending_score_display(self, obj):
        score = obj.trending_score
        if score >= 80:
            return format_html('<span style="color: red">🔥 {}</span>', score)
        elif score >= 60:
            return format_html('<span style="color: orange">📈 {}</span>', score)
        else:
            return format_html('<span style="color: blue">📊 {}</span>', score)
    get_trending_score_display.short_description = "Trending Score"
    get_trending_score_display.admin_order_field = 'trending_score'
    autocomplete_fields = ['movie']
    ordering = ['-trending_score', '-date']
