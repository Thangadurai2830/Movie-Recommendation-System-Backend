import requests
import os
from django.conf import settings
from django.core.cache import cache
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class TMDBService:
    """Service for interacting with The Movie Database (TMDB) API"""
    
    BASE_URL = "https://api.themoviedb.org/3"
    IMAGE_BASE_URL = "https://image.tmdb.org/t/p/"
    
    def __init__(self):
        self.api_key = getattr(settings, 'TMDB_API_KEY', None)
        if not self.api_key:
            logger.warning("TMDB API key not found in settings")
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Make a request to TMDB API with error handling"""
        if not self.api_key:
            logger.error("TMDB API key not configured")
            return None
        
        url = f"{self.BASE_URL}{endpoint}"
        default_params = {'api_key': self.api_key}
        
        if params:
            default_params.update(params)
        
        try:
            response = requests.get(url, params=default_params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"TMDB API request failed: {e}")
            return None
    
    def search_movies(self, query: str, page: int = 1) -> Optional[Dict]:
        """Search for movies by title"""
        cache_key = f"tmdb_search_{query}_{page}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result
        
        params = {
            'query': query,
            'page': page,
            'include_adult': False
        }
        
        result = self._make_request('/search/movie', params)
        
        if result:
            cache.set(cache_key, result, 3600)  # Cache for 1 hour
        
        return result
    
    def get_movie_details(self, tmdb_id: int) -> Optional[Dict]:
        """Get detailed information about a specific movie"""
        cache_key = f"tmdb_movie_{tmdb_id}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result
        
        params = {
            'append_to_response': 'credits,videos,images,keywords,reviews'
        }
        
        result = self._make_request(f'/movie/{tmdb_id}', params)
        
        if result:
            cache.set(cache_key, result, 86400)  # Cache for 24 hours
        
        return result
    
    def get_popular_movies(self, page: int = 1) -> Optional[Dict]:
        """Get popular movies"""
        cache_key = f"tmdb_popular_{page}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result
        
        params = {'page': page}
        result = self._make_request('/movie/popular', params)
        
        if result:
            cache.set(cache_key, result, 1800)  # Cache for 30 minutes
        
        return result
    
    def get_trending_movies(self, time_window: str = 'week', page: int = 1) -> Optional[Dict]:
        """Get trending movies (day or week)"""
        cache_key = f"tmdb_trending_{time_window}_{page}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result
        
        params = {'page': page}
        result = self._make_request(f'/trending/movie/{time_window}', params)
        
        if result:
            cache.set(cache_key, result, 1800)  # Cache for 30 minutes
        
        return result
    
    def get_movie_recommendations(self, tmdb_id: int, page: int = 1) -> Optional[Dict]:
        """Get movie recommendations based on a movie"""
        cache_key = f"tmdb_recommendations_{tmdb_id}_{page}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result
        
        params = {'page': page}
        result = self._make_request(f'/movie/{tmdb_id}/recommendations', params)
        
        if result:
            cache.set(cache_key, result, 3600)  # Cache for 1 hour
        
        return result
    
    def get_similar_movies(self, tmdb_id: int, page: int = 1) -> Optional[Dict]:
        """Get similar movies"""
        cache_key = f"tmdb_similar_{tmdb_id}_{page}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result
        
        params = {'page': page}
        result = self._make_request(f'/movie/{tmdb_id}/similar', params)
        
        if result:
            cache.set(cache_key, result, 3600)  # Cache for 1 hour
        
        return result
    
    def get_person_details(self, person_id: int) -> Optional[Dict]:
        """Get person details"""
        cache_key = f"tmdb_person_{person_id}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result
        
        params = {
            'append_to_response': 'movie_credits,tv_credits,images'
        }
        
        result = self._make_request(f'/person/{person_id}', params)
        
        if result:
            cache.set(cache_key, result, 86400)  # Cache for 24 hours
        
        return result
    
    def get_image_url(self, path: str, size: str = 'w500') -> str:
        """Get full image URL from TMDB image path"""
        if not path:
            return ''
        return f"{self.IMAGE_BASE_URL}{size}{path}"
    
    def discover_movies(self, **kwargs) -> Optional[Dict]:
        """Discover movies with various filters"""
        # Build cache key from parameters
        cache_key = f"tmdb_discover_{'_'.join(f'{k}_{v}' for k, v in sorted(kwargs.items()))}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result
        
        result = self._make_request('/discover/movie', kwargs)
        
        if result:
            cache.set(cache_key, result, 1800)  # Cache for 30 minutes
        
        return result


class OMDBService:
    """Service for interacting with Open Movie Database (OMDB) API"""
    
    BASE_URL = "http://www.omdbapi.com/"
    
    def __init__(self):
        self.api_key = getattr(settings, 'OMDB_API_KEY', None)
        if not self.api_key:
            logger.warning("OMDB API key not found in settings")
    
    def _make_request(self, params: Dict) -> Optional[Dict]:
        """Make a request to OMDB API with error handling"""
        if not self.api_key:
            logger.error("OMDB API key not configured")
            return None
        
        default_params = {'apikey': self.api_key}
        default_params.update(params)
        
        try:
            response = requests.get(self.BASE_URL, params=default_params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('Response') == 'False':
                logger.warning(f"OMDB API error: {data.get('Error')}")
                return None
            
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"OMDB API request failed: {e}")
            return None
    
    def get_movie_by_imdb_id(self, imdb_id: str) -> Optional[Dict]:
        """Get movie details by IMDB ID"""
        cache_key = f"omdb_movie_{imdb_id}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result
        
        params = {
            'i': imdb_id,
            'plot': 'full'
        }
        
        result = self._make_request(params)
        
        if result:
            cache.set(cache_key, result, 86400)  # Cache for 24 hours
        
        return result
    
    def search_movies(self, title: str, year: str = None, page: int = 1) -> Optional[Dict]:
        """Search for movies by title"""
        cache_key = f"omdb_search_{title}_{year}_{page}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result
        
        params = {
            's': title,
            'type': 'movie',
            'page': page
        }
        
        if year:
            params['y'] = year
        
        result = self._make_request(params)
        
        if result:
            cache.set(cache_key, result, 3600)  # Cache for 1 hour
        
        return result


# Service instances
tmdb_service = TMDBService()
omdb_service = OMDBService()