from django.core.management.base import BaseCommand
from django.conf import settings
from movies.tmdb_service import tmdb_service
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sync movie data from TMDB API'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['trending', 'popular', 'upcoming', 'genres', 'ratings'],
            default='trending',
            help='Type of data to sync (default: trending)'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=20,
            help='Number of movies to sync (default: 20)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force sync even if API key is not configured'
        )
    
    def handle(self, *args, **options):
        sync_type = options['type']
        limit = options['limit']
        force = options['force']
        
        # Check if TMDB API key is configured
        if not tmdb_service.api_key and not force:
            self.stdout.write(
                self.style.ERROR(
                    'TMDB API key not configured. Set TMDB_API_KEY in settings or use --force flag.'
                )
            )
            return
        
        self.stdout.write(f'Starting TMDB sync: {sync_type} (limit: {limit})')
        
        try:
            if sync_type == 'trending':
                count = tmdb_service.sync_trending_movies(limit=limit)
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully synced {count} trending movies')
                )
            
            elif sync_type == 'popular':
                count = tmdb_service.sync_popular_movies(limit=limit)
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully synced {count} popular movies')
                )
            
            elif sync_type == 'upcoming':
                # Get upcoming movies
                upcoming_data = tmdb_service.get_upcoming_movies()
                count = 0
                
                for movie_data in upcoming_data.get('results', [])[:limit]:
                    detailed_data = tmdb_service.get_movie_details(movie_data['id'])
                    movie = tmdb_service.create_or_update_movie(detailed_data)
                    if movie:
                        count += 1
                
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully synced {count} upcoming movies')
                )
            
            elif sync_type == 'genres':
                success = tmdb_service.sync_genres()
                if success:
                    self.stdout.write(
                        self.style.SUCCESS('Successfully synced genres from TMDB')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR('Failed to sync genres')
                    )
            
            elif sync_type == 'ratings':
                count = tmdb_service.update_movie_ratings()
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully updated ratings for {count} movies')
                )
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during TMDB sync: {str(e)}')
            )
            logger.error(f'TMDB sync error: {e}', exc_info=True)
        
        self.stdout.write('TMDB sync completed')