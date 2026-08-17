from django.urls import path
from . import views

app_name = 'recommendations'

urlpatterns = [
    # User preferences
    path('preferences/', views.UserPreferenceView.as_view(), name='user-preferences'),
    
    # Recommendations
    path('', views.RecommendationListView.as_view(), name='recommendation-list'),
    path('generate/', views.generate_recommendations, name='generate-recommendations'),
    path('stats/', views.user_recommendation_stats, name='user-recommendation-stats'),
    
    # User interactions
    path('interactions/', views.UserMovieInteractionListCreateView.as_view(), name='user-interactions'),
    path('interactions/<int:movie_id>/', views.record_interaction, name='record-interaction'),
    
    # Recommendation feedback
    path('feedback/', views.RecommendationFeedbackListCreateView.as_view(), name='recommendation-feedback'),
    path('feedback/analytics/', views.FeedbackAnalyticsView.as_view(), name='feedback-analytics'),
    
    # Trending movies
    path('trending/', views.TrendingMoviesView.as_view(), name='trending-movies'),
    
    # Similar movies
    path('similar/<int:movie_id>/', views.similar_movies, name='similar-movies'),
]