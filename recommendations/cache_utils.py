import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from django.core.cache import caches
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from functools import wraps

logger = logging.getLogger(__name__)

class CacheManager:
    """
    Centralized cache management for the recommendation system
    """
    
    def __init__(self):
        self.default_cache = caches['default']
        self.recommendations_cache = caches['recommendations']
        self.user_profiles_cache = caches['user_profiles']
        self.ml_models_cache = caches['ml_models']
    
    def _generate_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """
        Generate a consistent cache key from arguments
        """
        key_data = {
            'args': args,
            'kwargs': sorted(kwargs.items()) if kwargs else None
        }
        key_string = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()[:16]
        return f"{prefix}:{key_hash}"
    
    def get_user_recommendations(self, user_id: int, algorithm: str = 'hybrid', 
                               count: int = 10, **kwargs) -> Optional[List[Dict]]:
        """
        Get cached user recommendations
        """
        try:
            cache_key = self._generate_cache_key(
                f"user_recs_{user_id}", algorithm, count, **kwargs
            )
            return self.recommendations_cache.get(cache_key)
        except Exception as e:
            logger.warning(f"Error getting cached recommendations: {str(e)}")
            return None
    
    def set_user_recommendations(self, user_id: int, recommendations: List[Dict], 
                               algorithm: str = 'hybrid', count: int = 10, 
                               timeout: Optional[int] = None, **kwargs) -> bool:
        """
        Cache user recommendations
        """
        try:
            cache_key = self._generate_cache_key(
                f"user_recs_{user_id}", algorithm, count, **kwargs
            )
            timeout = timeout or 1800  # 30 minutes default
            
            # Add metadata
            cache_data = {
                'recommendations': recommendations,
                'algorithm': algorithm,
                'count': count,
                'cached_at': timezone.now().isoformat(),
                'user_id': user_id
            }
            
            self.recommendations_cache.set(cache_key, cache_data, timeout)
            logger.info(f"Cached recommendations for user {user_id} with key {cache_key}")
            return True
        except Exception as e:
            logger.error(f"Error caching recommendations: {str(e)}")
            return False
    
    def get_user_profile(self, user_id: int) -> Optional[Dict]:
        """
        Get cached user profile data
        """
        try:
            cache_key = f"profile_{user_id}"
            return self.user_profiles_cache.get(cache_key)
        except Exception as e:
            logger.warning(f"Error getting cached user profile: {str(e)}")
            return None
    
    def set_user_profile(self, user_id: int, profile_data: Dict, 
                        timeout: Optional[int] = None) -> bool:
        """
        Cache user profile data
        """
        try:
            cache_key = f"profile_{user_id}"
            timeout = timeout or 900  # 15 minutes default
            
            # Add metadata
            cache_data = {
                'profile': profile_data,
                'cached_at': timezone.now().isoformat(),
                'user_id': user_id
            }
            
            self.user_profiles_cache.set(cache_key, cache_data, timeout)
            return True
        except Exception as e:
            logger.error(f"Error caching user profile: {str(e)}")
            return False
    
    def get_movie_data(self, movie_id: int) -> Optional[Dict]:
        """
        Get cached movie data
        """
        try:
            cache_key = f"movie_{movie_id}"
            return self.default_cache.get(cache_key)
        except Exception as e:
            logger.warning(f"Error getting cached movie data: {str(e)}")
            return None
    
    def set_movie_data(self, movie_id: int, movie_data: Dict, 
                      timeout: Optional[int] = None) -> bool:
        """
        Cache movie data
        """
        try:
            cache_key = f"movie_{movie_id}"
            timeout = timeout or 3600  # 1 hour default
            
            cache_data = {
                'movie': movie_data,
                'cached_at': timezone.now().isoformat(),
                'movie_id': movie_id
            }
            
            self.default_cache.set(cache_key, cache_data, timeout)
            return True
        except Exception as e:
            logger.error(f"Error caching movie data: {str(e)}")
            return False
    
    def get_ml_model(self, model_name: str) -> Optional[Any]:
        """
        Get cached ML model
        """
        try:
            cache_key = f"model_{model_name}"
            return self.ml_models_cache.get(cache_key)
        except Exception as e:
            logger.warning(f"Error getting cached ML model: {str(e)}")
            return None
    
    def set_ml_model(self, model_name: str, model_data: Any, 
                    timeout: Optional[int] = None) -> bool:
        """
        Cache ML model
        """
        try:
            cache_key = f"model_{model_name}"
            timeout = timeout or 3600  # 1 hour default
            
            self.ml_models_cache.set(cache_key, model_data, timeout)
            logger.info(f"Cached ML model {model_name}")
            return True
        except Exception as e:
            logger.error(f"Error caching ML model: {str(e)}")
            return False
    
    def invalidate_user_cache(self, user_id: int) -> bool:
        """
        Invalidate all cache entries for a specific user
        """
        try:
            # Clear user recommendations
            pattern = f"*user_recs_{user_id}*"
            self._clear_cache_pattern(self.recommendations_cache, pattern)
            
            # Clear user profile
            profile_key = f"profile_{user_id}"
            self.user_profiles_cache.delete(profile_key)
            
            logger.info(f"Invalidated cache for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error invalidating user cache: {str(e)}")
            return False
    
    def invalidate_movie_cache(self, movie_id: int) -> bool:
        """
        Invalidate cache entries for a specific movie
        """
        try:
            cache_key = f"movie_{movie_id}"
            self.default_cache.delete(cache_key)
            
            # Also clear related recommendation caches
            # This is a simplified approach - in production, you might want more granular control
            self.recommendations_cache.clear()
            
            logger.info(f"Invalidated cache for movie {movie_id}")
            return True
        except Exception as e:
            logger.error(f"Error invalidating movie cache: {str(e)}")
            return False
    
    def _clear_cache_pattern(self, cache, pattern: str) -> None:
        """
        Clear cache entries matching a pattern (Redis-specific)
        """
        try:
            if hasattr(cache, '_cache') and hasattr(cache._cache, 'delete_pattern'):
                cache._cache.delete_pattern(pattern)
            else:
                # Fallback for non-Redis caches
                logger.warning("Pattern deletion not supported for this cache backend")
        except Exception as e:
            logger.warning(f"Error clearing cache pattern {pattern}: {str(e)}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics
        """
        stats = {
            'default_cache': self._get_cache_info(self.default_cache),
            'recommendations_cache': self._get_cache_info(self.recommendations_cache),
            'user_profiles_cache': self._get_cache_info(self.user_profiles_cache),
            'ml_models_cache': self._get_cache_info(self.ml_models_cache),
        }
        return stats
    
    def _get_cache_info(self, cache) -> Dict[str, Any]:
        """
        Get information about a specific cache
        """
        try:
            if hasattr(cache, '_cache') and hasattr(cache._cache, 'get_stats'):
                return cache._cache.get_stats()
            else:
                return {'status': 'available', 'backend': str(type(cache))}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}


def cache_recommendations(timeout: int = 1800, cache_key_prefix: str = "rec"):
    """
    Decorator to cache recommendation function results
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_manager = CacheManager()
            
            # Generate cache key
            cache_key = cache_manager._generate_cache_key(
                cache_key_prefix, func.__name__, *args, **kwargs
            )
            
            # Try to get from cache
            cached_result = cache_manager.recommendations_cache.get(cache_key)
            if cached_result is not None:
                logger.info(f"Cache hit for {func.__name__} with key {cache_key}")
                return cached_result
            
            # Execute function and cache result
            try:
                result = func(*args, **kwargs)
                cache_manager.recommendations_cache.set(cache_key, result, timeout)
                logger.info(f"Cached result for {func.__name__} with key {cache_key}")
                return result
            except Exception as e:
                logger.error(f"Error in cached function {func.__name__}: {str(e)}")
                raise
        
        return wrapper
    return decorator


def cache_user_profile(timeout: int = 900):
    """
    Decorator to cache user profile function results
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_manager = CacheManager()
            
            # Generate cache key
            cache_key = cache_manager._generate_cache_key(
                "profile", func.__name__, *args, **kwargs
            )
            
            # Try to get from cache
            cached_result = cache_manager.user_profiles_cache.get(cache_key)
            if cached_result is not None:
                logger.info(f"Cache hit for {func.__name__} with key {cache_key}")
                return cached_result
            
            # Execute function and cache result
            try:
                result = func(*args, **kwargs)
                cache_manager.user_profiles_cache.set(cache_key, result, timeout)
                logger.info(f"Cached result for {func.__name__} with key {cache_key}")
                return result
            except Exception as e:
                logger.error(f"Error in cached function {func.__name__}: {str(e)}")
                raise
        
        return wrapper
    return decorator


# Global cache manager instance
cache_manager = CacheManager()