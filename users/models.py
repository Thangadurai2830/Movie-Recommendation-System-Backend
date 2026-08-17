from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication"""
    
    def create_user(self, email, first_name, last_name, password=None, **extra_fields):
        """Create and return a regular user with an email and password."""
        if not email:
            raise ValueError('The Email field must be set')
        if not first_name:
            raise ValueError('The First Name field must be set')
        if not last_name:
            raise ValueError('The Last Name field must be set')
            
        email = self.normalize_email(email)
        # Generate username from email (for compatibility)
        username = email.split('@')[0]
        
        user = self.model(
            email=email,
            username=username,
            first_name=first_name,
            last_name=last_name,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, first_name, last_name, password=None, **extra_fields):
        """Create and return a superuser with an email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
            
        return self.create_user(email, first_name, last_name, password, **extra_fields)


class User(AbstractUser):
    """Custom User model with additional fields for movie recommendations"""
    
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    date_of_birth = models.DateField(null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    profile_picture = models.URLField(blank=True)
    
    # Preference fields
    favorite_genres = models.ManyToManyField(
        'movies.Genre', 
        blank=True, 
        related_name='users_who_like'
    )
    preferred_languages = models.ManyToManyField(
        'movies.Language', 
        blank=True, 
        related_name='users_who_prefer'
    )
    
    # Statistics
    total_movies_watched = models.PositiveIntegerField(default=0)
    total_ratings_given = models.PositiveIntegerField(default=0)
    average_rating = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(5.0)]
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_active = models.DateTimeField(auto_now=True)
    
    # Email verification
    is_email_verified = models.BooleanField(default=False)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    objects = UserManager()
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),  # For login and lookups
            models.Index(fields=['username']),  # For username lookups
            models.Index(fields=['is_email_verified']),  # For verification status
            models.Index(fields=['last_active']),  # For activity tracking
            models.Index(fields=['created_at']),  # For registration timeline
            models.Index(fields=['total_ratings_given']),  # For user statistics
            models.Index(fields=['average_rating']),  # For user analysis
            models.Index(fields=['date_of_birth']),  # For demographic analysis
        ]
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    def update_statistics(self):
        """Update user statistics based on their ratings"""
        from movies.models import Rating
        
        user_ratings = Rating.objects.filter(user=self)
        self.total_ratings_given = user_ratings.count()
        
        if self.total_ratings_given > 0:
            avg_rating = user_ratings.aggregate(
                avg=models.Avg('rating')
            )['avg']
            self.average_rating = round(avg_rating, 2) if avg_rating else 0.0
        
        # Count unique movies watched (rated)
        self.total_movies_watched = user_ratings.values('movie').distinct().count()
        self.save(update_fields=['total_ratings_given', 'average_rating', 'total_movies_watched'])


class UserProfile(models.Model):
    """Extended user profile for additional preferences"""
    
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='profile'
    )
    
    # Privacy settings
    is_profile_public = models.BooleanField(default=True)
    show_ratings = models.BooleanField(default=True)
    show_watchlist = models.BooleanField(default=True)
    
    # Notification preferences
    email_notifications = models.BooleanField(default=True)
    recommendation_emails = models.BooleanField(default=True)
    
    # Recommendation preferences
    min_rating_threshold = models.FloatField(
        default=3.0,
        validators=[MinValueValidator(1.0), MaxValueValidator(5.0)],
        help_text="Minimum rating for movie recommendations"
    )
    
    exclude_adult_content = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_profiles'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
        indexes = [
            models.Index(fields=['user']),  # For profile lookups
            models.Index(fields=['is_profile_public']),  # For public profile queries
            models.Index(fields=['email_notifications']),  # For notification targeting
            models.Index(fields=['recommendation_emails']),  # For email campaigns
            models.Index(fields=['exclude_adult_content']),  # For content filtering
            models.Index(fields=['min_rating_threshold']),  # For recommendation filtering
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()}'s Profile"


# Signal handlers
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create UserProfile when User is created"""
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save UserProfile when User is saved"""
    if hasattr(instance, 'profile'):
        instance.profile.save()
