from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from django.urls import reverse

User = get_user_model()


class Genre(models.Model):
    """Movie genres"""
    
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'genres'
        verbose_name = 'Genre'
        verbose_name_plural = 'Genres'
        ordering = ['name']
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name


class Language(models.Model):
    """Movie languages"""
    
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=10, unique=True)  # ISO language code
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'languages'
        verbose_name = 'Language'
        verbose_name_plural = 'Languages'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Country(models.Model):
    """Movie production countries"""
    
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=3, unique=True)  # ISO country code
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'countries'
        verbose_name = 'Country'
        verbose_name_plural = 'Countries'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Person(models.Model):
    """Directors, actors, and other crew members"""
    
    ROLE_CHOICES = [
        ('director', 'Director'),
        ('actor', 'Actor'),
        ('producer', 'Producer'),
        ('writer', 'Writer'),
        ('cinematographer', 'Cinematographer'),
        ('composer', 'Composer'),
        ('editor', 'Editor'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    biography = models.TextField(blank=True)
    birth_date = models.DateField(null=True, blank=True)
    death_date = models.DateField(null=True, blank=True)
    birth_place = models.CharField(max_length=200, blank=True)
    profile_picture = models.URLField(blank=True)
    
    # External IDs
    tmdb_id = models.PositiveIntegerField(null=True, blank=True, unique=True)
    imdb_id = models.CharField(max_length=20, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'persons'
        verbose_name = 'Person'
        verbose_name_plural = 'Persons'
        ordering = ['name']
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name


class Movie(models.Model):
    """Main Movie model"""
    
    STATUS_CHOICES = [
        ('released', 'Released'),
        ('upcoming', 'Upcoming'),
        ('in_production', 'In Production'),
        ('post_production', 'Post Production'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Basic Information
    title = models.CharField(max_length=300)
    original_title = models.CharField(max_length=300, blank=True)
    slug = models.SlugField(max_length=300, unique=True, blank=True)
    tagline = models.CharField(max_length=500, blank=True)
    overview = models.TextField(blank=True)
    
    # Release Information
    release_date = models.DateField(null=True, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='released')
    
    # Technical Details
    duration = models.PositiveIntegerField(null=True, blank=True, help_text="Duration in minutes")
    budget = models.BigIntegerField(null=True, blank=True)
    revenue = models.BigIntegerField(null=True, blank=True)
    
    # Media
    poster_url = models.URLField(blank=True)
    backdrop_url = models.URLField(blank=True)
    trailer_url = models.URLField(blank=True)
    
    # Ratings and Popularity
    tmdb_rating = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(10.0)]
    )
    imdb_rating = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(10.0)]
    )
    average_rating = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(5.0)]
    )
    total_ratings = models.PositiveIntegerField(default=0)
    popularity = models.FloatField(default=0.0)
    
    # Content Rating
    adult = models.BooleanField(default=False)
    content_rating = models.CharField(max_length=10, blank=True)  # PG, PG-13, R, etc.
    
    # Relationships
    genres = models.ManyToManyField(Genre, blank=True, related_name='movies')
    languages = models.ManyToManyField(Language, blank=True, related_name='movies')
    countries = models.ManyToManyField(Country, blank=True, related_name='movies')
    
    # External IDs
    tmdb_id = models.PositiveIntegerField(null=True, blank=True, unique=True)
    imdb_id = models.CharField(max_length=20, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'movies'
        verbose_name = 'Movie'
        verbose_name_plural = 'Movies'
        ordering = ['-release_date', '-created_at']
        indexes = [
            models.Index(fields=['title']),
            models.Index(fields=['release_date']),
            models.Index(fields=['year']),
            models.Index(fields=['average_rating']),
            models.Index(fields=['tmdb_id']),
            models.Index(fields=['imdb_id']),
            models.Index(fields=['popularity']),  # For trending/popular queries
            models.Index(fields=['release_date', 'average_rating']),  # Composite for filtering
            models.Index(fields=['popularity', 'average_rating']),  # For trending/popular queries
            models.Index(fields=['duration']),  # For duration-based filtering
            models.Index(fields=['budget']),  # For budget-based queries
            models.Index(fields=['revenue']),  # For revenue-based queries
            models.Index(fields=['status']),  # For status-based filtering
            models.Index(fields=['adult']),  # For content filtering
        ]
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(f"{self.title}-{self.year or ''}")
            self.slug = base_slug
            
            # Ensure unique slug
            counter = 1
            while Movie.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        
        if self.release_date and not self.year:
            self.year = self.release_date.year
            
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.title} ({self.year or 'TBA'})"
    
    def get_absolute_url(self):
        return reverse('movie-detail', kwargs={'slug': self.slug})
    
    def update_rating(self):
        """Update average rating based on user ratings"""
        ratings = self.ratings.all()
        if ratings.exists():
            avg_rating = ratings.aggregate(avg=models.Avg('rating'))['avg']
            self.average_rating = round(avg_rating, 2)
            self.total_ratings = ratings.count()
        else:
            self.average_rating = 0.0
            self.total_ratings = 0
        self.save(update_fields=['average_rating', 'total_ratings'])


