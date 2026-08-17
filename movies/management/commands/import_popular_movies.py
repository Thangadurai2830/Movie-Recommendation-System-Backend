from django.core.management.base import BaseCommand
from django.db import transaction
from movies.models import Movie, Genre, Language, Country, Person, MovieCast
from movies.services import tmdb_service
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import popular movies from TMDB API'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--pages',
            type=int,
            default=5,
            help='Number of pages to import (default: 5)'
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing movies if they already exist'
        )
    
    def handle(self, *args, **options):
        pages = options['pages']
        update_existing = options['update_existing']
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting import of popular movies ({pages} pages)...')
        )
        
        total_imported = 0
        total_updated = 0
        total_skipped = 0
        
        for page in range(1, pages + 1):
            self.stdout.write(f'Processing page {page}...')
            
            # Get popular movies from TMDB
            popular_data = tmdb_service.get_popular_movies(page=page)
            
            if not popular_data or 'results' not in popular_data:
                self.stdout.write(
                    self.style.WARNING(f'No data received for page {page}')
                )
                continue
            
            for movie_data in popular_data['results']:
                try:
                    result = self.import_movie(movie_data, update_existing)
                    if result == 'imported':
                        total_imported += 1
                    elif result == 'updated':
                        total_updated += 1
                    else:
                        total_skipped += 1
                        
                except Exception as e:
                    logger.error(f"Error importing movie {movie_data.get('title', 'Unknown')}: {e}")
                    self.stdout.write(
                        self.style.ERROR(f"Error importing {movie_data.get('title', 'Unknown')}: {e}")
                    )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Import completed! Imported: {total_imported}, '
                f'Updated: {total_updated}, Skipped: {total_skipped}'
            )
        )
    
    def import_movie(self, movie_data, update_existing=False):
        """Import a single movie from TMDB data"""
        tmdb_id = movie_data.get('id')
        
        if not tmdb_id:
            return 'skipped'
        
        # Check if movie already exists
        existing_movie = Movie.objects.filter(tmdb_id=tmdb_id).first()
        
        if existing_movie and not update_existing:
            return 'skipped'
        
        # Get detailed movie information
        detailed_data = tmdb_service.get_movie_details(tmdb_id)
        
        if not detailed_data:
            return 'skipped'
        
        with transaction.atomic():
            # Create or update movie
            movie_defaults = {
                'title': detailed_data.get('title', ''),
                'original_title': detailed_data.get('original_title', ''),
                'overview': detailed_data.get('overview', ''),
                'tagline': detailed_data.get('tagline', ''),
                'release_date': self.parse_date(detailed_data.get('release_date')),
                'duration': detailed_data.get('runtime'),
                'budget': detailed_data.get('budget'),
                'revenue': detailed_data.get('revenue'),
                'poster_url': tmdb_service.get_image_url(detailed_data.get('poster_path')),
                'backdrop_url': tmdb_service.get_image_url(detailed_data.get('backdrop_path'), 'w1280'),
                'tmdb_rating': detailed_data.get('vote_average'),
                'popularity': detailed_data.get('popularity', 0),
                'adult': detailed_data.get('adult', False),
                'status': self.map_status(detailed_data.get('status')),
                'imdb_id': detailed_data.get('imdb_id', ''),
            }
            
            # Extract year from release date
            if movie_defaults['release_date']:
                movie_defaults['year'] = movie_defaults['release_date'].year
            
            if existing_movie:
                for key, value in movie_defaults.items():
                    setattr(existing_movie, key, value)
                existing_movie.save()
                movie = existing_movie
                result = 'updated'
            else:
                movie = Movie.objects.create(tmdb_id=tmdb_id, **movie_defaults)
                result = 'imported'
            
            # Handle genres
            if 'genres' in detailed_data:
                movie.genres.clear()
                for genre_data in detailed_data['genres']:
                    genre, _ = Genre.objects.get_or_create(
                        name=genre_data['name']
                    )
                    movie.genres.add(genre)
            
            # Handle languages
            if 'spoken_languages' in detailed_data:
                movie.languages.clear()
                for lang_data in detailed_data['spoken_languages']:
                    language, _ = Language.objects.get_or_create(
                        name=lang_data['english_name'],
                        defaults={'code': lang_data.get('iso_639_1', '')}
                    )
                    movie.languages.add(language)
            
            # Handle countries
            if 'production_countries' in detailed_data:
                movie.countries.clear()
                for country_data in detailed_data['production_countries']:
                    country, _ = Country.objects.get_or_create(
                        name=country_data['name'],
                        defaults={'code': country_data.get('iso_3166_1', '')}
                    )
                    movie.countries.add(country)
            
            # Handle cast and crew
            if 'credits' in detailed_data:
                self.import_cast_and_crew(movie, detailed_data['credits'])
            
            self.stdout.write(f'  {result.capitalize()}: {movie.title}')
            
            return result
    
    def import_cast_and_crew(self, movie, credits_data):
        """Import cast and crew for a movie"""
        # Clear existing cast
        movie.cast.all().delete()
        
        # Import cast (actors)
        if 'cast' in credits_data:
            for i, cast_member in enumerate(credits_data['cast'][:20]):  # Limit to top 20
                person = self.get_or_create_person(cast_member)
                if person:
                    MovieCast.objects.create(
                        movie=movie,
                        person=person,
                        role='actor',
                        character_name=cast_member.get('character', ''),
                        order=i
                    )
        
        # Import crew (directors, producers, etc.)
        if 'crew' in credits_data:
            for crew_member in credits_data['crew']:
                job = crew_member.get('job', '').lower()
                role = self.map_crew_job_to_role(job)
                
                if role:
                    person = self.get_or_create_person(crew_member)
                    if person:
                        # Check if this person-role combination already exists
                        if not MovieCast.objects.filter(
                            movie=movie, person=person, role=role
                        ).exists():
                            MovieCast.objects.create(
                                movie=movie,
                                person=person,
                                role=role
                            )
    
    def get_or_create_person(self, person_data):
        """Get or create a person from TMDB data"""
        tmdb_id = person_data.get('id')
        name = person_data.get('name')
        
        if not tmdb_id or not name:
            return None
        
        person, created = Person.objects.get_or_create(
            tmdb_id=tmdb_id,
            defaults={
                'name': name,
                'profile_picture': tmdb_service.get_image_url(
                    person_data.get('profile_path')
                )
            }
        )
        
        return person
    
    def map_crew_job_to_role(self, job):
        """Map TMDB crew job to our role choices"""
        job_mapping = {
            'director': 'director',
            'producer': 'producer',
            'executive producer': 'producer',
            'writer': 'writer',
            'screenplay': 'writer',
            'story': 'writer',
            'director of photography': 'cinematographer',
            'cinematography': 'cinematographer',
            'original music composer': 'composer',
            'music': 'composer',
            'editor': 'editor',
            'film editor': 'editor',
        }
        
        return job_mapping.get(job)
    
    def map_status(self, tmdb_status):
        """Map TMDB status to our status choices"""
        status_mapping = {
            'Released': 'released',
            'Post Production': 'post_production',
            'In Production': 'in_production',
            'Planned': 'upcoming',
            'Canceled': 'cancelled',
            'Rumored': 'upcoming',
        }
        
        return status_mapping.get(tmdb_status, 'released')
    
    def parse_date(self, date_string):
        """Parse date string to date object"""
        if not date_string:
            return None
        
        try:
            from datetime import datetime
            return datetime.strptime(date_string, '%Y-%m-%d').date()
        except ValueError:
            return None