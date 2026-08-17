from rest_framework import generics, status, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly, AllowAny
from rest_framework.pagination import PageNumberPagination
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Avg, Count, Prefetch
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)
from .models import Movie, Genre, Language, Country, Person, MovieCast, Rating, Watchlist
from .serializers import (
    MovieListSerializer, MovieDetailSerializer, MovieCreateUpdateSerializer,
    GenreSerializer, LanguageSerializer, CountrySerializer, PersonSerializer,
    RatingSerializer, WatchlistSerializer, MovieSearchSerializer
)
from .services import tmdb_service, omdb_service

User = get_user_model()

class MoviePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class MovieListCreateView(generics.ListCreateAPIView):
    """List all movies or create a new movie with enhanced performance and validation"""
    queryset = Movie.objects.select_related().prefetch_related(
        'genres', 'languages', 'countries',
        Prefetch('cast', queryset=MovieCast.objects.select_related('person'))
    )
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'cast__person__name']
    ordering_fields = ['title', 'release_date', 'created_at', 'duration', 'imdb_rating']
    ordering = ['-created_at']
    pagination_class = MoviePagination
    throttle_classes = [UserRateThrottle, AnonRateThrottle]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return MovieCreateUpdateSerializer
        return MovieListSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        try:
            # Add custom filtering logic with validation
            genre = self.request.query_params.get('genre')
            if genre:
                queryset = queryset.filter(genres__name__icontains=genre)
            
            year = self.request.query_params.get('year')
            if year:
                try:
                    year_int = int(year)
                    if 1900 <= year_int <= 2030:
                        queryset = queryset.filter(release_date__year=year_int)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid year parameter: {year}")
            
            min_rating = self.request.query_params.get('min_rating')
            if min_rating:
                try:
                    min_rating_float = float(min_rating)
                    if 0 <= min_rating_float <= 10:
                        queryset = queryset.annotate(
                            avg_rating=Avg('ratings__rating')
                        ).filter(avg_rating__gte=min_rating_float)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid min_rating parameter: {min_rating}")
            
            max_rating = self.request.query_params.get('max_rating')
            if max_rating:
                try:
                    max_rating_float = float(max_rating)
                    if 0 <= max_rating_float <= 10:
                        queryset = queryset.annotate(
                            avg_rating=Avg('ratings__rating')
                        ).filter(avg_rating__lte=max_rating_float)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid max_rating parameter: {max_rating}")
            
            # Additional filters
            duration_min = self.request.query_params.get('duration_min')
            if duration_min:
                try:
                    duration_min_int = int(duration_min)
                    if duration_min_int > 0:
                        queryset = queryset.filter(duration__gte=duration_min_int)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid duration_min parameter: {duration_min}")
            
            duration_max = self.request.query_params.get('duration_max')
            if duration_max:
                try:
                    duration_max_int = int(duration_max)
                    if duration_max_int > 0:
                        queryset = queryset.filter(duration__lte=duration_max_int)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid duration_max parameter: {duration_max}")
            
            return queryset.distinct()
        
        except Exception as e:
            logger.error(f"Error in MovieListCreateView.get_queryset: {str(e)}")
            return queryset

class MovieDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete a movie"""
    queryset = Movie.objects.all().prefetch_related(
        'genres', 'languages', 'countries', 'cast__person'
    )
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return MovieCreateUpdateSerializer
        return MovieDetailSerializer

class GenreListCreateView(generics.ListCreateAPIView):
    """List all genres or create a new genre"""
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering = ['name']

class LanguageListCreateView(generics.ListCreateAPIView):
    """List all languages or create a new language"""
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code']
    ordering = ['name']

class CountryListCreateView(generics.ListCreateAPIView):
    """List all countries or create a new country"""
    queryset = Country.objects.all()
    serializer_class = CountrySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code']
    ordering = ['name']

class PersonListCreateView(generics.ListCreateAPIView):
    """List all persons or create a new person"""
    queryset = Person.objects.all()
    serializer_class = PersonSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering = ['name']

class PersonDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete a person"""
    queryset = Person.objects.all()
    serializer_class = PersonSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

