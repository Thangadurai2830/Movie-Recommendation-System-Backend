from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/movies/$', consumers.MovieConsumer.as_asgi()),
    re_path(r'ws/movies/(?P<movie_id>\w+)/$', consumers.MovieDetailConsumer.as_asgi()),
    re_path(r'ws/trending/$', consumers.TrendingConsumer.as_asgi()),
    re_path(r'ws/recommendations/(?P<user_id>\w+)/$', consumers.RecommendationConsumer.as_asgi()),
    re_path(r'ws/trailers/$', consumers.TrailerConsumer.as_asgi()),
    re_path(r'ws/ratings/(?P<movie_id>\w+)/$', consumers.RatingConsumer.as_asgi()),
]