import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from .models import Movie, Rating
from .services import TMDBService
from recommendations.models import Recommendation
import logging

logger = logging.getLogger(__name__)

class MovieConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for general movie updates"""
    
    async def connect(self):
        self.room_group_name = 'movies_general'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"WebSocket connected: {self.channel_name}")
        
        # Send initial data
        await self.send_popular_movies()
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        logger.info(f"WebSocket disconnected: {self.channel_name}")
    
    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'authenticate':
                token = text_data_json.get('token')
                await self.authenticate_user(token)
            elif message_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
            elif message_type == 'get_popular_movies':
                await self.send_popular_movies()
            elif message_type == 'get_trending_movies':
                await self.send_trending_movies()
            elif message_type == 'search_movies':
                query = text_data_json.get('query', '')
                await self.search_movies(query)
            elif message_type == 'get_movie_details':
                movie_id = text_data_json.get('movie_id')
                await self.send_movie_details(movie_id)
            elif message_type == 'subscribe_movie':
                movie_id = text_data_json.get('movie_id')
                await self.subscribe_to_movie(movie_id)
            elif message_type == 'unsubscribe_movie':
                movie_id = text_data_json.get('movie_id')
                await self.unsubscribe_from_movie(movie_id)
            elif message_type == 'rate_movie':
                movie_id = text_data_json.get('movie_id')
                rating = text_data_json.get('rating')
                await self.handle_movie_rating(movie_id, rating)
            elif message_type == 'toggle_watchlist':
                movie_id = text_data_json.get('movie_id')
                await self.handle_watchlist_toggle(movie_id)
            elif message_type == 'get_recommendations':
                user_id = text_data_json.get('user_id')
                await self.send_recommendations(user_id)
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error in MovieConsumer.receive: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Internal server error'
            }))
    
    async def authenticate_user(self, token):
        """Authenticate user with JWT token"""
        try:
            from django.contrib.auth.models import AnonymousUser
            from rest_framework_simplejwt.tokens import UntypedToken
            from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
            from django.contrib.auth import get_user_model
            import jwt
            from django.conf import settings
            
            if not token:
                self.user = AnonymousUser()
                return
                
            try:
                # Validate token
                UntypedToken(token)
                # Decode token to get user info
                decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
                user_id = decoded_token.get('user_id')
                
                User = get_user_model()
                self.user = await database_sync_to_async(User.objects.get)(id=user_id)
                
                await self.send(text_data=json.dumps({
                    'type': 'authentication_success',
                    'user': {
                        'id': self.user.id,
                        'username': self.user.username,
                        'email': self.user.email
                    }
                }))
            except (InvalidToken, TokenError, User.DoesNotExist):
                self.user = AnonymousUser()
                await self.send(text_data=json.dumps({
                    'type': 'authentication_failed',
                    'message': 'Invalid token'
                }))
        except Exception as e:
            logger.error(f"Error authenticating user: {str(e)}")
            self.user = AnonymousUser()
    
    async def send_popular_movies(self):
        """Send popular movies data"""
        try:
            movies = await self.get_popular_movies()
            await self.send(text_data=json.dumps({
                'type': 'popular_movies',
                'movies': movies
            }))
        except Exception as e:
            logger.error(f"Error sending popular movies: {str(e)}")
    
    async def send_trending_movies(self):
        """Send trending movies data"""
        try:
            movies = await self.get_trending_movies()
            await self.send(text_data=json.dumps({
                'type': 'trending_movies',
                'movies': movies
            }))
        except Exception as e:
            logger.error(f"Error sending trending movies: {str(e)}")
    
    async def search_movies(self, query):
        """Search movies and send results"""
        try:
            movies = await self.search_movies_db(query)
            await self.send(text_data=json.dumps({
                'type': 'search_results',
                'data': movies,
                'query': query
            }))
        except Exception as e:
            logger.error(f"Error searching movies: {str(e)}")
    
    async def send_movie_details(self, movie_id):
        """Send detailed movie information"""
        try:
            movie_details = await self.get_movie_details(movie_id)
            await self.send(text_data=json.dumps({
                'type': 'movie_details',
                'data': movie_details
            }))
        except Exception as e:
            logger.error(f"Error sending movie details: {str(e)}")
    
    async def subscribe_to_movie(self, movie_id):
        """Subscribe to real-time updates for a specific movie"""
        try:
            if not hasattr(self, 'subscribed_movies'):
                self.subscribed_movies = set()
            
            self.subscribed_movies.add(movie_id)
            room_group_name = f'movie_{movie_id}'
            
            await self.channel_layer.group_add(
                room_group_name,
                self.channel_name
            )
            
            await self.send(text_data=json.dumps({
                'type': 'subscription_success',
                'movie_id': movie_id
            }))
        except Exception as e:
            logger.error(f"Error subscribing to movie {movie_id}: {str(e)}")
    
    async def unsubscribe_from_movie(self, movie_id):
        """Unsubscribe from real-time updates for a specific movie"""
        try:
            if hasattr(self, 'subscribed_movies'):
                self.subscribed_movies.discard(movie_id)
            
            room_group_name = f'movie_{movie_id}'
            
            await self.channel_layer.group_discard(
                room_group_name,
                self.channel_name
            )
            
            await self.send(text_data=json.dumps({
                'type': 'unsubscription_success',
                'movie_id': movie_id
            }))
        except Exception as e:
            logger.error(f"Error unsubscribing from movie {movie_id}: {str(e)}")
    
    async def handle_movie_rating(self, movie_id, rating):
        """Handle movie rating submission"""
        try:
            if not hasattr(self, 'user') or self.user.is_anonymous:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Authentication required for rating'
                }))
                return
            
            result = await self.rate_movie_db(movie_id, rating, self.user.id)
            
            if result['success']:
                # Broadcast rating update to all subscribers
                room_group_name = f'movie_{movie_id}'
                await self.channel_layer.group_send(
                    room_group_name,
                    {
                        'type': 'rating_update',
                        'movie_id': movie_id,
                        'rating': rating,
                        'user_id': self.user.id,
                        'average_rating': result['average_rating'],
                        'vote_count': result['vote_count']
                    }
                )
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': result['error']
                }))
        except Exception as e:
            logger.error(f"Error handling movie rating: {str(e)}")
    
    async def handle_watchlist_toggle(self, movie_id):
        """Handle watchlist toggle"""
        try:
            if not hasattr(self, 'user') or self.user.is_anonymous:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Authentication required for watchlist'
                }))
                return
            
            result = await self.toggle_watchlist_db(movie_id, self.user.id)
            
            await self.send(text_data=json.dumps({
                'type': 'watchlist_update',
                'movie_id': movie_id,
                'in_watchlist': result['in_watchlist']
            }))
        except Exception as e:
            logger.error(f"Error handling watchlist toggle: {str(e)}")
    
    async def send_recommendations(self, user_id=None):
        """Send personalized recommendations"""
        try:
            if not user_id and hasattr(self, 'user') and not self.user.is_anonymous:
                user_id = self.user.id
            
            recommendations = await self.get_recommendations_db(user_id)
            
            await self.send(text_data=json.dumps({
                'type': 'recommendation_update',
                'recommendations': recommendations
            }))
        except Exception as e:
            logger.error(f"Error sending recommendations: {str(e)}")
    
    @database_sync_to_async
    def get_popular_movies(self):
        """Get popular movies from database"""
        movies = Movie.objects.all().order_by('-popularity')[:20]
        return [{
            'id': movie.id,
            'title': movie.title,
            'poster_path': movie.poster_path,
            'backdrop_path': movie.backdrop_path,
            'overview': movie.overview,
            'release_date': movie.release_date.isoformat() if movie.release_date else None,
            'average_rating': float(movie.average_rating),
            'vote_count': movie.total_ratings,
            'popularity': float(movie.popularity),
            'genres': [genre.name for genre in movie.genres.all()]
        } for movie in movies]
    
    @database_sync_to_async
    def get_trending_movies(self):
        """Get trending movies from database"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Get movies with recent activity (ratings, views)
        recent_date = timezone.now() - timedelta(days=7)
        movies = Movie.objects.filter(
            ratings__created_at__gte=recent_date
        ).annotate(
            recent_ratings=models.Count('ratings', filter=models.Q(ratings__created_at__gte=recent_date))
        ).order_by('-recent_ratings', '-average_rating')[:20]
        
        return [{
            'id': movie.id,
            'title': movie.title,
            'poster_path': movie.poster_path,
            'backdrop_path': movie.backdrop_path,
            'overview': movie.overview,
            'release_date': movie.release_date.isoformat() if movie.release_date else None,
            'average_rating': float(movie.average_rating),
            'vote_count': movie.total_ratings,
            'popularity': float(movie.popularity),
            'genres': [genre.name for genre in movie.genres.all()]
        } for movie in movies]
    
    @database_sync_to_async
    def search_movies_db(self, query):
        """Search movies in database"""
        movies = Movie.objects.filter(
            title__icontains=query
        )[:10]
        return [{
            'id': movie.id,
            'title': movie.title,
            'poster_path': movie.poster_path,
            'backdrop_path': movie.backdrop_path,
            'overview': movie.overview,
            'release_date': movie.release_date.isoformat() if movie.release_date else None,
            'average_rating': float(movie.average_rating),
            'vote_count': movie.total_ratings,
            'genres': [genre.name for genre in movie.genres.all()]
        } for movie in movies]
    
    @database_sync_to_async
    def rate_movie_db(self, movie_id, rating, user_id):
        """Rate a movie in the database"""
        try:
            from .models import Rating
            from django.contrib.auth import get_user_model
            from django.db import transaction
            
            User = get_user_model()
            user = User.objects.get(id=user_id)
            movie = Movie.objects.get(id=movie_id)
            
            # Validate rating
            if not (1 <= rating <= 10):
                return {'success': False, 'error': 'Rating must be between 1 and 10'}
            
            with transaction.atomic():
                # Update or create rating
                rating_obj, created = Rating.objects.update_or_create(
                    user=user,
                    movie=movie,
                    defaults={'rating': rating}
                )
                
                # Recalculate movie average rating
                ratings = Rating.objects.filter(movie=movie)
                avg_rating = sum(r.rating for r in ratings) / len(ratings)
                movie.average_rating = avg_rating
                movie.total_ratings = len(ratings)
                movie.save()
                
                return {
                    'success': True,
                    'average_rating': float(avg_rating),
                    'vote_count': len(ratings)
                }
        except (Movie.DoesNotExist, User.DoesNotExist):
            return {'success': False, 'error': 'Movie or user not found'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @database_sync_to_async
    def toggle_watchlist_db(self, movie_id, user_id):
        """Toggle movie in user's watchlist"""
        try:
            from .models import Watchlist
            from django.contrib.auth import get_user_model
            
            User = get_user_model()
            user = User.objects.get(id=user_id)
            movie = Movie.objects.get(id=movie_id)
            
            watchlist_item, created = Watchlist.objects.get_or_create(
                user=user,
                movie=movie
            )
            
            if not created:
                # Remove from watchlist
                watchlist_item.delete()
                return {'in_watchlist': False}
            else:
                # Added to watchlist
                return {'in_watchlist': True}
                
        except (Movie.DoesNotExist, User.DoesNotExist):
            return {'in_watchlist': False}
        except Exception as e:
            logger.error(f"Error toggling watchlist: {str(e)}")
            return {'in_watchlist': False}
    
    @database_sync_to_async
    def get_recommendations_db(self, user_id=None):
        """Get personalized movie recommendations"""
        try:
            if user_id:
                from django.contrib.auth import get_user_model
                from .models import Rating
                
                User = get_user_model()
                user = User.objects.get(id=user_id)
                
                # Get user's rated movies
                user_ratings = Rating.objects.filter(user=user)
                rated_movie_ids = [r.movie.id for r in user_ratings]
                
                # Get genres from highly rated movies (rating >= 7)
                preferred_genres = set()
                for rating in user_ratings.filter(rating__gte=7):
                    for genre in rating.movie.genres.all():
                        preferred_genres.add(genre.id)
                
                # Recommend movies from preferred genres that user hasn't rated
                if preferred_genres:
                    recommendations = Movie.objects.filter(
                        genres__id__in=preferred_genres,
                        average_rating__gte=6.0
                    ).exclude(
                        id__in=rated_movie_ids
                    ).distinct().order_by('-average_rating', '-popularity')[:10]
                else:
                    # Fallback to popular movies
                    recommendations = Movie.objects.exclude(
                        id__in=rated_movie_ids
                    ).order_by('-popularity', '-average_rating')[:10]
            else:
                # General recommendations for non-authenticated users
                recommendations = Movie.objects.filter(
                    average_rating__gte=7.0
                ).order_by('-popularity', '-average_rating')[:10]
            
            return [{
                'id': movie.id,
                'title': movie.title,
                'poster_path': movie.poster_path,
                'backdrop_path': movie.backdrop_path,
                'overview': movie.overview,
                'release_date': movie.release_date.isoformat() if movie.release_date else None,
                'average_rating': float(movie.average_rating),
                'vote_count': movie.total_ratings,
                'popularity': float(movie.popularity),
                'genres': [genre.name for genre in movie.genres.all()]
            } for movie in recommendations]
            
        except Exception as e:
            logger.error(f"Error getting recommendations: {str(e)}")
            return []
    
    @database_sync_to_async
    def get_movie_details(self, movie_id):
        """Get detailed movie information"""
        try:
            movie = Movie.objects.get(id=movie_id)
            return {
                'id': movie.id,
                'title': movie.title,
                'overview': movie.overview,
                'poster_path': movie.poster_path,
                'backdrop_path': movie.backdrop_path,
                'release_date': movie.release_date.isoformat() if movie.release_date else None,
                'average_rating': float(movie.average_rating),
                'vote_count': movie.total_ratings,
                'popularity': float(movie.popularity),
                'runtime': movie.runtime,
                'budget': movie.budget,
                'revenue': movie.revenue,
                'genres': [genre.name for genre in movie.genres.all()],
                'production_companies': [company.name for company in movie.production_companies.all()],
                'cast': [{
                    'name': cast.name,
                    'character': cast.character,
                    'profile_path': cast.profile_path
                } for cast in movie.cast.all()[:10]],
                'crew': [{
                    'name': crew.name,
                    'job': crew.job,
                    'department': crew.department
                } for crew in movie.crew.filter(job__in=['Director', 'Producer', 'Writer'])]
            }
        except Movie.DoesNotExist:
            return None
    
    # Handlers for group messages
    async def movie_update(self, event):
        """Handle movie update events"""
        await self.send(text_data=json.dumps({
            'type': 'movie_update',
            'data': event['data']
        }))
    
    async def new_movie(self, event):
        """Handle new movie events"""
        await self.send(text_data=json.dumps({
            'type': 'new_movie',
            'data': event['data']
        }))

class MovieDetailConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for specific movie details and real-time updates"""
    
    async def connect(self):
        self.movie_id = self.scope['url_route']['kwargs']['movie_id']
        self.room_group_name = f'movie_{self.movie_id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"WebSocket connected to movie {self.movie_id}: {self.channel_name}")
        
        # Send initial movie data
        await self.send_movie_data()
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        logger.info(f"WebSocket disconnected from movie {self.movie_id}: {self.channel_name}")
    
    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'get_movie_data':
                await self.send_movie_data()
            elif message_type == 'get_trailers':
                await self.send_trailers()
            elif message_type == 'rate_movie':
                rating = text_data_json.get('rating')
                await self.handle_rating(rating)
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error in MovieDetailConsumer.receive: {str(e)}")
    
    async def send_movie_data(self):
        """Send complete movie data including trailers"""
        try:
            movie_data = await self.get_movie_with_trailers()
            if movie_data:
                await self.send(text_data=json.dumps({
                    'type': 'movie_data',
                    'data': movie_data
                }))
        except Exception as e:
            logger.error(f"Error sending movie data: {str(e)}")
    
    async def send_trailers(self):
        """Send movie trailers"""
        try:
            trailers = await self.get_movie_trailers()
            await self.send(text_data=json.dumps({
                'type': 'trailers',
                'data': trailers
            }))
        except Exception as e:
            logger.error(f"Error sending trailers: {str(e)}")
    
    async def handle_rating(self, rating):
        """Handle movie rating submission"""
        try:
            if self.scope['user'] and not isinstance(self.scope['user'], AnonymousUser):
                await self.save_rating(rating)
                # Broadcast rating update to all connected clients
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'rating_update',
                        'data': {
                            'movie_id': self.movie_id,
                            'new_rating': rating,
                            'user_id': self.scope['user'].id
                        }
                    }
                )
        except Exception as e:
            logger.error(f"Error handling rating: {str(e)}")
    
    @database_sync_to_async
    def get_movie_with_trailers(self):
        """Get movie data with trailers"""
        try:
            movie = Movie.objects.get(id=self.movie_id)
            return {
                'id': movie.id,
                'title': movie.title,
                'overview': movie.overview,
                'poster_path': movie.poster_path,
                'backdrop_path': movie.backdrop_path,
                'release_date': movie.release_date.isoformat() if movie.release_date else None,
                'average_rating': float(movie.average_rating),
                'vote_count': movie.vote_count,
                'popularity': float(movie.popularity),
                'runtime': movie.runtime,
                'trailers': [{
                    'id': trailer.id,
                    'name': trailer.name,
                    'key': trailer.key,
                    'site': trailer.site,
                    'type': trailer.type,
                    'official': trailer.official
                } for trailer in movie.trailers.all()]
            }
        except Movie.DoesNotExist:
            return None
    
    @database_sync_to_async
    def get_movie_trailers(self):
        """Get movie trailers"""
        try:
            movie = Movie.objects.get(id=self.movie_id)
            return [{
                'id': trailer.id,
                'name': trailer.name,
                'key': trailer.key,
                'site': trailer.site,
                'type': trailer.type,
                'official': trailer.official
            } for trailer in movie.trailers.all()]
        except Movie.DoesNotExist:
            return []
    
    @database_sync_to_async
    def save_rating(self, rating_value):
        """Save user rating for movie"""
        try:
            movie = Movie.objects.get(id=self.movie_id)
            rating, created = Rating.objects.update_or_create(
                user=self.scope['user'],
                movie=movie,
                defaults={'rating': rating_value}
            )
            return rating
        except Movie.DoesNotExist:
            return None
    
    # Handlers for group messages
    async def rating_update(self, event):
        """Handle rating update events"""
        await self.send(text_data=json.dumps({
            'type': 'rating_update',
            'data': event['data']
        }))
    
    async def trailer_update(self, event):
        """Handle trailer update events"""
        await self.send(text_data=json.dumps({
            'type': 'trailer_update',
            'data': event['data']
        }))

class TrendingConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for trending movies and real-time updates"""
    
    async def connect(self):
        self.room_group_name = 'trending_movies'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"WebSocket connected to trending: {self.channel_name}")
        
        # Send initial trending data
        await self.send_trending_movies()
        
        # Start periodic updates
        asyncio.create_task(self.periodic_trending_updates())
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        logger.info(f"WebSocket disconnected from trending: {self.channel_name}")
    
    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'get_trending':
                await self.send_trending_movies()
            elif message_type == 'get_trending_by_genre':
                genre = text_data_json.get('genre')
                await self.send_trending_by_genre(genre)
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error in TrendingConsumer.receive: {str(e)}")
    
    async def send_trending_movies(self):
        """Send trending movies data"""
        try:
            trending_movies = await self.get_trending_movies()
            await self.send(text_data=json.dumps({
                'type': 'trending_movies',
                'data': trending_movies,
                'timestamp': asyncio.get_event_loop().time()
            }))
        except Exception as e:
            logger.error(f"Error sending trending movies: {str(e)}")
    
    async def send_trending_by_genre(self, genre):
        """Send trending movies by genre"""
        try:
            trending_movies = await self.get_trending_by_genre(genre)
            await self.send(text_data=json.dumps({
                'type': 'trending_by_genre',
                'data': trending_movies,
                'genre': genre
            }))
        except Exception as e:
            logger.error(f"Error sending trending by genre: {str(e)}")
    
    async def periodic_trending_updates(self):
        """Send periodic trending updates every 5 minutes"""
        while True:
            try:
                await asyncio.sleep(300)  # 5 minutes
                await self.send_trending_movies()
            except Exception as e:
                logger.error(f"Error in periodic trending updates: {str(e)}")
                break
    
    @database_sync_to_async
    def get_trending_movies(self):
        """Get trending movies from database"""
        movies = Movie.objects.all().order_by('-popularity', '-average_rating')[:15]
        return [{
            'id': movie.id,
            'title': movie.title,
            'poster_path': movie.poster_path,
            'overview': movie.overview,
            'release_date': movie.release_date.isoformat() if movie.release_date else None,
            'average_rating': float(movie.average_rating),
            'popularity': float(movie.popularity),
            'trending_score': float(movie.popularity) * float(movie.average_rating)
        } for movie in movies]
    
    @database_sync_to_async
    def get_trending_by_genre(self, genre_name):
        """Get trending movies by genre"""
        movies = Movie.objects.filter(
            genres__name__icontains=genre_name,

        ).order_by('-popularity', '-average_rating')[:10]
        return [{
            'id': movie.id,
            'title': movie.title,
            'poster_path': movie.poster_path,
            'overview': movie.overview,
            'release_date': movie.release_date.isoformat() if movie.release_date else None,
            'average_rating': float(movie.average_rating),
            'popularity': float(movie.popularity)
        } for movie in movies]
    
    # Handlers for group messages
    async def trending_update(self, event):
        """Handle trending update events"""
        await self.send(text_data=json.dumps({
            'type': 'trending_update',
            'data': event['data']
        }))

class RecommendationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for personalized recommendations"""
    
    async def connect(self):
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.room_group_name = f'recommendations_{self.user_id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"WebSocket connected to recommendations for user {self.user_id}: {self.channel_name}")
        
        # Send initial recommendations
        await self.send_recommendations()
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        logger.info(f"WebSocket disconnected from recommendations for user {self.user_id}: {self.channel_name}")
    
    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'get_recommendations':
                await self.send_recommendations()
            elif message_type == 'refresh_recommendations':
                await self.refresh_recommendations()
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error in RecommendationConsumer.receive: {str(e)}")
    
    async def send_recommendations(self):
        """Send user recommendations"""
        try:
            recommendations = await self.get_user_recommendations()
            await self.send(text_data=json.dumps({
                'type': 'recommendations',
                'data': recommendations
            }))
        except Exception as e:
            logger.error(f"Error sending recommendations: {str(e)}")
    
    async def refresh_recommendations(self):
        """Refresh and send updated recommendations"""
        try:
            # Clear cache and get fresh recommendations
            cache_key = f'user_recommendations_{self.user_id}'
            cache.delete(cache_key)
            recommendations = await self.get_user_recommendations()
            await self.send(text_data=json.dumps({
                'type': 'recommendations_refreshed',
                'data': recommendations
            }))
        except Exception as e:
            logger.error(f"Error refreshing recommendations: {str(e)}")
    
    @database_sync_to_async
    def get_user_recommendations(self):
        """Get user recommendations from database"""
        try:
            recommendations = Recommendation.objects.filter(
                user_id=self.user_id
            ).select_related('movie').order_by('-confidence_score')[:20]
            
            return [{
                'id': rec.movie.id,
                'title': rec.movie.title,
                'poster_path': rec.movie.poster_path,
                'overview': rec.movie.overview,
                'release_date': rec.movie.release_date.isoformat() if rec.movie.release_date else None,
                'average_rating': float(rec.movie.average_rating),
                'recommendation_score': float(rec.confidence_score),
                'algorithm': rec.algorithm_used
            } for rec in recommendations]
        except Exception as e:
            logger.error(f"Error getting user recommendations: {str(e)}")
            return []
    
    # Handlers for group messages
    async def recommendation_update(self, event):
        """Handle recommendation update events"""
        await self.send(text_data=json.dumps({
            'type': 'recommendation_update',
            'data': event['data']
        }))

class TrailerConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for trailer updates and streaming"""
    
    async def connect(self):
        self.room_group_name = 'trailers'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"WebSocket connected to trailers: {self.channel_name}")
        
        # Send latest trailers
        await self.send_latest_trailers()
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        logger.info(f"WebSocket disconnected from trailers: {self.channel_name}")
    
    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'get_latest_trailers':
                await self.send_latest_trailers()
            elif message_type == 'get_movie_trailers':
                movie_id = text_data_json.get('movie_id')
                await self.send_movie_trailers(movie_id)
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error in TrailerConsumer.receive: {str(e)}")
    
    async def send_latest_trailers(self):
        """Send latest movie trailers"""
        try:
            trailers = await self.get_latest_trailers()
            await self.send(text_data=json.dumps({
                'type': 'latest_trailers',
                'data': trailers
            }))
        except Exception as e:
            logger.error(f"Error sending latest trailers: {str(e)}")
    
    async def send_movie_trailers(self, movie_id):
        """Send trailers for specific movie"""
        try:
            trailers = await self.get_movie_trailers(movie_id)
            await self.send(text_data=json.dumps({
                'type': 'movie_trailers',
                'data': trailers,
                'movie_id': movie_id
            }))
        except Exception as e:
            logger.error(f"Error sending movie trailers: {str(e)}")
    
    @database_sync_to_async
    def get_latest_trailers(self):
        """Get latest trailers from database"""
        from .models import Trailer
        trailers = Trailer.objects.select_related('movie').filter(

        ).order_by('-created_at')[:15]
        
        return [{
            'id': trailer.id,
            'name': trailer.name,
            'key': trailer.key,
            'site': trailer.site,
            'type': trailer.type,
            'official': trailer.official,
            'movie': {
                'id': trailer.movie.id,
                'title': trailer.movie.title,
                'poster_path': trailer.movie.poster_path
            }
        } for trailer in trailers]
    
    @database_sync_to_async
    def get_movie_trailers(self, movie_id):
        """Get trailers for specific movie"""
        from .models import Trailer
        try:
            trailers = Trailer.objects.filter(
                movie_id=movie_id,
        
            ).order_by('-official', '-created_at')
            
            return [{
                'id': trailer.id,
                'name': trailer.name,
                'key': trailer.key,
                'site': trailer.site,
                'type': trailer.type,
                'official': trailer.official
            } for trailer in trailers]
        except Exception as e:
            logger.error(f"Error getting movie trailers: {str(e)}")
            return []
    
    # Handlers for group messages
    async def new_trailer(self, event):
        """Handle new trailer events"""
        await self.send(text_data=json.dumps({
            'type': 'new_trailer',
            'data': event['data']
        }))
    
    async def trailer_update(self, event):
        """Handle trailer update events"""
        await self.send(text_data=json.dumps({
            'type': 'trailer_update',
            'data': event['data']
        }))

class RatingConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time rating and feedback updates"""
    
    async def connect(self):
        self.movie_id = self.scope['url_route']['kwargs'].get('movie_id')
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Join movie-specific rating group
        self.rating_group_name = f'movie_ratings_{self.movie_id}'
        await self.channel_layer.group_add(
            self.rating_group_name,
            self.channel_name
        )
        
        # Join user-specific activity group
        self.user_activity_group = f'user_activity_{self.user.id}'
        await self.channel_layer.group_add(
            self.user_activity_group,
            self.channel_name
        )
        
        # Join global feedback group for recommendation feedback
        self.feedback_group_name = 'recommendation_feedback'
        await self.channel_layer.group_add(
            self.feedback_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send current rating data
        await self.send_current_ratings()
    
    async def disconnect(self, close_code):
        # Leave groups
        if hasattr(self, 'rating_group_name'):
            await self.channel_layer.group_discard(
                self.rating_group_name,
                self.channel_name
            )
        
        if hasattr(self, 'user_activity_group'):
            await self.channel_layer.group_discard(
                self.user_activity_group,
                self.channel_name
            )
            
        if hasattr(self, 'feedback_group_name'):
            await self.channel_layer.group_discard(
                self.feedback_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            action = data.get('action')
            
            if action == 'submit_rating':
                await self.handle_rating_submission(data)
            elif action == 'submit_feedback':
                await self.handle_feedback_submission(data)
            elif action == 'get_ratings':
                await self.send_current_ratings()
            elif action == 'get_user_activity':
                await self.send_user_activity()
            elif action == 'get_feedback_stats':
                await self.send_feedback_stats()
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'error': 'Invalid JSON format'
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'error': f'Server error: {str(e)}'
            }))
    
    async def handle_rating_submission(self, data):
        """Handle rating submission"""
        try:
            rating_value = data.get('rating')
            if rating_value is None or not (1 <= rating_value <= 10):
                await self.send(text_data=json.dumps({
                    'error': 'Invalid rating value'
                }))
                return
            
            # Save rating to database
            rating_data = await self.save_rating(rating_value)
            
            # Broadcast to movie rating group
            await self.channel_layer.group_send(
                self.rating_group_name,
                {
                    'type': 'rating_update',
                    'data': rating_data
                }
            )
            
        except Exception as e:
            logger.error(f"Error handling rating submission: {str(e)}")
    
    async def handle_feedback_submission(self, data):
        """Handle recommendation feedback submission"""
        try:
            feedback_type = data.get('feedback_type')  # 'like', 'dislike', 'not_interested'
            recommendation_id = data.get('recommendation_id')
            
            if not feedback_type or not recommendation_id:
                await self.send(text_data=json.dumps({
                    'error': 'Missing feedback data'
                }))
                return
            
            # Save feedback to database
            feedback_data = await self.save_feedback(recommendation_id, feedback_type)
            
            # Broadcast to feedback group
            await self.channel_layer.group_send(
                self.feedback_group_name,
                {
                    'type': 'feedback_update',
                    'data': feedback_data
                }
            )
            
        except Exception as e:
            logger.error(f"Error handling feedback submission: {str(e)}")
    
    async def send_current_ratings(self):
        """Send current movie ratings"""
        try:
            ratings_data = await self.get_movie_ratings()
            await self.send(text_data=json.dumps({
                'type': 'current_ratings',
                'data': ratings_data
            }))
        except Exception as e:
            logger.error(f"Error sending current ratings: {str(e)}")
    
    async def send_user_activity(self):
        """Send user activity data"""
        try:
            activity_data = await self.get_user_activity()
            await self.send(text_data=json.dumps({
                'type': 'user_activity',
                'data': activity_data
            }))
        except Exception as e:
            logger.error(f"Error sending user activity: {str(e)}")
    
    async def send_feedback_stats(self):
        """Send feedback statistics"""
        try:
            feedback_stats = await self.get_feedback_stats()
            await self.send(text_data=json.dumps({
                'type': 'feedback_stats',
                'data': feedback_stats
            }))
        except Exception as e:
            logger.error(f"Error sending feedback stats: {str(e)}")
    
    @database_sync_to_async
    def save_rating(self, rating_value):
        """Save user rating to database"""
        try:
            movie = Movie.objects.get(id=self.movie_id)
            rating, created = Rating.objects.update_or_create(
                user=self.user,
                movie=movie,
                defaults={'rating': rating_value}
            )
            
            return {
                'movie_id': self.movie_id,
                'user_id': self.user.id,
                'rating': rating_value,
                'created': created
            }
        except Movie.DoesNotExist:
            return None
    
    @database_sync_to_async
    def save_feedback(self, recommendation_id, feedback_type):
        """Save recommendation feedback to database"""
        try:
            from recommendations.models import RecommendationFeedback
            feedback, created = RecommendationFeedback.objects.update_or_create(
                user=self.user,
                recommendation_id=recommendation_id,
                defaults={'feedback_type': feedback_type}
            )
            
            return {
                'recommendation_id': recommendation_id,
                'user_id': self.user.id,
                'feedback_type': feedback_type,
                'created': created
            }
        except Exception as e:
            logger.error(f"Error saving feedback: {str(e)}")
            return None
    
    @database_sync_to_async
    def get_movie_ratings(self):
        """Get movie ratings data"""
        try:
            movie = Movie.objects.get(id=self.movie_id)
            ratings = Rating.objects.filter(movie=movie)
            
            total_ratings = ratings.count()
            avg_rating = ratings.aggregate(avg=models.Avg('rating'))['avg'] or 0
            
            user_rating = None
            if self.user.is_authenticated:
                try:
                    user_rating = ratings.get(user=self.user).rating
                except Rating.DoesNotExist:
                    pass
            
            return {
                'movie_id': self.movie_id,
                'total_ratings': total_ratings,
                'average_rating': float(avg_rating),
                'user_rating': user_rating
            }
        except Movie.DoesNotExist:
            return None
    
    @database_sync_to_async
    def get_user_activity(self):
        """Get user activity data"""
        try:
            ratings = Rating.objects.filter(user=self.user).order_by('-created_at')[:10]
            
            return {
                'user_id': self.user.id,
                'recent_ratings': [{
                    'movie_id': rating.movie.id,
                    'movie_title': rating.movie.title,
                    'rating': rating.rating,
                    'created_at': rating.created_at.isoformat()
                } for rating in ratings]
            }
        except Exception as e:
            logger.error(f"Error getting user activity: {str(e)}")
            return None
    
    @database_sync_to_async
    def get_feedback_stats(self):
        """Get feedback statistics"""
        try:
            from recommendations.models import RecommendationFeedback
            from django.db import models
            
            feedback_stats = RecommendationFeedback.objects.filter(
                user=self.user
            ).values('feedback_type').annotate(
                count=models.Count('id')
            )
            
            return {
                'user_id': self.user.id,
                'feedback_stats': list(feedback_stats)
            }
        except Exception as e:
            logger.error(f"Error getting feedback stats: {str(e)}")
            return None
    
    # Handlers for group messages
    async def rating_update(self, event):
        """Handle rating update events"""
        await self.send(text_data=json.dumps({
            'type': 'rating_update',
            'data': event['data']
        }))
    
    async def feedback_update(self, event):
        """Handle feedback update events"""
        await self.send(text_data=json.dumps({
            'type': 'feedback_update',
            'data': event['data']
        }))
    
    async def user_activity_update(self, event):
        """Handle user activity update events"""
        await self.send(text_data=json.dumps({
            'type': 'user_activity_update',
            'data': event['data']
        }))