class RatingListCreateView(generics.ListCreateAPIView):
    """List user's ratings or create a new rating"""
    serializer_class = RatingSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering = ['-created_at']
    
    def get_queryset(self):
        return Rating.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        try:
            # Check if user already rated this movie
            movie = serializer.validated_data['movie']
            existing_rating = Rating.objects.filter(
                user=self.request.user, movie=movie
            ).first()
            
            if existing_rating:
                # Update existing rating
                for attr, value in serializer.validated_data.items():
                    setattr(existing_rating, attr, value)
                existing_rating.save()
                logger.info(f"Rating updated: User {self.request.user.id} updated rating for movie {movie.id}")
                return existing_rating
            else:
                # Create new rating
                rating = serializer.save(user=self.request.user)
                logger.info(f"Rating created: User {self.request.user.id} rated movie {movie.id}")
                return rating
        except Exception as e:
            logger.error(f"Error creating/updating rating: {str(e)}")
            raise ValidationError("Failed to create or update rating. Please try again.")

class RatingDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete a rating"""
    serializer_class = RatingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Rating.objects.filter(user=self.request.user)

class WatchlistListCreateView(generics.ListCreateAPIView):
    """List user's watchlist or add a movie to watchlist"""
    serializer_class = WatchlistSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering = ['-added_at']
    
    def get_queryset(self):
        return Watchlist.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        # Check if movie is already in watchlist
        movie_id = serializer.validated_data['movie_id']
        existing_item = Watchlist.objects.filter(
            user=self.request.user, movie_id=movie_id
        ).first()
        
        if existing_item:
            return Response(
                {'detail': 'Movie is already in your watchlist.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer.save(user=self.request.user)

class WatchlistDetailView(generics.RetrieveDestroyAPIView):
    """Retrieve or remove a movie from watchlist"""
    serializer_class = WatchlistSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Watchlist.objects.filter(user=self.request.user)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_watchlist(request, movie_id):
    """Toggle movie in user's watchlist"""
    movie = get_object_or_404(Movie, id=movie_id)
    watchlist_item = Watchlist.objects.filter(
        user=request.user, movie=movie
    ).first()
    
    if watchlist_item:
        watchlist_item.delete()
        return Response(
            {'detail': 'Movie removed from watchlist.', 'in_watchlist': False},
            status=status.HTTP_200_OK
        )
    else:
        Watchlist.objects.create(user=request.user, movie=movie)
        return Response(
            {'detail': 'Movie added to watchlist.', 'in_watchlist': True},
            status=status.HTTP_201_CREATED
        )

@api_view(['GET'])
def movie_search(request):
    """Advanced movie search with multiple filters"""
    serializer = MovieSearchSerializer(data=request.query_params)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    queryset = Movie.objects.all().prefetch_related('genres', 'languages', 'countries')
    
    # Apply filters
    if data.get('query'):
        queryset = queryset.filter(
            Q(title__icontains=data['query']) |
            Q(description__icontains=data['query'])
        )
    
    if data.get('genre'):
        queryset = queryset.filter(genres__name__icontains=data['genre'])
    
    if data.get('year'):
        queryset = queryset.filter(release_date__year=data['year'])
    
    if data.get('language'):
        queryset = queryset.filter(languages__name__icontains=data['language'])
    
    if data.get('country'):
        queryset = queryset.filter(countries__name__icontains=data['country'])
    
    if data.get('duration_min'):
        queryset = queryset.filter(duration__gte=data['duration_min'])
    
    if data.get('duration_max'):
        queryset = queryset.filter(duration__lte=data['duration_max'])
    
    # Rating filters
    if data.get('min_rating') or data.get('max_rating'):
        queryset = queryset.annotate(avg_rating=Avg('ratings__rating'))
        
        if data.get('min_rating'):
            queryset = queryset.filter(avg_rating__gte=data['min_rating'])
        
        if data.get('max_rating'):
            queryset = queryset.filter(avg_rating__lte=data['max_rating'])
    
    # Sorting
    sort_by = data.get('sort_by', 'created_at')
    order = data.get('order', 'desc')
    
    if sort_by == 'rating':
        queryset = queryset.annotate(avg_rating=Avg('ratings__rating'))
        sort_field = 'avg_rating'
    else:
        sort_field = sort_by
    
    if order == 'desc':
        sort_field = f'-{sort_field}'
    
    queryset = queryset.order_by(sort_field).distinct()
    
    # Pagination
    from rest_framework.pagination import PageNumberPagination
    paginator = PageNumberPagination()
    paginator.page_size = 20
    page = paginator.paginate_queryset(queryset, request)
    
    if page is not None:
        serializer = MovieListSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)
    
    serializer = MovieListSerializer(queryset, many=True, context={'request': request})
    return Response(serializer.data)

@api_view(['GET'])
def popular_movies(request):
    """Get popular movies based on ratings and rating count"""
    movies = Movie.objects.annotate(
        avg_rating=Avg('ratings__rating'),
        rating_count=Count('ratings')
    ).filter(
        rating_count__gte=5  # At least 5 ratings
    ).order_by('-avg_rating', '-rating_count')[:20]
    
    serializer = MovieListSerializer(movies, many=True, context={'request': request})
    return Response(serializer.data)

@api_view(['GET'])
def recent_movies(request):
    """Get recently added movies"""
    movies = Movie.objects.order_by('-created_at')[:20]
    serializer = MovieListSerializer(movies, many=True, context={'request': request})
    return Response(serializer.data)

@api_view(['GET'])
def movie_stats(request, movie_id):
    """Get statistics for a specific movie"""
    movie = get_object_or_404(Movie, id=movie_id)
    
    stats = {
        'total_ratings': movie.ratings.count(),
        'average_rating': movie.ratings.aggregate(avg=Avg('rating'))['avg'],
        'rating_distribution': {},
        'total_watchlisted': movie.watchlists.count()
    }
    
    # Rating distribution (1-10)
    for i in range(1, 11):
        count = movie.ratings.filter(rating=i).count()
        stats['rating_distribution'][str(i)] = count
    
    return Response(stats)

@api_view(['GET'])
@permission_classes([AllowAny])
def movie_ratings(request, movie_id):
    """Get all ratings for a specific movie"""
    try:
        movie = get_object_or_404(Movie, id=movie_id)
        ratings = Rating.objects.filter(movie=movie).select_related('user').order_by('-created_at')
        
        # Paginate results
        paginator = MoviePagination()
        page = paginator.paginate_queryset(ratings, request)
        
        if page is not None:
            serializer = RatingSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = RatingSerializer(ratings, many=True)
        return Response(serializer.data)
        
    except Exception as e:
        logger.error(f"Error fetching movie ratings: {str(e)}")
        return Response(
            {'error': 'Failed to fetch movie ratings'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# External API Integration Views

@api_view(['GET'])
@permission_classes([AllowAny])
def tmdb_search(request):
    """Search movies using TMDB API"""
    query = request.GET.get('q', '')
    page = request.GET.get('page', 1)
    
    if not query:
        return Response(
            {'error': 'Query parameter is required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        page = int(page)
    except ValueError:
        page = 1
    
    results = tmdb_service.search_movies(query, page)
    
    if results is None:
        return Response(
            {'error': 'External API unavailable'}, 
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    return Response(results)


@api_view(['GET'])
@permission_classes([AllowAny])
def tmdb_popular(request):
    """Get popular movies from TMDB"""
    page = request.GET.get('page', 1)
    
    try:
        page = int(page)
    except ValueError:
        page = 1
    
    results = tmdb_service.get_popular_movies(page)
    
    if results is None:
        return Response(
            {'error': 'External API unavailable'}, 
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    return Response(results)


@api_view(['GET'])
@permission_classes([AllowAny])
def tmdb_trending(request):
    """Get trending movies from TMDB"""
    time_window = request.GET.get('time_window', 'week')
    page = request.GET.get('page', 1)
    
    if time_window not in ['day', 'week']:
        time_window = 'week'
    
    try:
        page = int(page)
    except ValueError:
        page = 1
    
    results = tmdb_service.get_trending_movies(time_window, page)
    
    if results is None:
        return Response(
            {'error': 'External API unavailable'}, 
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    return Response(results)


@api_view(['GET'])
@permission_classes([AllowAny])
def tmdb_movie_details(request, tmdb_id):
    """Get detailed movie information from TMDB"""
    try:
        tmdb_id = int(tmdb_id)
    except ValueError:
        return Response(
            {'error': 'Invalid TMDB ID'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    results = tmdb_service.get_movie_details(tmdb_id)
    
    if results is None:
        return Response(
            {'error': 'Movie not found or API unavailable'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    return Response(results)


@api_view(['GET'])
@permission_classes([AllowAny])
def tmdb_movie_recommendations(request, tmdb_id):
    """Get movie recommendations from TMDB"""
    page = request.GET.get('page', 1)
    
    try:
        tmdb_id = int(tmdb_id)
        page = int(page)
    except ValueError:
        return Response(
            {'error': 'Invalid parameters'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    results = tmdb_service.get_movie_recommendations(tmdb_id, page)
    
    if results is None:
        return Response(
            {'error': 'External API unavailable'}, 
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    return Response(results)


@api_view(['GET'])
@permission_classes([AllowAny])
def tmdb_similar_movies(request, tmdb_id):
    """Get similar movies from TMDB"""
    page = request.GET.get('page', 1)
    
    try:
        tmdb_id = int(tmdb_id)
        page = int(page)
    except ValueError:
        return Response(
            {'error': 'Invalid parameters'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    results = tmdb_service.get_similar_movies(tmdb_id, page)
    
    if results is None:
        return Response(
            {'error': 'External API unavailable'}, 
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    return Response(results)


@api_view(['GET'])
@permission_classes([AllowAny])
def omdb_movie_details(request, imdb_id):
    """Get movie details from OMDB by IMDB ID"""
    if not imdb_id.startswith('tt'):
        return Response(
            {'error': 'Invalid IMDB ID format'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    results = omdb_service.get_movie_by_imdb_id(imdb_id)
    
    if results is None:
        return Response(
            {'error': 'Movie not found or API unavailable'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    return Response(results)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def import_movie_from_tmdb(request):
    """Import a movie from TMDB into our database"""
    tmdb_id = request.data.get('tmdb_id')
    
    if not tmdb_id:
        return Response(
            {'error': 'TMDB ID is required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        tmdb_id = int(tmdb_id)
    except ValueError:
        return Response(
            {'error': 'Invalid TMDB ID'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if movie already exists
    existing_movie = Movie.objects.filter(tmdb_id=tmdb_id).first()
    if existing_movie:
        serializer = MovieDetailSerializer(existing_movie)
        return Response({
            'message': 'Movie already exists in database',
            'movie': serializer.data
        })
    
    # Get movie details from TMDB
    movie_data = tmdb_service.get_movie_details(tmdb_id)
    
    if not movie_data:
        return Response(
            {'error': 'Movie not found in TMDB'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    try:
        # Import the movie using the management command logic
        from django.core.management import call_command
        from io import StringIO
        
        # This would ideally use the import logic from the management command
        # For now, we'll create a basic movie entry
        movie = Movie.objects.create(
            tmdb_id=tmdb_id,
            title=movie_data.get('title', ''),
            original_title=movie_data.get('original_title', ''),
            overview=movie_data.get('overview', ''),
            tagline=movie_data.get('tagline', ''),
            duration=movie_data.get('runtime'),
            budget=movie_data.get('budget'),
            revenue=movie_data.get('revenue'),
            poster_url=tmdb_service.get_image_url(movie_data.get('poster_path')),
            backdrop_url=tmdb_service.get_image_url(movie_data.get('backdrop_path'), 'w1280'),
            tmdb_rating=movie_data.get('vote_average'),
                average_rating=movie_data.get('vote_average', 0),
            popularity=movie_data.get('popularity', 0),
            adult=movie_data.get('adult', False),
            imdb_id=movie_data.get('imdb_id', ''),
        )
        
        # Parse release date
        release_date = movie_data.get('release_date')
        if release_date:
            try:
                from datetime import datetime
                movie.release_date = datetime.strptime(release_date, '%Y-%m-%d').date()
                movie.year = movie.release_date.year
                movie.save()
            except ValueError:
                pass
        
        serializer = MovieDetailSerializer(movie)
        return Response({
            'message': 'Movie imported successfully',
            'movie': serializer.data
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response(
            {'error': f'Failed to import movie: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def tmdb_trending_movies(request):
    """Get trending movies from TMDB or fallback to local database"""
    from .services import TMDBService
    from .serializers import MovieListSerializer
    from django.db.models import Avg, Count
    
    try:
        tmdb_service = TMDBService()
        time_window = request.GET.get('time_window', 'day')  # day or week
        page = int(request.GET.get('page', 1))
        
        # Try to get data from TMDB first
        data = tmdb_service.get_trending_movies(time_window=time_window, page=page)
        
        # If TMDB fails (no API key or network error), fallback to local database
        if data is None:
            # Get trending movies from local database
            trending_movies = Movie.objects.annotate(
                avg_rating=Avg('ratings__rating'),
                rating_count=Count('ratings')
            ).filter(
                rating_count__gte=1  # At least 1 rating
            ).order_by('-popularity', '-tmdb_rating')[:20]
            
            # Format response similar to TMDB structure
            serializer = MovieListSerializer(trending_movies, many=True)
            data = {
                'page': page,
                'results': serializer.data,
                'total_pages': 1,
                'total_results': len(serializer.data)
            }
        
        return Response(data)
    except Exception as e:
        return Response(
            {'error': f'Failed to fetch trending movies: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def tmdb_popular_movies(request):
    """Get popular movies from TMDB"""
    from .services import TMDBService
    
    try:
        tmdb_service = TMDBService()
        page = int(request.GET.get('page', 1))
        data = tmdb_service.get_popular_movies(page=page)
        return Response(data)
    except Exception as e:
        return Response(
            {'error': f'Failed to fetch popular movies: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def tmdb_upcoming_movies(request):
    """Get upcoming movies from TMDB"""
    from .services import TMDBService
    
    try:
        tmdb_service = TMDBService()
        page = int(request.GET.get('page', 1))
        data = tmdb_service.get_upcoming_movies(page=page)
        return Response(data)
    except Exception as e:
        return Response(
            {'error': f'Failed to fetch upcoming movies: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def tmdb_search_movies(request):
    """Search movies on TMDB"""
    from .services import TMDBService
    
    try:
        tmdb_service = TMDBService()
        query = request.GET.get('query')
        if not query:
            return Response(
                {'error': 'Query parameter is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        page = int(request.GET.get('page', 1))
        year = request.GET.get('year')
        
        data = tmdb_service.search_movies(query=query, page=page, year=year)
        return Response(data)
    except Exception as e:
        return Response(
            {'error': f'Failed to search movies: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_tmdb_movie(request):
    """Sync a specific movie from TMDB by ID"""
    from .services import TMDBService
    
    try:
        tmdb_service = TMDBService()
        tmdb_id = request.data.get('tmdb_id')
        if not tmdb_id:
            return Response(
                {'error': 'tmdb_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get detailed movie data from TMDB
        movie_data = tmdb_service.get_movie_details(tmdb_id)
        
        # Create or update movie in our database
        movie = tmdb_service.create_or_update_movie(movie_data)
        
        if movie:
            serializer = MovieDetailSerializer(movie)
            return Response({
                'message': 'Movie synced successfully',
                'movie': serializer.data
            })
        else:
            return Response(
                {'error': 'Failed to sync movie'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    except Exception as e:
        return Response(
            {'error': f'Failed to sync movie: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_sync_tmdb_movies(request):
    """Bulk sync movies from TMDB"""
    from .services import TMDBService
    
    try:
        tmdb_service = TMDBService()
        sync_type = request.data.get('type', 'trending')  # trending, popular, upcoming
        limit = int(request.data.get('limit', 20))
        
        if sync_type == 'trending':
            count = tmdb_service.sync_trending_movies(limit=limit)
        elif sync_type == 'popular':
            count = tmdb_service.sync_popular_movies(limit=limit)
        else:
            return Response(
                {'error': 'Invalid sync type. Use: trending, popular'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({
            'message': f'Successfully synced {count} {sync_type} movies',
            'count': count,
            'type': sync_type
        })
    
    except Exception as e:
        return Response(
            {'error': f'Failed to bulk sync movies: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