class MovieCast(models.Model):
    """Movie cast and crew relationships"""
    
    ROLE_CHOICES = [
        ('director', 'Director'),
        ('actor', 'Actor'),
        ('producer', 'Producer'),
        ('writer', 'Writer'),
        ('cinematographer', 'Cinematographer'),
        ('composer', 'Composer'),
        ('editor', 'Editor'),
        ('other', 'Other'),
    ]
    
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='cast')
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='filmography')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    character_name = models.CharField(max_length=200, blank=True)  # For actors
    order = models.PositiveIntegerField(default=0)  # For ordering cast members
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'movie_cast'
        verbose_name = 'Movie Cast'
        verbose_name_plural = 'Movie Cast'
        unique_together = ['movie', 'person', 'role']
        ordering = ['order', 'person__name']
        indexes = [
            models.Index(fields=['movie', 'role']),  # For cast/crew queries
            models.Index(fields=['person', 'role']),  # For person filmography
            models.Index(fields=['role']),  # For role-based filtering
            models.Index(fields=['order']),  # For ordering cast members
        ]
    
    def __str__(self):
        if self.character_name:
            return f"{self.person.name} as {self.character_name} in {self.movie.title}"
        return f"{self.person.name} ({self.role}) in {self.movie.title}"


class Rating(models.Model):
    """User ratings for movies"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings')
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='ratings')
    rating = models.FloatField(
        validators=[MinValueValidator(1.0), MaxValueValidator(5.0)]
    )
    review = models.TextField(blank=True)
    is_implicit = models.BooleanField(default=False, help_text="Rating derived from user feedback rather than explicit rating")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ratings'
        verbose_name = 'Rating'
        verbose_name_plural = 'Ratings'
        unique_together = ['user', 'movie']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['rating']),
            models.Index(fields=['created_at']),
            models.Index(fields=['user', 'rating']),  # For user rating analysis
            models.Index(fields=['movie', 'rating']),  # For movie rating analysis
            models.Index(fields=['user', 'created_at']),  # For user activity timeline
            models.Index(fields=['movie', 'created_at']),  # For movie rating timeline
        ]
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update movie's average rating
        self.movie.update_rating()
        # Update user's statistics
        self.user.update_statistics()
    
    def delete(self, *args, **kwargs):
        movie = self.movie
        user = self.user
        super().delete(*args, **kwargs)
        # Update movie's average rating
        movie.update_rating()
        # Update user's statistics
        user.update_statistics()
    
    def __str__(self):
        return f"{self.user.get_full_name()} rated {self.movie.title}: {self.rating}/5"


class Watchlist(models.Model):
    """User watchlists"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='watchlist')
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='in_watchlists')
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'watchlists'
        verbose_name = 'Watchlist Item'
        verbose_name_plural = 'Watchlist Items'
        unique_together = ['user', 'movie']
        ordering = ['-added_at']
        indexes = [
            models.Index(fields=['user', 'added_at']),  # For user watchlist queries
            models.Index(fields=['movie']),  # For movie popularity in watchlists
            models.Index(fields=['added_at']),  # For chronological queries
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()}'s watchlist: {self.movie.title}"


class Trailer(models.Model):
    """Movie trailers"""
    
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='trailers')
    name = models.CharField(max_length=255)
    key = models.CharField(max_length=50)  # YouTube video key
    site = models.CharField(max_length=50, default='YouTube')
    type = models.CharField(max_length=50)  # Trailer, Teaser, etc.
    official = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'trailers'
        verbose_name = 'Trailer'
        verbose_name_plural = 'Trailers'
        ordering = ['-published_at', '-created_at']
        unique_together = ['movie', 'key']
        indexes = [
            models.Index(fields=['movie', 'type']),
            models.Index(fields=['published_at']),
        ]
    
    def __str__(self):
        return f"{self.movie.title} - {self.name}"
    
    @property
    def youtube_url(self):
        """Get YouTube URL for the trailer"""
        if self.site == 'YouTube':
            return f"https://www.youtube.com/watch?v={self.key}"
        return None
    
    @property
    def embed_url(self):
        """Get YouTube embed URL for the trailer"""
        if self.site == 'YouTube':
            return f"https://www.youtube.com/embed/{self.key}"
        return None
