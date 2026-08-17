from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import get_user_model
from movies.models import Movie, Rating, Genre
from recommendations.models import Recommendation, UserPreference, UserMovieInteraction
import logging
import requests
import json
import random
from datetime import datetime, timedelta

User = get_user_model()
logger = logging.getLogger('recommendations')

class Command(BaseCommand):
    help = 'Initialize the recommendation system with sample data and configurations'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--create-sample-data',
            action='store_true',
            help='Create sample users, movies, and ratings for testing'
        )
        parser.add_argument(
            '--sample-users',
            type=int,
            default=50,
            help='Number of sample users to create (default: 50)'
        )
        parser.add_argument(
            '--sample-movies',
            type=int,
            default=200,
            help='Number of sample movies to create (default: 200)'
        )
        parser.add_argument(
            '--sample-ratings',
            type=int,
            default=1000,
            help='Number of sample ratings to create (default: 1000)'
        )
        parser.add_argument(
            '--fetch-real-movies',
            action='store_true',
            help='Fetch real movie data from TMDB API'
        )
        parser.add_argument(
            '--setup-genres',
            action='store_true',
            help='Set up standard movie genres'
        )
        parser.add_argument(
            '--create-admin',
            action='store_true',
            help='Create admin user for testing'
        )
        parser.add_argument(
            '--reset-system',
            action='store_true',
            help='Reset the entire recommendation system (WARNING: Deletes all data)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force operations without confirmation'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output'
        )
    
    def handle(self, *args, **options):
        self.verbosity = options['verbosity']
        self.verbose = options['verbose']
        
        try:
            self.stdout.write(
                self.style.SUCCESS('Initializing Movie Recommendation System')
            )
            
            # Reset system if requested
            if options['reset_system']:
                self._reset_system(options)
            
            # Set up genres
            if options['setup_genres']:
                self._setup_genres()
            
            # Fetch real movies from TMDB
            if options['fetch_real_movies']:
                self._fetch_real_movies(options['sample_movies'])
            
            # Create sample data
            if options['create_sample_data']:
                self._create_sample_data(options)
            
            # Create admin user
            if options['create_admin']:
                self._create_admin_user()
            
            # Initialize system configurations
            self._initialize_configurations()
            
            # Verify system setup
            self._verify_setup()
            
            self.stdout.write(
                self.style.SUCCESS('Recommendation system initialization completed!')
            )
            
        except Exception as e:
            logger.error(f'System initialization failed: {str(e)}')
            raise CommandError(f'Initialization failed: {str(e)}')
    
    def _reset_system(self, options):
        """Reset the entire recommendation system"""
        if not options['force']:
            confirm = input(
                'This will delete ALL recommendation data. '
                'Are you sure? (yes/no): '
            )
            if confirm.lower() != 'yes':
                self.stdout.write('Reset cancelled.')
                return
        
        self.stdout.write(
            self.style.WARNING('Resetting recommendation system...')
        )
        
        with transaction.atomic():
            # Delete recommendation data
            Recommendation.objects.all().delete()
            UserMovieInteraction.objects.all().delete()
            UserPreference.objects.all().delete()
            Rating.objects.all().delete()
            
            # Optionally delete movies and users (be careful!)
            if options['force']:
                Movie.objects.all().delete()
                User.objects.filter(is_superuser=False).delete()
        
        # Clear cache
        cache.clear()
        
        self.stdout.write(
            self.style.SUCCESS('System reset completed')
        )
    
    def _setup_genres(self):
        """Set up standard movie genres"""
        self.stdout.write('Setting up movie genres...')
        
        standard_genres = [
            'Action', 'Adventure', 'Animation', 'Comedy', 'Crime',
            'Documentary', 'Drama', 'Family', 'Fantasy', 'History',
            'Horror', 'Music', 'Mystery', 'Romance', 'Science Fiction',
            'TV Movie', 'Thriller', 'War', 'Western', 'Biography',
            'Musical', 'Sport', 'Film-Noir', 'Short'
        ]
        
        created_count = 0
        for genre_name in standard_genres:
            genre, created = Genre.objects.get_or_create(
                name=genre_name,
                defaults={'tmdb_id': None}
            )
            if created:
                created_count += 1
        
        self.stdout.write(
            f'Created {created_count} new genres '
            f'({Genre.objects.count()} total)'
        )
    
    def _fetch_real_movies(self, count):
        """Fetch real movie data from TMDB API"""
        if not hasattr(settings, 'TMDB_API_KEY') or not settings.TMDB_API_KEY:
            self.stdout.write(
                self.style.WARNING(
                    'TMDB_API_KEY not configured. Skipping real movie fetch.'
                )
            )
            return
        
        self.stdout.write(f'Fetching {count} real movies from TMDB...')
        
        api_key = settings.TMDB_API_KEY
        base_url = 'https://api.themoviedb.org/3'
        
        created_count = 0
        pages_to_fetch = min(count // 20 + 1, 10)  # TMDB returns 20 per page
        
        try:
            for page in range(1, pages_to_fetch + 1):
                url = f'{base_url}/movie/popular'
                params = {
                    'api_key': api_key,
                    'page': page,
                    'language': 'en-US'
                }
                
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                
                for movie_data in data.get('results', []):
                    if created_count >= count:
                        break
                    
                    # Check if movie already exists
                    if Movie.objects.filter(
                        tmdb_id=movie_data['id']
                    ).exists():
                        continue
                    
                    # Create movie
                    movie = self._create_movie_from_tmdb(movie_data)
                    if movie:
                        created_count += 1
                        
                        if self.verbose:
                            self.stdout.write(
                                f'Created movie: {movie.title}'
                            )
                
                if created_count >= count:
                    break
        
        except requests.RequestException as e:
            self.stdout.write(
                self.style.WARNING(
                    f'Error fetching movies from TMDB: {str(e)}'
                )
            )
        
        self.stdout.write(
            f'Created {created_count} movies from TMDB '
            f'({Movie.objects.count()} total)'
        )
    
    def _create_movie_from_tmdb(self, movie_data):
        """Create a movie from TMDB data"""
        try:
            # Parse release date
            release_date = None
            if movie_data.get('release_date'):
                try:
                    release_date = datetime.strptime(
                        movie_data['release_date'], '%Y-%m-%d'
                    ).date()
                except ValueError:
                    pass
            
            # Create movie
            movie = Movie.objects.create(
                title=movie_data['title'],
                overview=movie_data.get('overview', ''),
                release_date=release_date,
                tmdb_id=movie_data['id'],
                imdb_id=None,  # Would need additional API call
                poster_path=movie_data.get('poster_path'),
                backdrop_path=movie_data.get('backdrop_path'),
                average_rating=movie_data.get('vote_average', 0),
                vote_count=movie_data.get('vote_count', 0),
                popularity=movie_data.get('popularity', 0),
                runtime=None,  # Would need additional API call
                budget=None,
                revenue=None,
                status='Released'
            )
            
            # Add genres
            for genre_id in movie_data.get('genre_ids', []):
                # Map TMDB genre IDs to our genres
                genre_mapping = {
                    28: 'Action', 12: 'Adventure', 16: 'Animation',
                    35: 'Comedy', 80: 'Crime', 99: 'Documentary',
                    18: 'Drama', 10751: 'Family', 14: 'Fantasy',
                    36: 'History', 27: 'Horror', 10402: 'Music',
                    9648: 'Mystery', 10749: 'Romance', 878: 'Science Fiction',
                    10770: 'TV Movie', 53: 'Thriller', 10752: 'War',
                    37: 'Western'
                }
                
                genre_name = genre_mapping.get(genre_id)
                if genre_name:
                    genre, _ = Genre.objects.get_or_create(name=genre_name)
                    movie.genres.add(genre)
            
            return movie
            
        except Exception as e:
            logger.warning(
                f'Failed to create movie from TMDB data: {str(e)}'
            )
            return None
    
    def _create_sample_data(self, options):
        """Create sample users, movies, and ratings"""
        self.stdout.write('Creating sample data...')
        
        # Create sample users
        self._create_sample_users(options['sample_users'])
        
        # Create sample movies (if not fetching real ones)
        if not options['fetch_real_movies']:
            self._create_sample_movies(options['sample_movies'])
        
        # Create sample ratings
        self._create_sample_ratings(options['sample_ratings'])
        
        # Create sample user preferences
        self._create_sample_preferences()
    
    def _create_sample_users(self, count):
        """Create sample users"""
        self.stdout.write(f'Creating {count} sample users...')
        
        created_count = 0
        for i in range(count):
            username = f'user_{i+1:03d}'
            email = f'user{i+1:03d}@example.com'
            
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password='testpass123',
                    first_name=f'User',
                    last_name=f'{i+1:03d}',
                    is_active=True
                )
                created_count += 1
                
                if self.verbose:
                    self.stdout.write(f'Created user: {username}')
        
        self.stdout.write(
            f'Created {created_count} users '
            f'({User.objects.count()} total)'
        )
    
    def _create_sample_movies(self, count):
        """Create sample movies"""
        self.stdout.write(f'Creating {count} sample movies...')
        
        # Sample movie data
        sample_titles = [
            'The Adventure Begins', 'Mystery of the Lost City',
            'Romance in Paris', 'Action Hero Returns',
            'Comedy Night Out', 'Horror in the Woods',
            'Sci-Fi Future', 'Drama of Life', 'Fantasy Quest',
            'Thriller Chase', 'War Stories', 'Western Sunset'
        ]
        
        genres = list(Genre.objects.all())
        if not genres:
            self._setup_genres()
            genres = list(Genre.objects.all())
        
        created_count = 0
        for i in range(count):
            title = f"{random.choice(sample_titles)} {i+1}"
            
            if not Movie.objects.filter(title=title).exists():
                movie = Movie.objects.create(
                    title=title,
                    overview=f'This is a sample movie description for {title}.',
                    release_date=self._random_date(),
                    average_rating=round(random.uniform(3.0, 9.0), 1),
                    vote_count=random.randint(100, 10000),
                    popularity=round(random.uniform(1.0, 100.0), 1),
                    runtime=random.randint(80, 180),
                    status='Released'
                )
                
                # Add random genres
                movie_genres = random.sample(
                    genres, 
                    random.randint(1, min(3, len(genres)))
                )
                movie.genres.set(movie_genres)
                
                created_count += 1
                
                if self.verbose:
                    self.stdout.write(f'Created movie: {title}')
        
        self.stdout.write(
            f'Created {created_count} movies '
            f'({Movie.objects.count()} total)'
        )
    
    def _create_sample_ratings(self, count):
        """Create sample ratings"""
        self.stdout.write(f'Creating {count} sample ratings...')
        
        users = list(User.objects.all())
        movies = list(Movie.objects.all())
        
        if not users or not movies:
            self.stdout.write(
                self.style.WARNING(
                    'No users or movies found. Create them first.'
                )
            )
            return
        
        created_count = 0
        attempts = 0
        max_attempts = count * 3  # Avoid infinite loop
        
        while created_count < count and attempts < max_attempts:
            user = random.choice(users)
            movie = random.choice(movies)
            
            # Check if rating already exists
            if not Rating.objects.filter(user=user, movie=movie).exists():
                rating_value = random.choice([1, 2, 3, 4, 5])
                # Bias towards higher ratings
                if random.random() < 0.3:
                    rating_value = random.choice([4, 5])
                
                Rating.objects.create(
                    user=user,
                    movie=movie,
                    rating=rating_value,
                    created_at=self._random_datetime()
                )
                
                created_count += 1
                
                if self.verbose and created_count % 100 == 0:
                    self.stdout.write(
                        f'Created {created_count} ratings...'
                    )
            
            attempts += 1
        
        self.stdout.write(
            f'Created {created_count} ratings '
            f'({Rating.objects.count()} total)'
        )
    
    def _create_sample_preferences(self):
        """Create sample user preferences"""
        self.stdout.write('Creating sample user preferences...')
        
        users = User.objects.all()
        genres = list(Genre.objects.all())
        
        if not genres:
            self.stdout.write(
                self.style.WARNING('No genres found. Set up genres first.')
            )
            return
        
        created_count = 0
        for user in users:
            if not UserPreference.objects.filter(user=user).exists():
                # Select random favorite genres
                favorite_genres = random.sample(
                    genres, 
                    random.randint(1, min(5, len(genres)))
                )
                
                UserPreference.objects.create(
                    user=user,
                    favorite_genres=','.join([g.name for g in favorite_genres]),
                    preferred_decade=random.choice([
                        '1980s', '1990s', '2000s', '2010s', '2020s'
                    ]),
                    min_rating=random.choice([3.0, 4.0, 5.0]),
                    preferred_runtime_min=random.choice([80, 90, 100]),
                    preferred_runtime_max=random.choice([120, 150, 180])
                )
                
                created_count += 1
        
        self.stdout.write(
            f'Created {created_count} user preferences '
            f'({UserPreference.objects.count()} total)'
        )
    
    def _create_admin_user(self):
        """Create admin user for testing"""
        username = 'admin'
        email = 'admin@example.com'
        password = 'admin123'
        
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'Admin user "{username}" already exists')
            )
            return
        
        admin_user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            first_name='Admin',
            last_name='User'
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Created admin user: {username} (password: {password})'
            )
        )
    
    def _initialize_configurations(self):
        """Initialize system configurations"""
        self.stdout.write('Initializing system configurations...')
        
        # Set initial cache values
        cache.set('system_initialized', True, timeout=None)
        cache.set('initialization_date', timezone.now(), timeout=None)
        
        # Initialize ML settings in cache
        cache.set('ml_system_ready', False, timeout=None)
        cache.set('ml_last_training', None, timeout=None)
        
        self.stdout.write('System configurations initialized')
    
    def _verify_setup(self):
        """Verify system setup"""
        self.stdout.write('Verifying system setup...')
        
        # Check data counts
        user_count = User.objects.count()
        movie_count = Movie.objects.count()
        rating_count = Rating.objects.count()
        genre_count = Genre.objects.count()
        
        self.stdout.write(f'Users: {user_count}')
        self.stdout.write(f'Movies: {movie_count}')
        self.stdout.write(f'Ratings: {rating_count}')
        self.stdout.write(f'Genres: {genre_count}')
        
        # Check minimum requirements
        issues = []
        if user_count < 5:
            issues.append(f'Too few users: {user_count} (need at least 5)')
        if movie_count < 10:
            issues.append(f'Too few movies: {movie_count} (need at least 10)')
        if rating_count < 20:
            issues.append(f'Too few ratings: {rating_count} (need at least 20)')
        if genre_count < 5:
            issues.append(f'Too few genres: {genre_count} (need at least 5)')
        
        if issues:
            self.stdout.write(
                self.style.WARNING('Setup verification issues:')
            )
            for issue in issues:
                self.stdout.write(f'  - {issue}')
        else:
            self.stdout.write(
                self.style.SUCCESS('✓ System setup verification passed')
            )
    
    def _random_date(self):
        """Generate random date within last 20 years"""
        start_date = datetime.now().date() - timedelta(days=20*365)
        end_date = datetime.now().date()
        
        time_between = end_date - start_date
        days_between = time_between.days
        random_days = random.randrange(days_between)
        
        return start_date + timedelta(days=random_days)
    
    def _random_datetime(self):
        """Generate random datetime within last 2 years"""
        start_date = timezone.now() - timedelta(days=2*365)
        end_date = timezone.now()
        
        time_between = end_date - start_date
        seconds_between = time_between.total_seconds()
        random_seconds = random.randrange(int(seconds_between))
        
        return start_date + timedelta(seconds=random_seconds)