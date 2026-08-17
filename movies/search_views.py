from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Avg, Count, F, Case, When, IntegerField
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
import logging
import json
from datetime import datetime, timedelta

from .models import Movie, Genre, Language, Country, Person, Rating
from .serializers import MovieListSerializer, MovieSearchSerializer
from recommendations.models import UserMovieInteraction

logger = logging.getLogger(__name__)

class SearchPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

@api_view(['GET'])
@permission_classes([AllowAny])
def enhanced_movie_search(request):
    """
    Enhanced movie search with real-time capabilities, autocomplete, and advanced filtering
    """
    try:
        # Get search parameters
        query = request.GET.get('q', '').strip()
        genre = request.GET.get('genre', '')
        year = request.GET.get('year', '')
        min_rating = request.GET.get('min_rating', '')
        max_rating = request.GET.get('max_rating', '')
        language = request.GET.get('language', '')
        country = request.GET.get('country', '')
        sort_by = request.GET.get('sort_by', 'relevance')  # relevance, rating, year, title
        order = request.GET.get('order', 'desc')
        include_adult = request.GET.get('include_adult', 'false').lower() == 'true'
        
        # Create cache key for this search
        cache_key = f"search:{hash(str(request.GET.dict()))}"
        cached_result = cache.get(cache_key)
        
        if cached_result and not request.GET.get('no_cache'):
            return Response(cached_result)
        
        # Start with base queryset
        queryset = Movie.objects.select_related().prefetch_related(
            'genres', 'languages', 'countries', 'cast__person'
        )
        
        # Apply adult content filter
        if not include_adult:
            queryset = queryset.filter(adult=False)
        
        # Text search with ranking
        if query:
            # Use PostgreSQL full-text search if available, otherwise use icontains
            try:
                search_vector = SearchVector('title', weight='A') + \
                               SearchVector('description', weight='B') + \
                               SearchVector('tagline', weight='C')
                search_query = SearchQuery(query)
                
                queryset = queryset.annotate(
                    search=search_vector,
                    rank=SearchRank(search_vector, search_query)
                ).filter(search=search_query).order_by('-rank')
            except:
                # Fallback to simple text search
                queryset = queryset.filter(
                    Q(title__icontains=query) |
                    Q(description__icontains=query) |
                    Q(tagline__icontains=query) |
                    Q(cast__person__name__icontains=query)
                ).distinct()
        
        # Apply filters
        if genre:
            queryset = queryset.filter(genres__name__icontains=genre)
        
        if year:
            try:
                year_int = int(year)
                queryset = queryset.filter(release_date__year=year_int)
            except ValueError:
                pass
        
        if language:
            queryset = queryset.filter(languages__name__icontains=language)
        
        if country:
            queryset = queryset.filter(countries__name__icontains=country)
        
        # Rating filters
        if min_rating or max_rating:
            queryset = queryset.annotate(avg_rating=Avg('ratings__rating'))
            
            if min_rating:
                try:
                    min_rating_float = float(min_rating)
                    queryset = queryset.filter(avg_rating__gte=min_rating_float)
                except ValueError:
                    pass
            
            if max_rating:
                try:
                    max_rating_float = float(max_rating)
                    queryset = queryset.filter(avg_rating__lte=max_rating_float)
                except ValueError:
                    pass
        
        # Sorting
        if sort_by == 'rating':
            if 'avg_rating' not in [f.name for f in queryset.query.annotations]:
                queryset = queryset.annotate(avg_rating=Avg('ratings__rating'))
            sort_field = 'avg_rating'
        elif sort_by == 'year':
            sort_field = 'release_date'
        elif sort_by == 'title':
            sort_field = 'title'
        elif sort_by == 'popularity':
            queryset = queryset.annotate(
                popularity_score=Count('ratings') + Count('watchlists')
            )
            sort_field = 'popularity_score'
        else:  # relevance or default
            if query and 'rank' in [f.name for f in queryset.query.annotations]:
                sort_field = 'rank'
            else:
                sort_field = 'created_at'
        
        if order == 'desc' and not sort_field.startswith('-'):
            sort_field = f'-{sort_field}'
        elif order == 'asc' and sort_field.startswith('-'):
            sort_field = sort_field[1:]
        
        queryset = queryset.order_by(sort_field).distinct()
        
        # Pagination
        paginator = SearchPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = MovieListSerializer(page, many=True, context={'request': request})
            result = paginator.get_paginated_response(serializer.data).data
        else:
            serializer = MovieListSerializer(queryset, many=True, context={'request': request})
            result = serializer.data
        
        # Cache the result for 5 minutes
        cache.set(cache_key, result, 300)
        
        return Response(result)
        
    except Exception as e:
        logger.error(f"Error in enhanced movie search: {str(e)}")
        return Response(
            {'error': 'Search failed. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([AllowAny])
def search_autocomplete(request):
    """
    Provide autocomplete suggestions for search queries
    """
    try:
        query = request.GET.get('q', '').strip()
        limit = min(int(request.GET.get('limit', 10)), 20)
        
        if len(query) < 2:
            return Response({'suggestions': []})
        
        # Cache key for autocomplete
        cache_key = f"autocomplete:{query.lower()}:{limit}"
        cached_suggestions = cache.get(cache_key)
        
        if cached_suggestions:
            return Response({'suggestions': cached_suggestions})
        
        suggestions = []
        
        # Movie title suggestions
        movie_titles = Movie.objects.filter(
            title__icontains=query
        ).values_list('title', flat=True)[:limit//2]
        
        for title in movie_titles:
            suggestions.append({
                'type': 'movie',
                'text': title,
                'category': 'Movies'
            })
        
        # Genre suggestions
        genres = Genre.objects.filter(
            name__icontains=query
        ).values_list('name', flat=True)[:3]
        
        for genre in genres:
            suggestions.append({
                'type': 'genre',
                'text': genre,
                'category': 'Genres'
            })
        
        # Person suggestions (actors, directors)
        persons = Person.objects.filter(
            name__icontains=query
        ).values_list('name', flat=True)[:3]
        
        for person in persons:
            suggestions.append({
                'type': 'person',
                'text': person,
                'category': 'People'
            })
        
        # Limit total suggestions
        suggestions = suggestions[:limit]
        
        # Cache for 1 hour
        cache.set(cache_key, suggestions, 3600)
        
        return Response({'suggestions': suggestions})
        
    except Exception as e:
        logger.error(f"Error in search autocomplete: {str(e)}")
        return Response({'suggestions': []})

@api_view(['GET'])
@permission_classes([AllowAny])
def search_filters(request):
    """
    Get available filter options for search
    """
    try:
        cache_key = "search_filters"
        cached_filters = cache.get(cache_key)
        
        if cached_filters:
            return Response(cached_filters)
        
        # Get current year for year range
        current_year = datetime.now().year
        
        filters = {
            'genres': list(Genre.objects.values('id', 'name').order_by('name')),
            'languages': list(Language.objects.values('id', 'name').order_by('name')),
            'countries': list(Country.objects.values('id', 'name').order_by('name')),
            'year_range': {
                'min': Movie.objects.aggregate(
                    min_year=models.Min('release_date__year')
                )['min_year'] or 1900,
                'max': current_year
            },
            'rating_range': {
                'min': 1.0,
                'max': 10.0
            },
            'sort_options': [
                {'value': 'relevance', 'label': 'Relevance'},
                {'value': 'rating', 'label': 'Rating'},
                {'value': 'year', 'label': 'Release Year'},
                {'value': 'title', 'label': 'Title'},
                {'value': 'popularity', 'label': 'Popularity'}
            ]
        }
        
        # Cache for 1 hour
        cache.set(cache_key, filters, 3600)
        
        return Response(filters)
        
    except Exception as e:
        logger.error(f"Error getting search filters: {str(e)}")
        return Response(
            {'error': 'Failed to load filters'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def personalized_search(request):
    """
    Personalized search based on user preferences and history
    """
    try:
        user = request.user
        query = request.GET.get('q', '').strip()
        
        # Get user's preferred genres from ratings
        preferred_genres = Genre.objects.filter(
            movies__ratings__user=user,
            movies__ratings__rating__gte=7
        ).annotate(
            preference_score=Avg('movies__ratings__rating')
        ).order_by('-preference_score')[:5]
        
        # Get user's interaction history
        interacted_movies = UserMovieInteraction.objects.filter(
            user=user
        ).values_list('movie_id', flat=True)
        
        # Base search
        queryset = Movie.objects.select_related().prefetch_related(
            'genres', 'languages', 'countries'
        ).exclude(id__in=interacted_movies)  # Exclude already interacted movies
        
        # Apply text search if provided
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query)
            )
        
        # Boost movies in preferred genres
        genre_cases = []
        for i, genre in enumerate(preferred_genres):
            genre_cases.append(
                When(genres=genre, then=5 - i)  # Higher score for more preferred genres
            )
        
        queryset = queryset.annotate(
            preference_boost=Case(
                *genre_cases,
                default=0,
                output_field=IntegerField()
            ),
            avg_rating=Avg('ratings__rating'),
            rating_count=Count('ratings')
        ).order_by('-preference_boost', '-avg_rating', '-rating_count')
        
        # Pagination
        paginator = SearchPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = MovieListSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)
        
        serializer = MovieListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)
        
    except Exception as e:
        logger.error(f"Error in personalized search: {str(e)}")
        return Response(
            {'error': 'Personalized search failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_search_query(request):
    """
    Save user's search query for analytics and personalization
    """
    try:
        query = request.data.get('query', '').strip()
        filters = request.data.get('filters', {})
        results_count = request.data.get('results_count', 0)
        
        if not query:
            return Response(
                {'error': 'Query is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Save to user interactions (you might want to create a SearchQuery model)
        UserMovieInteraction.objects.create(
            user=request.user,
            interaction_type='search',
            interaction_data={
                'query': query,
                'filters': filters,
                'results_count': results_count,
                'timestamp': datetime.now().isoformat()
            }
        )
        
        return Response({'status': 'saved'})
        
    except Exception as e:
        logger.error(f"Error saving search query: {str(e)}")
        return Response(
            {'error': 'Failed to save search query'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recent_searches(request):
    """
    Get user's recent search queries
    """
    try:
        user = request.user
        limit = min(int(request.GET.get('limit', 10)), 20)
        
        # Get recent search interactions
        recent_searches = UserMovieInteraction.objects.filter(
            user=user,
            interaction_type='search'
        ).order_by('-created_at')[:limit]
        
        searches = []
        for interaction in recent_searches:
            data = interaction.interaction_data or {}
            searches.append({
                'query': data.get('query', ''),
                'filters': data.get('filters', {}),
                'results_count': data.get('results_count', 0),
                'timestamp': interaction.created_at.isoformat()
            })
        
        return Response({'recent_searches': searches})
        
    except Exception as e:
        logger.error(f"Error getting recent searches: {str(e)}")
        return Response({'recent_searches': []})