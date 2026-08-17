import asyncio
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from django.conf import settings
from django.core.cache import cache
from channels.layers import get_channel_layer
from asgiref.sync import sync_to_async
from .models import Movie, Trailer, Genre, ProductionCompany, Cast, Crew
from .services import TMDBService
import aiohttp

logger = logging.getLogger(__name__)

class RealTimeMovieService:
    """Service for handling real-time movie data updates and streaming"""
    
    def __init__(self):
        self.channel_layer = get_channel_layer()
        self.tmdb_service = TMDBService()
        self.update_interval = 300  # 5 minutes
        self.is_running = False
        
    async def start_streaming(self):
        """Start the real-time movie data streaming service"""
        if self.is_running:
            logger.warning("Real-time movie service is already running")
            return
            
        self.is_running = True
        logger.info("Starting real-time movie streaming service")
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self.stream_popular_movies()),
            asyncio.create_task(self.stream_trending_movies()),
            asyncio.create_task(self.stream_new_trailers()),
            asyncio.create_task(self.stream_movie_updates()),
        ]
        
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Error in real-time streaming service: {str(e)}")
        finally:
            self.is_running = False
    
    async def stop_streaming(self):
        """Stop the real-time movie data streaming service"""
        self.is_running = False
        logger.info("Stopping real-time movie streaming service")
    
    async def stream_popular_movies(self):
        """Stream popular movies updates"""
        while self.is_running:
            try:
                # Fetch popular movies from TMDB
                popular_movies = await self.fetch_tmdb_popular_movies()
                
                if popular_movies:
                    # Update database
                    await self.update_popular_movies_db(popular_movies)
                    
                    # Broadcast to WebSocket clients
                    await self.broadcast_popular_movies(popular_movies)
                
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error streaming popular movies: {str(e)}")
                await asyncio.sleep(60)  # Wait 1 minute before retry
    
    async def stream_trending_movies(self):
        """Stream trending movies updates"""
        while self.is_running:
            try:
                # Fetch trending movies from TMDB
                trending_movies = await self.fetch_tmdb_trending_movies()
                
                if trending_movies:
                    # Update database
                    await self.update_trending_movies_db(trending_movies)
                    
                    # Broadcast to WebSocket clients
                    await self.broadcast_trending_movies(trending_movies)
                
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error streaming trending movies: {str(e)}")
                await asyncio.sleep(60)
    
    async def stream_new_trailers(self):
        """Stream new movie trailers"""
        while self.is_running:
            try:
                # Check for movies that need trailer updates
                movies_needing_trailers = await self.get_movies_needing_trailers()
                
                for movie in movies_needing_trailers:
                    trailers = await self.fetch_movie_trailers(movie['tmdb_id'])
                    if trailers:
                        await self.update_movie_trailers(movie['id'], trailers)
                        await self.broadcast_new_trailers(movie['id'], trailers)
                
                await asyncio.sleep(600)  # Check every 10 minutes
                
            except Exception as e:
                logger.error(f"Error streaming new trailers: {str(e)}")
                await asyncio.sleep(120)
    
    async def stream_movie_updates(self):
        """Stream general movie updates"""
        while self.is_running:
            try:
                # Check for movies that need updates
                movies_to_update = await self.get_movies_for_update()
                
                for movie in movies_to_update:
                    updated_data = await self.fetch_movie_details(movie['tmdb_id'])
                    if updated_data:
                        await self.update_movie_data(movie['id'], updated_data)
                        await self.broadcast_movie_update(movie['id'], updated_data)
                
                await asyncio.sleep(1800)  # Check every 30 minutes
                
            except Exception as e:
                logger.error(f"Error streaming movie updates: {str(e)}")
                await asyncio.sleep(300)
    
    async def fetch_tmdb_popular_movies(self) -> List[Dict]:
        """Fetch popular movies from TMDB API"""
        try:
            if not settings.TMDB_API_KEY:
                logger.warning("TMDB API key not configured")
                return []
            
            url = f"{settings.TMDB_BASE_URL}/movie/popular"
            params = {
                'api_key': settings.TMDB_API_KEY,
                'language': 'en-US',
                'page': 1
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('results', [])
                    else:
                        logger.error(f"TMDB API error: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Error fetching popular movies from TMDB: {str(e)}")
            return []
    
    async def fetch_tmdb_trending_movies(self) -> List[Dict]:
        """Fetch trending movies from TMDB API"""
        try:
            if not settings.TMDB_API_KEY:
                logger.warning("TMDB API key not configured")
                return []
            
            url = f"{settings.TMDB_BASE_URL}/trending/movie/day"
            params = {
                'api_key': settings.TMDB_API_KEY,
                'language': 'en-US'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('results', [])
                    else:
                        logger.error(f"TMDB API error: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Error fetching trending movies from TMDB: {str(e)}")
            return []
    
    async def fetch_movie_trailers(self, tmdb_id: int) -> List[Dict]:
        """Fetch movie trailers from TMDB API"""
        try:
            if not settings.TMDB_API_KEY:
                return []
            
            url = f"{settings.TMDB_BASE_URL}/movie/{tmdb_id}/videos"
            params = {
                'api_key': settings.TMDB_API_KEY,
                'language': 'en-US'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('results', [])
                    else:
                        logger.error(f"TMDB API error for trailers: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Error fetching movie trailers: {str(e)}")
            return []
    
    async def fetch_movie_details(self, tmdb_id: int) -> Optional[Dict]:
        """Fetch detailed movie information from TMDB API"""
        try:
            if not settings.TMDB_API_KEY:
                return None
            
            url = f"{settings.TMDB_BASE_URL}/movie/{tmdb_id}"
            params = {
                'api_key': settings.TMDB_API_KEY,
                'language': 'en-US',
                'append_to_response': 'credits,keywords,release_dates'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"TMDB API error for movie details: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error fetching movie details: {str(e)}")
            return None
    
    @sync_to_async
    def update_popular_movies_db(self, movies_data: List[Dict]):
        """Update popular movies in database"""
        try:
            for movie_data in movies_data:
                movie, created = Movie.objects.update_or_create(
                    tmdb_id=movie_data['id'],
                    defaults={
                        'title': movie_data.get('title', ''),
                        'overview': movie_data.get('overview', ''),
                        'poster_path': movie_data.get('poster_path', ''),
                        'backdrop_path': movie_data.get('backdrop_path', ''),
                        'release_date': movie_data.get('release_date'),
                        'average_rating': movie_data.get('average_rating', movie_data.get('vote_average', 0)),
                        'total_ratings': movie_data.get('vote_count', 0),
                        'popularity': movie_data.get('popularity', 0),
                        'last_updated': datetime.now()
                    }
                )
                
                # Update genres
                if 'genre_ids' in movie_data:
                    self.update_movie_genres(movie, movie_data['genre_ids'])
                    
            logger.info(f"Updated {len(movies_data)} popular movies in database")
            
        except Exception as e:
            logger.error(f"Error updating popular movies in database: {str(e)}")
    
    @sync_to_async
    def update_trending_movies_db(self, movies_data: List[Dict]):
        """Update trending movies in database"""
        try:
            for movie_data in movies_data:
                movie, created = Movie.objects.update_or_create(
                    tmdb_id=movie_data['id'],
                    defaults={
                        'title': movie_data.get('title', ''),
                        'overview': movie_data.get('overview', ''),
                        'poster_path': movie_data.get('poster_path', ''),
                        'backdrop_path': movie_data.get('backdrop_path', ''),
                        'release_date': movie_data.get('release_date'),
                        'average_rating': movie_data.get('average_rating', movie_data.get('vote_average', 0)),
                        'total_ratings': movie_data.get('vote_count', 0),
                        'popularity': movie_data.get('popularity', 0),
                        'is_trending': True,
                        'last_updated': datetime.now()
                    }
                )
                
                # Update genres
                if 'genre_ids' in movie_data:
                    self.update_movie_genres(movie, movie_data['genre_ids'])
                    
            logger.info(f"Updated {len(movies_data)} trending movies in database")
            
        except Exception as e:
            logger.error(f"Error updating trending movies in database: {str(e)}")
    
    @sync_to_async
    def update_movie_trailers(self, movie_id: int, trailers_data: List[Dict]):
        """Update movie trailers in database"""
        try:
            movie = Movie.objects.get(id=movie_id)
            
            for trailer_data in trailers_data:
                if trailer_data.get('site') == 'YouTube' and trailer_data.get('type') in ['Trailer', 'Teaser']:
                    Trailer.objects.update_or_create(
                        movie=movie,
                        key=trailer_data['key'],
                        defaults={
                            'name': trailer_data.get('name', ''),
                            'site': trailer_data.get('site', 'YouTube'),
                            'type': trailer_data.get('type', 'Trailer'),
                            'official': trailer_data.get('official', False),
                            'published_at': trailer_data.get('published_at'),
                        }
                    )
                    
            logger.info(f"Updated trailers for movie {movie_id}")
            
        except Movie.DoesNotExist:
            logger.error(f"Movie {movie_id} not found for trailer update")
        except Exception as e:
            logger.error(f"Error updating movie trailers: {str(e)}")
    
    @sync_to_async
    def update_movie_data(self, movie_id: int, movie_data: Dict):
        """Update detailed movie data in database"""
        try:
            movie = Movie.objects.get(id=movie_id)
            
            # Update basic movie information
            movie.title = movie_data.get('title', movie.title)
            movie.overview = movie_data.get('overview', movie.overview)
            movie.poster_path = movie_data.get('poster_path', movie.poster_path)
            movie.backdrop_path = movie_data.get('backdrop_path', movie.backdrop_path)
            movie.release_date = movie_data.get('release_date', movie.release_date)
            movie.average_rating = movie_data.get('average_rating', movie_data.get('vote_average', movie.average_rating))
            movie.total_ratings = movie_data.get('vote_count', movie.total_ratings)
            movie.popularity = movie_data.get('popularity', movie.popularity)
            movie.runtime = movie_data.get('runtime', movie.runtime)
            movie.budget = movie_data.get('budget', movie.budget)
            movie.revenue = movie_data.get('revenue', movie.revenue)
            movie.last_updated = datetime.now()
            movie.save()
            
            # Update genres
            if 'genres' in movie_data:
                self.update_movie_genres_detailed(movie, movie_data['genres'])
            
            # Update production companies
            if 'production_companies' in movie_data:
                self.update_movie_production_companies(movie, movie_data['production_companies'])
            
            # Update cast and crew
            if 'credits' in movie_data:
                self.update_movie_credits(movie, movie_data['credits'])
                
            logger.info(f"Updated detailed data for movie {movie_id}")
            
        except Movie.DoesNotExist:
            logger.error(f"Movie {movie_id} not found for data update")
        except Exception as e:
            logger.error(f"Error updating movie data: {str(e)}")
    
    def update_movie_genres(self, movie, genre_ids):
        """Update movie genres by IDs"""
        try:
            # TMDB genre mapping
            genre_mapping = {
                28: 'Action', 12: 'Adventure', 16: 'Animation', 35: 'Comedy',
                80: 'Crime', 99: 'Documentary', 18: 'Drama', 10751: 'Family',
                14: 'Fantasy', 36: 'History', 27: 'Horror', 10402: 'Music',
                9648: 'Mystery', 10749: 'Romance', 878: 'Science Fiction',
                10770: 'TV Movie', 53: 'Thriller', 10752: 'War', 37: 'Western'
            }
            
            movie.genres.clear()
            for genre_id in genre_ids:
                if genre_id in genre_mapping:
                    genre, created = Genre.objects.get_or_create(
                        name=genre_mapping[genre_id]
                    )
                    movie.genres.add(genre)
                    
        except Exception as e:
            logger.error(f"Error updating movie genres: {str(e)}")
    
    def update_movie_genres_detailed(self, movie, genres_data):
        """Update movie genres with detailed data"""
        try:
            movie.genres.clear()
            for genre_data in genres_data:
                genre, created = Genre.objects.get_or_create(
                    name=genre_data['name']
                )
                movie.genres.add(genre)
                
        except Exception as e:
            logger.error(f"Error updating movie genres (detailed): {str(e)}")
    
    def update_movie_production_companies(self, movie, companies_data):
        """Update movie production companies"""
        try:
            movie.production_companies.clear()
            for company_data in companies_data:
                company, created = ProductionCompany.objects.get_or_create(
                    name=company_data['name'],
                    defaults={
                        'logo_path': company_data.get('logo_path', ''),
                        'origin_country': company_data.get('origin_country', '')
                    }
                )
                movie.production_companies.add(company)
                
        except Exception as e:
            logger.error(f"Error updating production companies: {str(e)}")
    
    def update_movie_credits(self, movie, credits_data):
        """Update movie cast and crew"""
        try:
            # Update cast
            if 'cast' in credits_data:
                movie.cast.clear()
                for cast_data in credits_data['cast'][:20]:  # Limit to top 20
                    cast_member, created = Cast.objects.get_or_create(
                        name=cast_data['name'],
                        defaults={
                            'character': cast_data.get('character', ''),
                            'profile_path': cast_data.get('profile_path', ''),
                            'order': cast_data.get('order', 0)
                        }
                    )
                    movie.cast.add(cast_member)
            
            # Update crew
            if 'crew' in credits_data:
                movie.crew.clear()
                important_jobs = ['Director', 'Producer', 'Writer', 'Screenplay', 'Story']
                for crew_data in credits_data['crew']:
                    if crew_data.get('job') in important_jobs:
                        crew_member, created = Crew.objects.get_or_create(
                            name=crew_data['name'],
                            job=crew_data['job'],
                            defaults={
                                'department': crew_data.get('department', ''),
                                'profile_path': crew_data.get('profile_path', '')
                            }
                        )
                        movie.crew.add(crew_member)
                        
        except Exception as e:
            logger.error(f"Error updating movie credits: {str(e)}")
    
    @sync_to_async
    def get_movies_needing_trailers(self) -> List[Dict]:
        """Get movies that need trailer updates"""
        try:
            # Get movies without trailers or with old trailer data
            cutoff_date = datetime.now() - timedelta(days=7)
            movies = Movie.objects.filter(
                last_updated__gte=cutoff_date
            ).exclude(
                trailers__isnull=False
            )[:10]  # Limit to 10 movies per batch
            
            return [{
                'id': movie.id,
                'tmdb_id': movie.tmdb_id
            } for movie in movies if movie.tmdb_id]
            
        except Exception as e:
            logger.error(f"Error getting movies needing trailers: {str(e)}")
            return []
    
    @sync_to_async
    def get_movies_for_update(self) -> List[Dict]:
        """Get movies that need general updates"""
        try:
            # Get movies that haven't been updated in the last 24 hours
            cutoff_date = datetime.now() - timedelta(hours=24)
            movies = Movie.objects.filter(
                is_active=True,
                last_updated__lt=cutoff_date
            ).order_by('last_updated')[:5]  # Limit to 5 movies per batch
            
            return [{
                'id': movie.id,
                'tmdb_id': movie.tmdb_id
            } for movie in movies if movie.tmdb_id]
            
        except Exception as e:
            logger.error(f"Error getting movies for update: {str(e)}")
            return []
    
    async def broadcast_popular_movies(self, movies_data: List[Dict]):
        """Broadcast popular movies update to WebSocket clients"""
        try:
            await self.channel_layer.group_send(
                'movies_general',
                {
                    'type': 'movie_update',
                    'data': {
                        'type': 'popular_movies_update',
                        'movies': movies_data[:10],  # Send top 10
                        'timestamp': datetime.now().isoformat()
                    }
                }
            )
            logger.info("Broadcasted popular movies update")
            
        except Exception as e:
            logger.error(f"Error broadcasting popular movies: {str(e)}")
    
    async def broadcast_trending_movies(self, movies_data: List[Dict]):
        """Broadcast trending movies update to WebSocket clients"""
        try:
            await self.channel_layer.group_send(
                'trending_movies',
                {
                    'type': 'trending_update',
                    'data': {
                        'type': 'trending_movies_update',
                        'movies': movies_data[:15],  # Send top 15
                        'timestamp': datetime.now().isoformat()
                    }
                }
            )
            logger.info("Broadcasted trending movies update")
            
        except Exception as e:
            logger.error(f"Error broadcasting trending movies: {str(e)}")
    
    async def broadcast_new_trailers(self, movie_id: int, trailers_data: List[Dict]):
        """Broadcast new trailers to WebSocket clients"""
        try:
            # Broadcast to general trailers room
            await self.channel_layer.group_send(
                'trailers',
                {
                    'type': 'new_trailer',
                    'data': {
                        'movie_id': movie_id,
                        'trailers': trailers_data,
                        'timestamp': datetime.now().isoformat()
                    }
                }
            )
            
            # Broadcast to specific movie room
            await self.channel_layer.group_send(
                f'movie_{movie_id}',
                {
                    'type': 'trailer_update',
                    'data': {
                        'movie_id': movie_id,
                        'trailers': trailers_data,
                        'timestamp': datetime.now().isoformat()
                    }
                }
            )
            
            logger.info(f"Broadcasted new trailers for movie {movie_id}")
            
        except Exception as e:
            logger.error(f"Error broadcasting new trailers: {str(e)}")
    
    async def broadcast_movie_update(self, movie_id: int, movie_data: Dict):
        """Broadcast movie data update to WebSocket clients"""
        try:
            # Broadcast to general movies room
            await self.channel_layer.group_send(
                'movies_general',
                {
                    'type': 'movie_update',
                    'data': {
                        'type': 'movie_data_update',
                        'movie_id': movie_id,
                        'movie_data': {
                            'id': movie_id,
                            'title': movie_data.get('title'),
                            'average_rating': movie_data.get('average_rating', movie_data.get('vote_average', 0)),
                            'popularity': movie_data.get('popularity'),
                            'vote_count': movie_data.get('vote_count')
                        },
                        'timestamp': datetime.now().isoformat()
                    }
                }
            )
            
            # Broadcast to specific movie room
            await self.channel_layer.group_send(
                f'movie_{movie_id}',
                {
                    'type': 'movie_update',
                    'data': {
                        'type': 'movie_data_update',
                        'movie_data': movie_data,
                        'timestamp': datetime.now().isoformat()
                    }
                }
            )
            
            logger.info(f"Broadcasted movie update for movie {movie_id}")
            
        except Exception as e:
            logger.error(f"Error broadcasting movie update: {str(e)}")

# Global instance
realtime_service = RealTimeMovieService()