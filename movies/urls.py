from django.urls import path
from . import views
from . import search_views

app_name = 'movies'

urlpatterns = [
    # Movie endpoints
    path('', views.MovieListCreateView.as_view(), name='movie_list_create'),
    path('<int:pk>/', views.MovieDetailView.as_view(), name='movie_detail'),
    path('search/', views.movie_search, name='movie_search'),
    
    # Enhanced search endpoints
    path('search/enhanced/', search_views.enhanced_movie_search, name='enhanced_search'),
    path('search/autocomplete/', search_views.search_autocomplete, name='search_autocomplete'),
    path('search/filters/', search_views.search_filters, name='search_filters'),
    path('search/personalized/', search_views.personalized_search, name='personalized_search'),
    path('search/save/', search_views.save_search_query, name='save_search'),
    path('search/recent/', search_views.recent_searches, name='recent_searches'),
    path('popular/', views.popular_movies, name='popular_movies'),
    path('trending/', views.tmdb_trending_movies, name='trending_movies'),
    path('recent/', views.recent_movies, name='recent_movies'),
    path('<int:movie_id>/stats/', views.movie_stats, name='movie_stats'),
    
    # Genre endpoints
    path('genres/', views.GenreListCreateView.as_view(), name='genre_list_create'),
    
    # Language endpoints
    path('languages/', views.LanguageListCreateView.as_view(), name='language_list_create'),
    
    # Country endpoints
    path('countries/', views.CountryListCreateView.as_view(), name='country_list_create'),
    
    # Person endpoints
    path('persons/', views.PersonListCreateView.as_view(), name='person_list_create'),
    path('persons/<int:pk>/', views.PersonDetailView.as_view(), name='person_detail'),
    
    # Rating endpoints
    path('ratings/', views.RatingListCreateView.as_view(), name='rating_list_create'),
    path('ratings/<int:pk>/', views.RatingDetailView.as_view(), name='rating_detail'),
    path('ratings/movie/<int:movie_id>/', views.movie_ratings, name='movie_ratings'),
    
    # Watchlist endpoints
    path('watchlist/', views.WatchlistListCreateView.as_view(), name='watchlist_list_create'),
    path('watchlist/<int:pk>/', views.WatchlistDetailView.as_view(), name='watchlist_detail'),
    path('<int:movie_id>/toggle-watchlist/', views.toggle_watchlist, name='toggle_watchlist'),
    
    # External API endpoints
    path('tmdb/search/', views.tmdb_search, name='tmdb-search'),
    path('tmdb/popular/', views.tmdb_popular, name='tmdb-popular'),
    path('tmdb/trending/', views.tmdb_trending, name='tmdb-trending'),
    path('tmdb/movie/<int:tmdb_id>/', views.tmdb_movie_details, name='tmdb-movie-details'),
    path('tmdb/movie/<int:tmdb_id>/recommendations/', views.tmdb_movie_recommendations, name='tmdb-movie-recommendations'),
    path('tmdb/movie/<int:tmdb_id>/similar/', views.tmdb_similar_movies, name='tmdb-similar-movies'),
    path('omdb/movie/<str:imdb_id>/', views.omdb_movie_details, name='omdb-movie-details'),
    path('import/tmdb/', views.import_movie_from_tmdb, name='import-movie-from-tmdb'),
    
    # New TMDB real-time endpoints
    path('api/tmdb/trending/', views.tmdb_trending_movies, name='api-tmdb-trending'),
    path('api/tmdb/popular/', views.tmdb_popular_movies, name='api-tmdb-popular'),
    path('api/tmdb/upcoming/', views.tmdb_upcoming_movies, name='api-tmdb-upcoming'),
    path('api/tmdb/search/', views.tmdb_search_movies, name='api-tmdb-search'),
    path('api/tmdb/sync/', views.sync_tmdb_movie, name='api-tmdb-sync'),
    path('api/tmdb/bulk-sync/', views.bulk_sync_tmdb_movies, name='api-tmdb-bulk-sync'),
]